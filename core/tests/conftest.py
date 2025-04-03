from django.core.management import call_command
import pytest


@pytest.fixture(scope="class")
def populatedb(django_db_setup, django_db_blocker):  # noqa: PT004
    with django_db_blocker.unblock():
        call_command("flush", "--noinput")
        call_command("populatedb")
