from collections import defaultdict
import json
import logging

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Message
from .models import Room
from .room_state import get_state
from .room_state import update_state
from data.models import Annotation
from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import BatchUser
from projects.models import ProjectRole

# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.joined = False
        self.route = self.scope["url_route"]
        self.batch_id = self.scope["url_route"]["kwargs"]["batch_id"]
        self.user = self.scope["user"]
        if not await self.is_batch_annotator():
            await self.close()
            return

        self.batch = await database_sync_to_async(Batch.objects.get)(id=self.batch_id)
        self.room_group_name = f"chat_{self.batch_id}"
        self.username = getattr(self.user, "username", str(self.user))
        self.joined = True
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)  # type: ignore
        await self.accept()

        # Initialize / update room state in Redis. A user can be connected more than once
        # (two tabs, or a reconnect while the server has not yet noticed the old socket
        # died), so the room tracks connections and a user is online while one is open.
        first_connection = False

        async def _init(state):
            nonlocal first_connection
            # required users (usernames) once
            if not state["required_users"]:
                annotators = await self.get_assigned_annotators()
                state["required_users"] = sorted({u.username for u in annotators})
            connections = state.setdefault("connections", {})
            first_connection = not connections.get(self.username)
            connections.setdefault(self.username, []).append(self.channel_name)
            state["online_users"] = list(connections)
            # init clicked_done entry
            state["clicked_done"].setdefault(self.username, 0)
            return state

        state = await update_state(self.batch_id, _init)
        log.debug(f"Current {state=} ")
        if first_connection:
            await self._append_chat_message(
                username="system",
                message=f"{self.username} is now connected.",
            )

        if (set(state["online_users"]) == set(state["required_users"])) and not state[
            "discussion_ended"
        ]:
            # start, or resync a room state whose example was decided in the meantime
            if state["page"] == 0 or not await self._is_open(state["cur_example_id"]):
                await self._set_next_and_reset()
        await self.group_send_state()

    async def disconnect(self, close_code):  # noqa: ARG002
        if not self.joined:
            return

        last_connection = False

        async def _leave(state):
            nonlocal last_connection
            connections = state.setdefault("connections", {})
            mine = [c for c in connections.get(self.username, []) if c != self.channel_name]
            last_connection = not mine
            if mine:
                connections[self.username] = mine
            else:
                connections.pop(self.username, None)
                state["clicked_done"].pop(self.username, None)
            state["online_users"] = list(connections)
            return state

        state = await update_state(self.batch_id, _leave)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)  # type: ignore
        if not last_connection:
            return  # another connection of this user is still in the room
        await self._append_chat_message(
            username="system",
            message=f"{self.username} has disconnected.",
        )
        await self.group_send_state()

        if len(state["online_users"]) == 0:
            log.debug("No users, closing websocket.")
            await self.close(code=1000)

    async def receive(self, text_data):
        # An exception escaping here would end the consumer: the socket closes, disconnect()
        # never runs, and a half-done save leaves both Done flags set with locked buttons,
        # so the room can never continue. Recover instead and let the users retry.
        saving = False
        try:
            data = json.loads(text_data)
            saving = isinstance(data, dict) and "clicked-done" in data
            await self._handle(data)
        except Exception:
            log.exception(f"Batch {self.batch_id}: handling a message of {self.username} failed")
            await self._recover(saving)

    async def _recover(self, saving: bool):
        """Put the room back into a state the users can retry from, and tell them."""
        try:
            if saving:

                async def mut(state):
                    state["clicked_done"] = dict.fromkeys(state["clicked_done"], 0)
                    return state

                await update_state(self.batch_id, mut)
                msg = "Saving failed. Please save your labels again."
            else:
                msg = f"Something went wrong with the last action of {self.username}."
            await self._append_chat_message(username="system", message=msg)
            await self.group_send_state()
            if saving:
                await self.channel_layer.group_send(  # type: ignore
                    self.room_group_name,
                    {"type": "save_failed"},
                )
        except Exception:
            # e.g. Redis is down: nothing more to do here, the users can reload
            log.exception(f"Batch {self.batch_id}: recovering from the error failed")

    async def _handle(self, data):
        log.debug(f"Received: {data}")

        if "message" in data.keys():
            message = data["message"]
            username = self.user.username
            if not isinstance(message, str):
                msg = f"message must be a string, got {message!r}"
                raise TypeError(msg)

            # return instantly if message is empty
            if not message.strip():
                return
            await self._append_chat_message(username=username, message=message)

            # send to all users
            await self.group_send_state()

        elif "typing" in data.keys():
            await self.channel_layer.group_send(  # type: ignore
                self.room_group_name,
                {
                    "type": "chat_typing",
                    "user": self.username,
                    "typing": bool(data["typing"]),
                },
            )

        elif "clicked-done" in data.keys():
            labels = await self._validated_labels(data.get("labels"))

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
    def _validated_labels(self, labels) -> list[int]:
        """The label ids a client sent, if they all are labels of this project."""
        if not isinstance(labels, list) or not all(
            isinstance(i, int) and not isinstance(i, bool) for i in labels
        ):
            msg = f"labels must be a list of label ids, got {labels!r}"
            raise ValueError(msg)
        unknown = set(labels) - set(self.batch.labels.values_list("id", flat=True))
        if unknown:
            msg = f"labels {sorted(unknown)} are not labels of this project"
            raise ValueError(msg)
        return labels

    @database_sync_to_async
    def save_labels_to_db(self):
        """Write cached labels to DB for all users for the given example: for all of them
        or, if anything fails, for none."""
        state = async_to_sync(self._get_state)()

        example = Example.objects.get(pk=state["cur_example_id"])

        with transaction.atomic():
            for username, label_ids in (state["discussion_labels"] or {}).items():
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    continue
                assignment = ExampleAssignment.objects.filter(
                    user=user,
                    example=example,
                    batch=self.batch,
                    phase=BatchPhase.DISCUSSION,
                ).get()
                assignment.set_user_annotations(label_ids=label_ids)

    async def _store_discussion_labels(self, username, labels):
        async def mut(state):
            state["discussion_labels"][username] = labels
            return state

        return await update_state(self.batch_id, mut)

    async def _clicked_done(self, username):
        log.debug(f"{username =} clicked done.")

        async def mut(state):
            log.debug(f"clicked done state: {state['clicked_done']}")
            if state["clicked_done"].get(username):
                # TODO: Looks like on reload the user can press Save & Done
                # even after having pressed it previously.
                # After pressing it again the boolean rotates.
                state["clicked_done"][username] = 0
                # This means the button should change the un/lock dynamically on the frontend.
            else:
                state["clicked_done"][username] = 1

            return state

        state = await update_state(self.batch_id, mut)

        # get labels
        labels = state["discussion_labels"][username]
        label_dict = await database_sync_to_async(Label.objects.in_bulk)(labels)
        label_names = [label_dict[i].name for i in labels]

        # print finalized message
        msg = f"{username} finalized their decision: {label_names}"
        await self._append_chat_message(username="system", message=msg)

        return

    async def _all_done(self):
        state = await self._get_state()
        log.debug(f"{state =}")
        required = set(state.get("required_users", []))
        clicked = {u for u, v in (state.get("clicked_done", {}) or {}).items() if v == 1}
        log.debug(f"{required <= clicked =}")
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

        example, annotations, page, total_pages = await database_sync_to_async(
            self.get_example,
        )(state=state)

        end_reason = None
        msg = None
        if example is None:
            if total_pages == 0:
                end_reason = "NO_EXAMPLES"
                msg = "No disagreements exist."

            else:
                end_reason = "DISCUSSION_END"
                msg = "All Examples discussed."

        elif state["page"] != 0:
            msg = "All done. Next Sentence."

        async def mut(state):
            if end_reason:
                state["discussion_ended"] = end_reason
            else:
                state["page"] = page
                state["cur_example_id"] = example.id
                state["cur_example"] = example.content
                state["annotation_labels"] = annotations
                state["total_pages"] = total_pages

                state["clicked_done"] = dict.fromkeys(state.get("online_users", []), 0)
            return state

        await update_state(self.batch_id, mut)

        if end_reason:
            await database_sync_to_async(self._advance_batch_after_discussion)()

        if msg:
            await self._append_chat_message(username="system", message=msg)

    def _advance_batch_after_discussion(self):
        # Re-fetch: self.batch was loaded at connect time and may be stale.
        batch = Batch.objects.get(pk=self.batch_id)
        new_phase = batch.advance_from_discussion()
        if new_phase is not None:
            log.info(f"Batch {batch.id} advanced to phase {new_phase} after discussion ended.")

    async def send_state(self, event):  # noqa: ARG002
        """Notify the connected clients in group that annotation ended."""
        await self.send(
            text_data=json.dumps(
                {"state": event["state"], "user": self.username},
                ensure_ascii=False,
            ),
        )

    async def save_failed(self, event):  # noqa: ARG002
        """Saving failed: the clients unlock their labels so the users can save again."""
        await self.send(text_data=json.dumps({"save_failed": True}))

    async def chat_typing(self, event):
        if event["user"] == self.username:
            return
        await self.send(
            text_data=json.dumps(
                {"typing": {"user": event["user"], "typing": event["typing"]}},
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
        """The next example to discuss: the first one (in batch order) that not every
        annotator has decided yet. The DISCUSSION assignments in the database are the
        source of truth, so a lost or stale room state resumes at the right example.

        Returns (example, annotation labels by user, page, total pages); example is
        None when nothing is left to discuss."""
        log.debug("Getting example")
        total_pages = self.batch.discussion_examples().count()
        open_examples = self.batch.open_discussion_examples()
        example = open_examples.first()
        if example is None:
            return None, None, total_pages, total_pages
        page = total_pages - open_examples.count() + 1

        log.debug("Getting annotations")
        all_labels = example.labels.all()

        by_user = defaultdict(list)
        for user in state["required_users"]:
            query = Annotation.objects.filter(
                assignment__example=example,
                assignment__user__username=user,
                assignment__phase=BatchPhase.ANNOTATION,
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

        return example, by_user, page, total_pages

    @database_sync_to_async
    def _is_open(self, example_id):
        return self.batch.open_discussion_examples().filter(id=example_id).exists()

    @database_sync_to_async
    def is_batch_annotator(self):
        return (
            self.user.is_authenticated
            and BatchUser.objects.filter(
                batch_id=self.batch_id,
                user_id=self.user.id,
                role=ProjectRole.ANNOTATOR,
            ).exists()
        )

    @database_sync_to_async
    def get_assigned_annotators(self):
        return set(Batch.objects.get(id=self.batch_id).assignees(role=ProjectRole.ANNOTATOR))
