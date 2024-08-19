import json

from channels.generic.websocket import AsyncWebsocketConsumer


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.route = self.scope["url_route"]
        self.room_name = self.scope["url_route"]["kwargs"]["batch_id"]
        self.room_group_name = f"chat_{self.room_name}"
        self.user = self.scope["user"]

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):  # noqa: ARG002
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        username = self.user.username

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "username": username},
        )

    async def chat_message(self, event):
        message = event["message"]
        username = event["username"]

        if self.user.username == username:
            # if self-message
            div_class = "self-message"
            container_class = "d-flex flex-row-reverse"
        else:
            div_class = "other-message"
            container_class = "d-flex flex-row"

        message_html = (
            f"<div class='{container_class}'><div class='message {div_class}'>{message}</div></div>"
        )
        composed_message = f"<div hx-swap-oob='beforeend:#messages'>{message_html}</div>"

        # print(message_html)
        await self.send(
            text_data=json.dumps(
                {"message": composed_message, "username": username},
                ensure_ascii=False,
            ),
        )
