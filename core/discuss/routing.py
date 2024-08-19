from django.urls import path

from .consumers import ChatConsumer
from .middleware import RoomStateMiddleware

websocket_urlpatterns = [
    path(
        "ws/chat/<int:batch_id>",
        RoomStateMiddleware(ChatConsumer.as_asgi()),
        name="ws-chat-simple",
    ),
]
