from django.conf import settings
from django.core.management import call_command
from django.db import connection
import pytest


def run_sql(sql):
    with connection.cursor() as conn:
        conn.execute(sql)


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):  # noqa: PT004

    settings.DATABASES["default"]["NAME"] = "postgres"
    connection.close()

    with django_db_blocker.unblock():
        run_sql("DROP DATABASE IF EXISTS test_annotationtool")
        run_sql("CREATE DATABASE test_annotationtool")

    connection.close()

    settings.DATABASES["default"]["NAME"] = "test_annotationtool"

    with django_db_blocker.unblock():
        call_command("migrate")
        call_command("populatedb")

    yield

    connection.close()
    settings.DATABASES["default"]["NAME"] = "postgres"
    with django_db_blocker.unblock():
        run_sql("DROP DATABASE test_annotationtool")
