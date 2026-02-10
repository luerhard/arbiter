import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
import pytest

from projects.forms import BatchCreateForm
from projects.models import Project
from projects.models import ProjectUser

User = get_user_model()


def _setup_project_users():
    suffix = uuid.uuid4().hex[:8]
    ann1 = User.objects.create_user(username=f"ann1_{suffix}", password="123")
    ann2 = User.objects.create_user(username=f"ann2_{suffix}", password="123")
    exp1 = User.objects.create_user(username=f"exp1_{suffix}", password="123")

    project = Project.objects.create(name=f"Project {suffix}", description="Test project")
    ProjectUser.objects.create(project=project, user=ann1, default_role=ProjectUser.Role.ANNOTATOR)
    ProjectUser.objects.create(project=project, user=ann2, default_role=ProjectUser.Role.ANNOTATOR)
    ProjectUser.objects.create(project=project, user=exp1, default_role=ProjectUser.Role.EXPERT)

    return project, ann1, ann2, exp1


@pytest.mark.django_db
def test_batch_create_form_requires_two_annotators_and_one_expert():
    project, ann1, ann2, exp1 = _setup_project_users()

    upload = SimpleUploadedFile("examples.csv", b"text\nhello\n", content_type="text/csv")

    form = BatchCreateForm(
        data={
            f"role_user_{ann1.id}": ProjectUser.Role.ANNOTATOR,
            f"role_user_{ann2.id}": "",
            f"role_user_{exp1.id}": ProjectUser.Role.EXPERT,
        },
        files={"file": upload},
        project=project,
    )
    assert form.is_valid() is False
    assert form.non_field_errors() == ["Select at least 2 annotators and 1 expert for this batch."]


@pytest.mark.django_db
def test_batch_create_form_requires_at_least_one_expert():
    project, ann1, ann2, exp1 = _setup_project_users()

    upload = SimpleUploadedFile("examples.csv", b"text\nhello\n", content_type="text/csv")

    form = BatchCreateForm(
        data={
            f"role_user_{ann1.id}": ProjectUser.Role.ANNOTATOR,
            f"role_user_{ann2.id}": ProjectUser.Role.ANNOTATOR,
            f"role_user_{exp1.id}": "",
        },
        files={"file": upload},
        project=project,
    )
    assert form.is_valid() is False
    assert form.non_field_errors() == ["Select at least 2 annotators and 1 expert for this batch."]


@pytest.mark.django_db
def test_batch_create_form_valid_with_two_annotators_and_one_expert():
    project, ann1, ann2, exp1 = _setup_project_users()

    upload = SimpleUploadedFile("examples.csv", b"text\nhello\n", content_type="text/csv")

    form = BatchCreateForm(
        data={
            f"role_user_{ann1.id}": ProjectUser.Role.ANNOTATOR,
            f"role_user_{ann2.id}": ProjectUser.Role.ANNOTATOR,
            f"role_user_{exp1.id}": ProjectUser.Role.EXPERT,
        },
        files={"file": upload},
        project=project,
    )
    assert form.is_valid() is True


@pytest.mark.django_db
def test_batch_create_form_allows_changing_roles_for_any_user():
    project, ann1, ann2, exp1 = _setup_project_users()

    upload = SimpleUploadedFile("examples.csv", b"text\nhello\n", content_type="text/csv")

    form = BatchCreateForm(
        data={
            f"role_user_{ann1.id}": ProjectUser.Role.EXPERT,
            f"role_user_{ann2.id}": ProjectUser.Role.ANNOTATOR,
            f"role_user_{exp1.id}": ProjectUser.Role.ANNOTATOR,
        },
        files={"file": upload},
        project=project,
    )
    assert form.is_valid() is True
