import uuid

from django.contrib.auth import get_user_model
import pytest

from data.models import Example
from data.models.example_assignment import ExampleAssignment
from data.models.models import Annotation
from data.models.models import Label
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser

User = get_user_model()


def _setup_example_assignment():
    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create_user(username=f"user_{suffix}", password="123")
    project = Project.objects.create(
        name=f"Project {suffix}",
        description="Test project",
        owner=user,
    )
    ProjectUser.objects.create(
        project=project,
        user=user,
        default_role=ProjectRole.ANNOTATOR,
    )
    label1 = Label.objects.create(project=project, name=f"Label A {suffix}")
    label2 = Label.objects.create(project=project, name=f"Label B {suffix}")
    batch = Batch.objects.create(project=project, current_phase=BatchPhase.ANNOTATION)
    batch.users.add(user, through_defaults={"role": ProjectRole.ANNOTATOR})
    example = Example.objects.create(batch=batch, content="Example")
    assignment = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=example,
        phase=BatchPhase.ANNOTATION,
        order=1,
    )
    return {
        "user": user,
        "project": project,
        "labels": [label1, label2],
        "batch": batch,
        "example": example,
        "assignment": assignment,
    }


@pytest.mark.django_db
def test_example_assignment_set_user_annotations_creates_and_marks_done():
    data = _setup_example_assignment()
    assignment = data["assignment"]
    label1, _label2 = data["labels"]

    assignment.set_user_annotations([label1.id])

    assignment.refresh_from_db()
    annotations = Annotation.objects.filter(assignment=assignment)
    assert annotations.count() == 1
    assert annotations.first().label_id == label1.id
    assert assignment.done is not None


@pytest.mark.django_db
def test_example_assignment_set_user_annotations_replaces_labels_only():
    data = _setup_example_assignment()
    assignment = data["assignment"]
    label1, label2 = data["labels"]

    assignment.set_user_annotations([label1.id])
    assignment.set_user_annotations([label2.id])

    assignment.refresh_from_db()
    labels = list(
        Annotation.objects.filter(assignment=assignment).values_list("label_id", flat=True),
    )
    assert labels == [label2.id]
    assert assignment.phase == BatchPhase.ANNOTATION
    assert assignment.done is not None


@pytest.mark.django_db
def test_example_set_user_annotations_uses_user_assignment():
    data = _setup_example_assignment()
    example = data["example"]
    user = data["user"]
    label1, _label2 = data["labels"]
    assignment = data["assignment"]

    assignment.set_user_annotations(label_ids=[label1.id])

    annotations = Annotation.objects.filter(assignment=assignment)
    assert annotations.count() == 1
    assert annotations.first().label_id == label1.id
    assignment.refresh_from_db()
    assert assignment.done is not None


@pytest.mark.django_db
def test_example_set_user_annotations_with_phase_updates_discussion_assignment():
    data = _setup_example_assignment()
    example = data["example"]
    user = data["user"]
    label1, _label2 = data["labels"]
    batch = data["batch"]

    # Create a discussion assignment, then update annotations through Example API.
    discussion_assignment = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=example,
        phase=BatchPhase.DISCUSSION,
        order=2,
    )

    example.set_user_annotations(user=user, label_ids=[label1.id], phase="DISCUSSION")

    discussion_assignment.refresh_from_db()
    annotations = Annotation.objects.filter(assignment=discussion_assignment)
    assert annotations.count() == 1
    assert annotations.first().label_id == label1.id
    assert discussion_assignment.done is not None
