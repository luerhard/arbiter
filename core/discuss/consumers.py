from collections import defaultdict
import json
import logging

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator

from .models import Message
from .models import Room
from .room_state import get_state
from .room_state import update_state
from data.models import Annotation
from data.models import Example
from projects.models import Batch

# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.route = self.scope["url_route"]
        self.batch_id = self.scope["url_route"]["kwargs"]["batch_id"]
        self.room_group_name = f"chat_{self.batch_id}"
        self.user = self.scope["user"]
        self.username = getattr(self.user, "username", str(self.user))
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)  # type: ignore
        await self.accept()

        # Initialize / update room state in Redis
        async def _init(state):
            # required users (usernames) once
            if not state["required_users"]:
                annotators = await self.get_assigned_annotators()
                state["required_users"] = sorted({u.username for u in annotators})
            # join online users
            if self.username not in state["online_users"]:
                state["online_users"].append(self.username)
            # init clicked_done entry
            state["clicked_done"].setdefault(self.username, 0)
            return state

        await self._append_chat_message(
            username="system",
            message=f"{self.username} is now connected.",
        )
        state = await update_state(self.batch_id, _init)
        log.debug(f"Current {state=} ")

        if (set(state["online_users"]) == set(state["required_users"])) and not state[
            "discussion_ended"
        ]:
            if state["page"] == 0:
                await self._set_next_and_reset()
        await self.group_send_state()

    async def disconnect(self, close_code):  # noqa: ARG002
        async def _leave(state):
            if self.username in state["online_users"]:
                state["online_users"].remove(self.username)
            state["clicked_done"].pop(self.username, None)

            return state

        state = await update_state(self.batch_id, _leave)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)  # type: ignore
        await self._append_chat_message(
            username="system",
            message=f"{self.username} has disconnected.",
        )
        await self.group_send_state()

        if len(state["online_users"]) == 0:
            log.debug("No users, closing websocket.")
            await self.close(code=1000)

    async def receive(self, text_data):
        data = json.loads(text_data)
        log.debug(f"Received: {data}")

        if "message" in data.keys():
            message = data["message"]
            username = self.user.username

            # return instantly if message is empty
            if not message.strip():
                return
            await self._append_chat_message(username=username, message=message)

            # send to all users
            await self.group_send_state()

        elif "clicked-done" in data.keys():
            labels = [label_id for label_id in data["labels"]]

            await self._store_discussion_labels(self.username, labels)
            log.debug(f"{self.username} clicked done.")
            await self._clicked_done(self.username)

            log.debug("Await self._all_done().")
            if await self._all_done():
                state = await self._get_state()
                # log.debug(f"{not state["discussion_ended"] = }")
                if not state["discussion_ended"]:
                    await self.save_labels_to_db()
                    await self._set_next_and_reset()
            await self.group_send_state()

    # ---------- LABEL HELPERS -----------------
    @database_sync_to_async
    def save_labels_to_db(self):
        """Write cached labels to DB for all users for the given example."""
        state = async_to_sync(self._get_state)()

        example = Example.objects.get(pk=state["cur_example_id"])

        # save per user
        for username, label_ids in (state["discussion_labels"] or {}).items():
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                continue
            example.set_user_annotations(user=user, label_ids=label_ids, phase="DISCUSSION")

    async def _store_discussion_labels(self, username, labels):
        async def mut(state):
            state["discussion_labels"][username] = labels
            return state

        return await update_state(self.batch_id, mut)

    async def _clicked_done(self, username):
        log.debug(f"{username = } clicked done.")

        async def mut(state):
            log.debug(f"{state["clicked_done"] = }")
            if state["clicked_done"][username]:
                # TODO: Looks like on reload the user can press Save & Done
                # even after having pressed it previously.
                # After pressing it again the boolean rotates.
                state["clicked_done"][username] = 0
                # This means the button should change the un/lock dynamically on the frontend.
            else:
                state["clicked_done"][username] = 1

            return state

        return await update_state(self.batch_id, mut)

    async def _all_done(self):
        state = await self._get_state()
        log.debug(f"{state = }")
        required = set(state.get("required_users", []))
        clicked = {u for u, v in (state.get("clicked_done", {}) or {}).items() if v == 1}
        log.debug(f"{required <= clicked = }")
        return required <= clicked

    # ---------- CHAT HELPERS -----------------
    def get_or_create_room(self):
        room, _ = Room.objects.get_or_create(pk=self.batch_id)
        return room

    @database_sync_to_async
    def save_message_to_db(self, username: str, message: str) -> None:
        log.debug(f"Save message from {username}: {message}")
        room = self.get_or_create_room()
        state = async_to_sync(self._get_state)()
        example_id = state.get("cur_example_id")
        example_kw = {"example_id": example_id} if example_id else {"example": None}
        Message.objects.create(room=room, user=username, message=message, **example_kw)

    async def _append_chat_message(self, username: str, message: str):
        async def _mut(s: dict, u=username, m=message):
            s["messages"].append({"user": u, "text": m})
            return s

        await self.save_message_to_db(username=username, message=message)
        return await update_state(self.batch_id, _mut)

    # ---------- STATE HELPERS -----------------
    async def _get_state(self):
        return await get_state(self.batch_id)

    async def _set_next_and_reset(self):
        state = await self._get_state()
        if state["discussion_ended"]:
            log.debug("Discussion ended.")
            return

        next_page = int(state.get("page", 0)) + 1
        state["page"] = next_page
        example, annotations = await database_sync_to_async(self.get_example)(state=state)

        end_reason = None
        msg = None
        if example is None:
            had_any = await database_sync_to_async(
                lambda: Example.objects.filter(batch=self.batch_id, has_disagreement=True).exists(),
            )()

            if not had_any:
                end_reason = "NO_EXAMPLES"
                msg = "No disagreements exist."

            else:
                end_reason = "DISCUSSION_END"
                msg = "All Examples discussed."

        else:
            if state["page"] != 1:
                msg = "All done. Next Sentence."

        async def mut(state):
            if end_reason:
                state["discussion_ended"] = end_reason
            else:
                state["page"] = next_page
                state["cur_example_id"] = example.id
                state["cur_example"] = example.content
                state["annotation_labels"] = annotations

                state["clicked_done"] = dict.fromkeys(state.get("online_users", []), 0)
            return state

        await update_state(self.batch_id, mut)

        if msg:
            await self._append_chat_message(username="system", message=msg)

    async def send_state(self, event):  # noqa: ARG002
        """Notify the connected clients in group that annotation ended."""
        await self.send(
            text_data=json.dumps(
                {"state": event["state"], "user": self.username},
                ensure_ascii=False,
            ),
        )

    async def group_send_state(self):
        state = await self._get_state()
        log.debug(f"Group send: {state=}")
        await self.channel_layer.group_send(  # type: ignore
            self.room_group_name,
            {
                "type": "send_state",
                "state": state,
            },
        )

    # ---------- EXAMPLE HELPERS -----------------

    def get_example(self, state):
        log.debug("Getting example")
        queryset = Example.objects.filter(batch=self.batch_id, has_disagreement=True).distinct()
        log.debug(f"{queryset = }")
        paginator = Paginator(queryset, 1)
        page_obj = paginator.get_page(state["page"])

        if page_obj.number < state["page"] or not queryset.count():
            return None, None

        example = page_obj.object_list[0]

        log.debug("Getting annotations")
        all_labels = example.labels.all()

        by_user = defaultdict(list)
        for user in state["required_users"]:
            query = Annotation.objects.filter(
                assignment__example=example,
                assignment__user__username=user,
                phase=Annotation.Phase.ANNOTATION,
            ).select_related("label")
            label_set = {anno.label for anno in query}

            for label in all_labels:
                label = (
                    {
                        "id": label.id,
                        "label": label.name,
                        "color": label.color,
                        "is_set": True if label in label_set else False,
                    },
                )
                by_user[user].append(label)

        return example, by_user

    @database_sync_to_async
    def get_assigned_annotators(self):
        return set(Batch.objects.get(id=self.batch_id).project.annotators)
