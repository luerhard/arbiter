import json

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.paginator import Paginator
from django.urls import reverse

from .models import Message
from .models import Room
from data.models import Example
from projects.models import Batch


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.route = self.scope["url_route"]
        self.batch_id = self.scope["url_route"]["kwargs"]["batch_id"]
        self.room_group_name = f"chat_{self.batch_id}"
        self.user = self.scope["user"]
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # SET UP N ONLINE COUNT
        if "n_online" not in self.scope["room_state"]:
            self.scope["room_state"]["n_online"] = 0

        if "required_users" not in self.scope["room_state"]:
            self.scope["room_state"]["required_users"] = await self.get_assigned_annotators()

        if "online_users" not in self.scope["room_state"]:
            self.scope["room_state"]["online_users"] = {self.user}
        else:
            self.scope["room_state"]["online_users"].add(self.user)

        if "page" not in self.scope["room_state"]:
            self.scope["room_state"]["page"] = 1

        await self.group_send_user_connected()

        if self.scope["room_state"]["online_users"] == self.scope["room_state"]["required_users"]:
            await self.group_send_current_example()

        # SET UP SYNCED BUTTONS
        if "clicked_done" not in self.scope["room_state"]:
            self.scope["room_state"]["clicked_done"] = {self.user.username: 0}
        elif self.user.username not in self.scope["room_state"]["clicked_done"]:
            self.scope["room_state"]["clicked_done"][self.user.username] = 0

    # GENERAL
    async def disconnect(self, close_code):  # noqa: ARG002
        await self.group_send_user_disconnected()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        # if chat message is sent
        if "message" in data.keys():
            message = data["message"]
            # return instantly if message is empty
            if not message.strip():
                return
            username = self.user.username
            # send to all users
            await self.group_send_chat_message(username=username, message=message)

        elif "clicked-done" in data.keys():
            labels = [int(label_id) for label_id in json.loads(data["labels"]) if label_id.strip()]
            await self.save_annotation(labels)
            await self.group_send_user_done()

    @async_to_sync
    async def group_send_done(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_done",
            },
        )

    async def send_done(self, event):  # noqa: ARG002
        await self.send(
            text_data=json.dumps({"done": reverse("discussion-done")}, ensure_ascii=False),
        )

    # Example UI
    def get_example(self, page):
        queryset = Example.objects.filter(batch=self.batch_id, has_disagreement=True).all()
        paginator = Paginator(queryset, 1)
        page_obj = paginator.get_page(page)

        if page_obj.number < page:
            self.group_send_done()
        try:
            example = page_obj.object_list[0]
        except IndexError as e:
            raise e

        return example

    @database_sync_to_async
    def example_annotations(self, page):
        example = self.get_example(page)
        annotations = {}
        for user in self.scope["room_state"]["online_users"]:
            labels = []
            query = example.get_user_annotations(user, phase="ANNOTATION").select_related("label")
            label_set = {anno.label for anno in query}
            for label in example.labels.all():
                labels.append(
                    {
                        "id": label.id,
                        "label": label.name,
                        "is_set": True if label in label_set else False,
                    },
                )
            annotations[user.username] = labels

        return example, annotations

    @database_sync_to_async
    def save_annotation(self, label_ids):
        example = self.get_example(self.scope["room_state"]["page"])
        example.set_user_annotations(user=self.user, label_ids=label_ids, phase="DISCUSSION")

    async def group_send_current_example(self):
        example, prev_annotations = await self.example_annotations(
            self.scope["room_state"]["page"],
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_current_example",
                "update-example": example.content,
                "update-labels": prev_annotations,
            },
        )

    async def send_current_example(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "update-example": event["update-example"],
                    "update-labels": event["update-labels"],
                    "current-user": self.user.username,
                },
                ensure_ascii=False,
            ),
        )

    async def group_send_next_example(self):
        self.scope["room_state"]["page"] += 1
        example, prev_annotations = await self.example_annotations(
            self.scope["room_state"]["page"],
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_next_example",
                "update-example": example.content,
                "update-labels": prev_annotations,
            },
        )

    async def send_next_example(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "update-example": event["update-example"],
                    "update-labels": event["update-labels"],
                    "current-user": self.user.username,
                },
                ensure_ascii=False,
            ),
        )

    async def group_send_user_done(self):
        self.scope["room_state"]["clicked_done"][self.user.username] = 1
        if not all(x == 1 for x in self.scope["room_state"]["clicked_done"].values()):
            # TODO: maybe UPDATE UI of other users to show that this user has clicked done.
            return

        # send to all users
        chat_msg = "All users done. Next sentence."
        await self.group_send_chat_message(username="system", message=chat_msg)

        await self.group_send_next_example()

        # reset clicked_done
        clicked_done = self.scope["room_state"]["clicked_done"]
        for key in clicked_done:
            clicked_done[key] = 0

    # CHAT
    def get_or_create_room(self):
        room, _ = Room.objects.get_or_create(pk=self.batch_id)
        return room

    @staticmethod
    def create_chat_message(msg, msg_type):
        if msg_type == "self-message":
            div_class = "self-message"
            container_class = "d-flex flex-row-reverse"
        elif msg_type == "other-message":
            div_class = "other-message"
            container_class = "d-flex flex-row"
        elif msg_type == "system-message":
            div_class = "system-message"
            container_class = "d-flex flex-row"
        else:
            err_msg = f"Unknow message type: {msg_type}"
            raise ValueError(err_msg)

        message_html = (
            f"<div class='{container_class}'><div class='message {div_class}'>{msg}</div></div>"
        )
        composed_message = f"<div hx-swap-oob='beforeend:#messages'>{message_html}</div>"
        return composed_message

    async def group_send_chat_message(self, username, message):
        # store message in db
        await self.save_message_to_db(username=username, message=message)
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_chat_message", "message": message, "username": username},
        )

    async def send_chat_message(self, event):
        message = event["message"]
        username = event["username"]

        if self.user.username == username:
            chat_message = self.create_chat_message(message, msg_type="self-message")
        elif username == "system":
            chat_message = self.create_chat_message(message, msg_type="system-message")
        else:
            chat_message = self.create_chat_message(message, msg_type="other-message")

        await self.send(text_data=json.dumps({"message": chat_message}, ensure_ascii=False))

    @database_sync_to_async
    def save_message_to_db(self, username, message):
        room = self.get_or_create_room()
        example = self.get_example(self.scope["room_state"]["page"])
        Message.objects.create(room=room, example=example, user=username, message=message)
        return None

    # ONLINE STATUS

    @database_sync_to_async
    def get_assigned_annotators(self):
        return set(Batch.objects.get(id=self.batch_id).project.annotators)

    @staticmethod
    def create_n_online_message(n_online):
        msg = f"<div id='n-online-status' hx-swap-oob='true'> {n_online}</div>"
        return msg

    async def group_send_user_connected(self):
        self.scope["room_state"]["n_online"] += 1
        msg = f"{self.user.username} is now connected."
        await self.group_send_chat_message(username="system", message=msg)
        n_online_msg = self.create_n_online_message(self.scope["room_state"]["n_online"])

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_user_connected", "n_online": n_online_msg},
        )

    async def send_user_connected(self, event):
        n_online = event["n_online"]
        await self.send(
            text_data=json.dumps({"n_online": n_online}, ensure_ascii=False),
        )

    async def group_send_user_disconnected(self):
        self.scope["room_state"]["n_online"] -= 1
        self.scope["room_state"]["online_users"].discard(self.user)

        msg = f"{self.user.username} has disconnected."
        await self.group_send_chat_message(username="system", message=msg)
        n_online_msg = self.create_n_online_message(self.scope["room_state"]["n_online"])

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_user_disconnected", "n_online": n_online_msg},
        )

    async def send_user_disconnected(self, event):
        n_online = event["n_online"]
        await self.send(
            text_data=json.dumps({"n_online": n_online}, ensure_ascii=False),
        )
