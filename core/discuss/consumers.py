import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Message
from .models import Room


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.route = self.scope["url_route"]
        self.room_name = self.scope["url_route"]["kwargs"]["batch_id"]
        self.room_group_name = f"chat_{self.room_name}"
        self.user = self.scope["user"]
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.increment_user_online()
        await self.accept()

    async def disconnect(self, close_code):  # noqa: ARG002
        await self.decrement_user_online()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        # if chat message is sent
        if "message" in data.keys():
            message = data["message"]
            username = self.user.username

            # store message in db
            await self.save_message_to_db(username=username, message=message)

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": message, "username": username},
            )
        # other case: not implemented yet
        elif "test" in data.keys():
            self.message_count += 1
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "test_count", "n": self.message_count},
            )

    async def chat_message(self, event):
        message = event["message"]
        username = event["username"]

        if self.user.username == username:
            chat_message = self.create_chat_message(message, msg_type="self-message")
        else:
            chat_message = self.create_chat_message(message, msg_type="other-message")

        await self.send(text_data=json.dumps({"message": chat_message}, ensure_ascii=False))

    def get_or_create_room(self):
        room, _ = Room.objects.get_or_create(pk=self.room_name)
        return room

    @database_sync_to_async
    def update_n_online(self, change):
        room = self.get_or_create_room()
        room.n_online += change
        if room.n_online < 0:
            room.n_online = 0
        room.save()
        return room.n_online

    @database_sync_to_async
    def save_message_to_db(self, username, message):
        room = self.get_or_create_room()
        Message.objects.create(room=room, user=username, message=message)
        return None

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

    @staticmethod
    def create_n_online_message(n_online):
        msg = f"<div id='n-online-status' hx-swap-oob='true'> {n_online}</div>"
        return msg

    async def increment_user_online(self):
        n_online = await self.update_n_online(1)

        msg = f"{self.user.username} is now connected."
        await self.save_message_to_db(username="system", message=msg)

        chat_message = self.create_chat_message(msg, msg_type="system-message")
        n_online_msg = self.create_n_online_message(n_online)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "user_connected", "message": chat_message, "n_online": n_online_msg},
        )

    async def user_connected(self, event):
        msg = event["message"]
        n_online = event["n_online"]
        await self.send(
            text_data=json.dumps({"message": msg, "n_online": n_online}, ensure_ascii=False),
        )

    async def decrement_user_online(self):
        n_online = await self.update_n_online(-1)

        msg = f"{self.user.username} has disconnected."
        chat_message = self.create_chat_message(msg, msg_type="system-message")
        await self.save_message_to_db(username="system", message=msg)
        n_online_msg = self.create_n_online_message(n_online)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "user_disconnected", "message": chat_message, "n_online": n_online_msg},
        )

    async def user_disconnected(self, event):
        msg = event["message"]
        n_online = event["n_online"]
        await self.send(
            text_data=json.dumps({"message": msg, "n_online": n_online}, ensure_ascii=False),
        )
