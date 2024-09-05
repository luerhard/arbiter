import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.paginator import Paginator

from .models import Message
from .models import Room
from annotation.models import Batch
from annotation.models import Sentence


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.route = self.scope["url_route"]
        self.batch_id = self.scope["url_route"]["kwargs"]["batch_id"]
        self.room_group_name = f"chat_{self.batch_id}"
        self.user = self.scope["user"]

        # SET UP N ONLINE COUNT
        if f"{self.user}_done" not in self.scope["room_state"]:
            self.scope["room_state"][f"{self.user}_done"] = 0
        if "n_online" not in self.scope["room_state"]:
            self.scope["room_state"]["n_online"] = 0

        # SET UP SYNCED SENTENCES
        if "sentence" not in self.scope["room_state"]:
            self.scope["room_state"]["sentence_page"] = 1
            await self.next_sentence()

        # SET UP SYNCED BUTTONS
        if "clicked_done" not in self.scope["room_state"]:
            self.scope["room_state"]["clicked_done"] = {self.user.username: 0}
        elif self.user.username not in self.scope["room_state"]["clicked_done"]:
            self.scope["room_state"]["clicked_done"][self.user.username] = 0

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.group_send_user_connected()
        await self.accept()

    # GENERAL
    async def disconnect(self, close_code):  # noqa: ARG002
        await self.group_send_user_disconnected()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        print(f"RECEIVED DATA: {data}")

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
            await self.group_send_update_ui()

        # other case: not implemented yet

    # SENTENCE UI

    @database_sync_to_async
    def next_sentence(self):
        if "sentence_page" not in self.scope["room_state"]:
            self.scope["room_state"]["sentence_page"] = 1
        else:
            self.scope["room_state"]["sentence_page"] += 1

        queryset = Sentence.objects.filter(batch=self.batch_id, has_disagreement_labels=True).all()
        paginator = Paginator(queryset, 1)
        page = paginator.get_page(self.scope["room_state"]["sentence_page"])
        if page.object_list:
            sentence = page.object_list[0]
        else:
            sentence = Sentence(id=None, text="Done")
        return sentence

    @staticmethod
    def sentence_html(sentence):
        msg = f"<div id='current-sentence' hx-swap-oob='true'>{sentence.content}</div>"
        return msg

    @staticmethod
    def update_button(self, button):
        pass

    async def group_send_update_ui(self):
        self.scope["room_state"]["clicked_done"][self.user.username] = 1
        print(f"CURRENT DONE STATE: {self.scope['room_state']['clicked_done']}")
        if not all(x == 1 for x in self.scope["room_state"]["clicked_done"].values()):
            # TODO: maybe UPDATE UI of other users to show that this user has clicked done.
            return

        try:
            next_sentence = await self.next_sentence()
        except StopIteration:
            next_sentence = "ALL DONE."
        msg = self.sentence_html(next_sentence)

        # store message in db
        chat_msg = "Showing next sentence."
        await self.save_message_to_db(username="system", message=chat_msg)
        # send to all users
        await self.group_send_chat_message(username="system", message=chat_msg)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_update_ui", "sentence": msg},
        )

        # reset clicked_done
        clicked_done = self.scope["room_state"]["clicked_done"]
        for key in clicked_done:
            clicked_done[key] = 0

    async def send_update_ui(self, event):
        sentence = event["sentence"]
        print("sending", sentence)
        await self.send(text_data=json.dumps({"sentence": sentence}, ensure_ascii=False))

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
        Message.objects.create(room=room, user=username, message=message)
        return None

    # ONLINE STATUS
    @database_sync_to_async
    def update_n_online(self, change):
        room = self.get_or_create_room()
        room.n_online += change
        if room.n_online < 0:
            room.n_online = 0
        room.save()
        return room.n_online

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
