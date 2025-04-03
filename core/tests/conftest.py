from django.conf import settings
from django.core.management import call_command
import pytest


@pytest.fixture(scope="session")
def populatedb(django_db_setup, django_db_blocker):  # noqa: PT004
    settings.DATABASES["default"]["NAME"] = ":memory:"

    with django_db_blocker.unblock():
        call_command("populatedb")
