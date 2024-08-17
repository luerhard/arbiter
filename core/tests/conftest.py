from django.core.management import call_command
import pytest


@pytest.fixture(scope="class")
def django_db_setup(django_db_setup, django_db_blocker):  # noqa: PT004
    print("LOADED FIXTURE")
    with django_db_blocker.unblock():
        call_command("loaddata", "tests/fixtures/fixture.json")
