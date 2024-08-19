from channels.middleware import BaseMiddleware


class RoomStateMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)
        self.state = {}

    async def __call__(self, scope, receive, send):
        layer_name = scope["url_route"]["kwargs"]["batch_id"]

        # Ensure there's a state dictionary for the layer
        if layer_name not in self.state:
            self.state[layer_name] = {}

        # Add the state to the scope so that it can be accessed in consumers
        scope["room_state"] = self.state[layer_name]

        return await super().__call__(scope, receive, send)
