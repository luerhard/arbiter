from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import OperationalError
from django.db import connection
from redis.exceptions import RedisError

from discuss import room_state


class Command(BaseCommand):
    help = "Delete all data, including the chat state in Redis, and re-apply migrations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Do not prompt for confirmation.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if not options["noinput"]:
            confirm = input(
                "This will DELETE ALL DATA and re-run migrations. Type 'yes' to continue: ",
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        try:
            connection.ensure_connection()
        except OperationalError as exc:
            msg = "Database connection failed. Is the database created?"
            raise CommandError(msg) from exc

        call_command("flush", interactive=False, verbosity=options["verbosity"])
        call_command("migrate", interactive=False, verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS("Database reset complete."))

        # The chat state in Redis is keyed by batch id, and new batches start at id 1 again:
        # without this, a new batch would inherit the chat of the old batch with the same id.
        try:
            room_state.delete_all_states()
            if layer := get_channel_layer():
                async_to_sync(layer.flush)()
        except RedisError as exc:
            self.stdout.write(
                self.style.WARNING(f"Redis could not be cleared, old chat state remains: {exc}"),
            )
        else:
            self.stdout.write(self.style.SUCCESS("Redis chat state cleared."))
