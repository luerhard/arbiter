import json

from django.contrib.messages import get_messages
from django.utils.deprecation import MiddlewareMixin


class HtmxMessageMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if "HX-Request" not in request.headers:
            return response

        # When the response asks htmx for a full page refresh or a redirect, it
        # loads a new page and discards any HX-Trigger events. Leave the messages
        # unconsumed so they survive in storage and render server-side there.
        if response.headers.get("HX-Refresh") == "true" or "HX-Redirect" in response.headers:
            return response

        messages = [
            {"message": message.message, "tags": message.tags} for message in get_messages(request)
        ]
        if not messages:
            return response

        existing_triggers_raw = response.headers.get("HX-Trigger")
        if existing_triggers_raw:
            try:
                triggers = json.loads(existing_triggers_raw)
                if not isinstance(triggers, dict):
                    triggers = {}
            except json.JSONDecodeError:
                triggers = {
                    key.strip(): True for key in existing_triggers_raw.split(",") if key.strip()
                }
        else:
            triggers = {}

        existing_messages = triggers.get("messages")
        if isinstance(existing_messages, list):
            existing_messages.extend(messages)
        else:
            triggers["messages"] = messages

        response.headers["HX-Trigger"] = json.dumps(triggers)

        return response
