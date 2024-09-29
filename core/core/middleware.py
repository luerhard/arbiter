import json

from django.contrib.messages import get_messages
from django.utils.deprecation import MiddlewareMixin


class HtmxMessageMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if "HX-Request" in request.headers:
            response.headers["HX-Trigger"] = json.dumps(
                {
                    "messages": [
                        {"message": message.message, "tags": message.tags}
                        for message in get_messages(request)
                    ],
                },
            )

        return response
