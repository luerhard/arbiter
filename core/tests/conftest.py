import uuid

from django.conf import settings
from django.core.management import call_command
from django.db import connection
import pytest

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import Project
from projects.models import ProjectUser
from users.models import User


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


@pytest.fixture
def project_annotation():
    suffix = uuid.uuid4().hex[:8]
    annotator1 = User.objects.create_user(username=f"user_{suffix}", password="123")
    annotator2 = User.objects.create_user(username=f"user2_{suffix}", password="123")
    expert = User.objects.create_user(username=f"user3_{suffix}", password="123")
    project = Project.objects.create(name=f"Project {suffix}", description="Test project")
    for user in (annotator1, annotator2):
        ProjectUser.objects.create(
            project=project,
            user=user,
            default_role=ProjectUser.Role.ANNOTATOR,
        )
    ProjectUser.objects.create(
        project=project,
        user=expert,
        default_role=ProjectUser.Role.EXPERT,
    )
    label1 = Label.objects.create(project=project, name=f"Label A {suffix}")
    label2 = Label.objects.create(project=project, name=f"Label B {suffix}")
    batch = Batch.objects.create(project=project, current_phase=Batch.Phase.SETUP)
    example = Example.objects.create(batch=batch, content="Example")
    batch.set_phase(Batch.Phase.ANNOTATION)
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
        ExampleAssignment.objects
        .from_project(project=project)
        .filter(
            batch_assignment__user=a1,
            example=example,
            batch_assignment__phase=Batch.Phase.ANNOTATION,
        )
        .first()
    )
    ea_a1.set_user_annotations(label_ids=[label1.id])
    ea_a2 = (
        ExampleAssignment.objects
        .from_project(project=project)
        .filter(
            batch_assignment__user=a2,
            example=example,
            batch_assignment__phase=Batch.Phase.ANNOTATION,
        )
        .first()
    )
    ea_a2.set_user_annotations(label_ids=[label1.id, label2.id])
    batch.set_phase(Batch.Phase.DISCUSSION)
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
        ExampleAssignment.objects
        .from_project(project=project)
        .filter(
            batch_assignment__user=a1,
            example=example,
            batch_assignment__phase=Batch.Phase.DISCUSSION,
        )
        .first()
    )
    ea_a1.set_user_annotations(label_ids=[label1.id])
    ea_a2 = (
        ExampleAssignment.objects
        .from_project(project=project)
        .filter(
            batch_assignment__user=a2,
            example=example,
            batch_assignment__phase=Batch.Phase.DISCUSSION,
        )
        .first()
    )
    ea_a2.set_user_annotations(label_ids=[label1.id, label2.id])
    batch.set_phase(Batch.Phase.EXPERT)
    return data
