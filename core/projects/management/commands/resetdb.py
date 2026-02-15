from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import OperationalError
from django.db import connection


class Command(BaseCommand):
    help = "Delete all data and re-apply migrations, leaving an empty database."

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
