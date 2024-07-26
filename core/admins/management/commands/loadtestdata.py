import json
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load test data into database"

    def handle(self, *args, **kwargs):  # noqa: ARG002
        path = Path(settings.BASE_DIR / "../test.json")
        call_command("migrate")
        call_command("loaddata", str(path))
        result = {"message": "Successfully dumped current state of DB"}
        return json.dumps(result)
