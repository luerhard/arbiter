import threading
import time
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
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


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("second", ["same", "other"])
def test_concurrent_saves_of_an_assignment_keep_the_last_one(monkeypatch, second):
    # Two saves of the same assignment at once (double click, two tabs): before, both
    # deleted the old labels and both inserted theirs. With a label in common, the
    # second failed on the unique constraint (a 500, seen in production); with
    # different labels, the labels of both stayed. Now the second waits for the first.
    data = _setup_example_assignment()
    assignment = data["assignment"]
    label1, label2 = data["labels"]
    labels_b = [label1.id] if second == "same" else [label2.id]

    first_inside = threading.Event()
    let_first_finish = threading.Event()
    original_bulk_create = Annotation.objects.bulk_create

    def bulk_create(objs, *args, **kwargs):
        if threading.current_thread().name == "first":
            first_inside.set()
            let_first_finish.wait(timeout=10)
        return original_bulk_create(objs, *args, **kwargs)

    monkeypatch.setattr(Annotation.objects, "bulk_create", bulk_create)
    errors = []

    def save(label_ids):
        try:
            ExampleAssignment.objects.get(pk=assignment.pk).set_user_annotations(label_ids)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        finally:
            connection.close()

    first = threading.Thread(target=save, args=([label1.id],), name="first")
    first.start()
    assert first_inside.wait(timeout=10)
    second_save = threading.Thread(target=save, args=(labels_b,), name="second")
    second_save.start()
    time.sleep(0.5)  # the second save is now waiting for the first, or racing it
    let_first_finish.set()
    first.join(timeout=10)
    second_save.join(timeout=10)

    assert errors == []
    labels = Annotation.objects.filter(assignment=assignment).values_list("label_id", flat=True)
    assert list(labels) == labels_b


@pytest.mark.django_db
def test_example_assignment_previous_next_respects_order_and_bounds():
    data = _setup_example_assignment()
    user = data["user"]
    batch = data["batch"]

    a1 = data["assignment"]

    ex2 = Example.objects.create(batch=batch, content="Example 2")
    ex3 = Example.objects.create(batch=batch, content="Example 3")

    a2 = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=ex2,
        phase=BatchPhase.ANNOTATION,
        order=2,
    )
    a3 = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=ex3,
        phase=BatchPhase.ANNOTATION,
        order=3,
    )

    assert a1.previous() is None
    assert a1.next().id == a2.id
    assert a2.previous().id == a1.id
    assert a2.next().id == a3.id
    assert a3.previous().id == a2.id
    assert a3.next() is None


@pytest.mark.django_db
def test_example_assignment_previous_next_skip_annotated_skips_done_assignments():
    data = _setup_example_assignment()
    user = data["user"]
    batch = data["batch"]

    a1 = data["assignment"]
    ex2 = Example.objects.create(batch=batch, content="Example 2")
    ex3 = Example.objects.create(batch=batch, content="Example 3")

    a2 = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=ex2,
        phase=BatchPhase.ANNOTATION,
        order=2,
    )
    a3 = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=ex3,
        phase=BatchPhase.ANNOTATION,
        order=3,
    )

    a2.done = timezone.now()
    a2.save(update_fields=["done"])

    assert a3.previous().id == a2.id
    assert a3.previous(skip_annotated=True).id == a1.id
    assert a1.next(skip_annotated=True).id == a3.id


@pytest.mark.django_db
def test_example_assignment_save_without_order_appends_to_user_queue():
    data = _setup_example_assignment()
    batch, user = data["batch"], data["user"]
    example2 = Example.objects.create(batch=batch, content="Example 2")
    example3 = Example.objects.create(batch=batch, content="Example 3")

    appended = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=example2,
        phase=BatchPhase.ANNOTATION,
    )
    other_phase = ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=example3,
        phase=BatchPhase.DISCUSSION,
    )

    assert appended.order == data["assignment"].order + 1
    assert other_phase.order == 1
    assert "id: " in str(appended)
