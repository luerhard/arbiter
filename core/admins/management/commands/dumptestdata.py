import json
from pathlib import Path
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export current state of DB as testdata"

    def handle(self, *args, **kwargs):  # noqa: ARG002
        sysout = sys.stdout
        path = Path(settings.BASE_DIR / "../tests/test.json")
        with path.open("w") as f:
            sys.stdout = f
            call_command(
                "dumpdata",
                "--natural-foreign",
                "--exclude=contenttypes",
                "--exclude=auth.permission",
                "--indent=2",
            )

        sys.stdout = sysout
        result = {"message": "Successfully dumped current state of DB"}
        return json.dumps(result)
