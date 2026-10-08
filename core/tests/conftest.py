import os
from pathlib import Path
import shutil
import tempfile
import uuid

from django.conf import settings
from django.core.management import call_command
from django.db import connection
import pytest
import redis

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from discuss import room_state
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser
from users.models import User

# The default hasher is deliberately slow (0.15 s per password); tests create and log in
# hundreds of users. Set before populatedb creates its users, so their logins are fast too.
settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def run_sql(sql):
    with connection.cursor() as conn:
        conn.execute(sql)


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):  # noqa: PT004
    # Codebooks are git repositories on disk, stored by codebook id. Keep the
    # test ones in a temporary folder: the test database reuses the ids of the
    # dev database, and creating a codebook wipes an existing folder.
    import core.settings as project_settings

    dev_codebooks_root = project_settings.CODEBOOKS_ROOT
    test_codebooks_root = Path(tempfile.mkdtemp(prefix="arbiter-test-codebooks-"))
    project_settings.CODEBOOKS_ROOT = test_codebooks_root

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

    project_settings.CODEBOOKS_ROOT = dev_codebooks_root
    shutil.rmtree(test_codebooks_root, ignore_errors=True)


@pytest.fixture
def redis_client(monkeypatch, settings):
    """An empty Redis database for the chat state and the channel layer. In docker compose
    (and CI) Redis runs in its own container, which REDIS_HOST names."""
    url = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:6379/15"
    monkeypatch.setattr(room_state, "REDIS_URL", url)
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [url]},
        },
    }
    client = redis.Redis.from_url(url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def project_annotation():
    suffix = uuid.uuid4().hex[:8]
    annotator1 = User.objects.create_user(username=f"user_{suffix}", password="123")
    annotator2 = User.objects.create_user(username=f"user2_{suffix}", password="123")
    expert = User.objects.create_user(username=f"user3_{suffix}", password="123")
    project = Project.objects.create(
        name=f"Project {suffix}",
        description="Test project",
        owner=expert,
    )
    for user in (annotator1, annotator2):
        ProjectUser.objects.create(
            project=project,
            user=user,
            default_role=ProjectRole.ANNOTATOR,
        )
    ProjectUser.objects.create(
        project=project,
        user=expert,
        default_role=ProjectRole.EXPERT,
    )
    label1 = Label.objects.create(project=project, name=f"Label A {suffix}")
    label2 = Label.objects.create(project=project, name=f"Label B {suffix}")
    batch = Batch.objects.create(project=project, current_phase=BatchPhase.SETUP)
    batch.users.add(annotator1, annotator2, through_defaults={"role": ProjectRole.ANNOTATOR})
    batch.users.add(expert, through_defaults={"role": ProjectRole.EXPERT})
    example = Example.objects.create(batch=batch, content="Example")
    batch.set_phase(BatchPhase.ANNOTATION)
    return {
        "annotators": [annotator1, annotator2],
        "expert": expert,
        "project": project,
        "labels": [label1, label2],
        "batch": batch,
        "example": example,
    }


@pytest.fixture
def project_discussion(project_annotation):
    data = project_annotation
    a1, a2 = data["annotators"]
    example = data["example"]
    project = data["project"]
    label1, label2 = data["labels"]
    batch = data["batch"]

    ea_a1 = (
        ExampleAssignment.objects.from_project(project=project)
        .filter(user=a1, example=example, phase=BatchPhase.ANNOTATION)
        .first()
    )
    ea_a1.set_user_annotations(label_ids=[label1.id])
    ea_a2 = (
        ExampleAssignment.objects.from_project(project=project)
        .filter(user=a2, example=example, phase=BatchPhase.ANNOTATION)
        .first()
    )
    ea_a2.set_user_annotations(label_ids=[label1.id, label2.id])
    batch.set_phase(BatchPhase.DISCUSSION)
    return data


@pytest.fixture
def project_expert(project_discussion):
    data = project_discussion
    a1, a2 = data["annotators"]
    example = data["example"]
    project = data["project"]
    label1, label2 = data["labels"]
    batch = data["batch"]

    ea_a1 = (
        ExampleAssignment.objects.from_project(project=project)
        .filter(user=a1, example=example, phase=BatchPhase.DISCUSSION)
        .first()
    )
    ea_a1.set_user_annotations(label_ids=[label1.id])
    ea_a2 = (
        ExampleAssignment.objects.from_project(project=project)
        .filter(user=a2, example=example, phase=BatchPhase.DISCUSSION)
        .first()
    )
    ea_a2.set_user_annotations(label_ids=[label1.id, label2.id])
    batch.set_phase(BatchPhase.EXPERT)
    return data


@pytest.fixture
def get_as(client):
    """GET a page as one of the people of a project fixture: "anonymous", "annotator" (the
    first one), "other annotator", "expert", or "outsider" (logged in, but in no project).
    For the access tables in each app's test_views.py."""

    def get(url, who, project):
        people = {
            "annotator": project["annotators"][0],
            "other annotator": project["annotators"][1],
            "expert": project["expert"],
        }
        if who == "outsider":
            outsider = User.objects.create_user(f"out_{uuid.uuid4().hex[:8]}", password="123")
            client.force_login(outsider)
        elif who != "anonymous":
            client.force_login(people[who])
        response = client.get(url)
        if who == "anonymous" and response.status_code == 302:  # sent to log in, nothing else
            assert response.url.startswith(f"{settings.LOGIN_URL}?next=")
        return response

    return get
