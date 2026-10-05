from collections import defaultdict
import uuid

from django.contrib.auth import get_user_model
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
from projects.models.batch import BatchUser

User = get_user_model()


def _finalize(batch, *users):
    BatchUser.objects.filter(batch=batch, user__in=users).update(finalized_at=timezone.now())


def _create_project_with_batch():
    suffix = uuid.uuid4().hex[:8]
    annotator1 = User.objects.create_user(username=f"ann1_{suffix}", password="123")
    annotator2 = User.objects.create_user(username=f"ann2_{suffix}", password="123")
    expert = User.objects.create_user(username=f"exp1_{suffix}", password="123")

    project = Project.objects.create(
        name=f"Project {suffix}",
        description="Test project",
        owner=expert,
    )
    ProjectUser.objects.create(
        project=project,
        user=annotator1,
        default_role=ProjectRole.ANNOTATOR,
    )
    ProjectUser.objects.create(
        project=project,
        user=annotator2,
        default_role=ProjectRole.ANNOTATOR,
    )
    ProjectUser.objects.create(
        project=project,
        user=expert,
        default_role=ProjectRole.EXPERT,
    )

    label1 = Label.objects.create(project=project, name=f"Label A {suffix}")
    label2 = Label.objects.create(project=project, name=f"Label B {suffix}")

    batch = Batch.objects.create(project=project, current_phase=BatchPhase.ANNOTATION)
    batch.users.add(annotator1, annotator2, through_defaults={"role": ProjectRole.ANNOTATOR})
    batch.users.add(expert, through_defaults={"role": ProjectRole.EXPERT})

    ex1 = Example.objects.create(batch=batch, content="Example 1")
    ex2 = Example.objects.create(batch=batch, content="Example 2")

    batch.set_phase(BatchPhase.ANNOTATION)

    a11 = ExampleAssignment.objects.filter(example=ex1, user=annotator1).get()
    a12 = ExampleAssignment.objects.filter(example=ex1, user=annotator2).get()
    a21 = ExampleAssignment.objects.filter(example=ex2, user=annotator1).get()
    a22 = ExampleAssignment.objects.filter(example=ex2, user=annotator2).get()

    # disagreement on ex1, agreement on ex2
    Annotation.objects.create(assignment=a11, label=label1)
    Annotation.objects.create(assignment=a12, label=label2)
    Annotation.objects.create(assignment=a21, label=label1)
    Annotation.objects.create(assignment=a22, label=label1)

    return {
        "project": project,
        "batch": batch,
        "annotators": [annotator1, annotator2],
        "expert": expert,
        "labels": [label1, label2],
        "examples": [ex1, ex2],
    }


@pytest.mark.django_db
def test_batch_set_phase_annotation_creates_assignments():
    data = _create_project_with_batch()
    batch = data["batch"]
    annotator1, annotator2 = data["annotators"]

    ea = ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.ANNOTATION)
    assert ea.count() == 4
    counter = defaultdict(int)
    for assignment in ea:
        counter[assignment.user.id] += 1
    assert counter == {annotator1.id: 2, annotator2.id: 2}


@pytest.mark.django_db
def test_batch_set_phase_discussion_creates_assignments_for_disagreements():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, ex2 = data["examples"]
    annotator1, annotator2 = data["annotators"]

    batch.set_phase(BatchPhase.DISCUSSION)
    disagreements = batch.disagreements(phase=BatchPhase.ANNOTATION).count()
    assert disagreements == 1

    ba = ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.DISCUSSION)
    assert ba.count() == 2
    users = {a.user for a in ba}
    assert users == {annotator1, annotator2}

    ea = ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.DISCUSSION)
    assert ea.count() == 2
    counter = defaultdict(int)
    for assignment in ea:
        counter[assignment.user.id] += 1
    assert counter == {annotator1.id: 1, annotator2.id: 1}

    discussion_ex1 = ExampleAssignment.objects.filter(example=ex1, phase=BatchPhase.DISCUSSION)
    discussion_ex2 = ExampleAssignment.objects.filter(example=ex2, phase=BatchPhase.DISCUSSION)

    assert discussion_ex1.count() == 2
    assert discussion_ex2.count() == 0


@pytest.mark.django_db
def test_batch_set_phase_expert_creates_assignments_for_discussion_disagreements():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, ex2 = data["examples"]
    label1, label2 = data["labels"]

    assert batch.disagreements(BatchPhase.ANNOTATION).count() == 1
    batch.set_phase(phase=BatchPhase.DISCUSSION)

    # create discussion labels (disagreement on ex1 only)
    disc_ex1 = ExampleAssignment.objects.filter(example=ex1, phase=BatchPhase.DISCUSSION).order_by(
        "id",
    )
    disc_ex2 = ExampleAssignment.objects.filter(example=ex2, phase=BatchPhase.DISCUSSION).order_by(
        "id",
    )

    assert disc_ex1.count() == 2
    assert disc_ex2.count() == 0

    Annotation.objects.create(assignment=disc_ex1[0], label=label1)
    Annotation.objects.create(assignment=disc_ex1[1], label=label2)

    batch.set_phase(BatchPhase.EXPERT)

    expert_assignments = ExampleAssignment.objects.filter(phase=BatchPhase.EXPERT, batch=batch)
    assert expert_assignments.count() == 1
    assert expert_assignments.first().example_id == ex1.id

    # expert batch assignment should exist
    assert ExampleAssignment.objects.filter(
        batch=batch,
        user=data["expert"],
        batch__batchuser__role=ProjectRole.EXPERT,
    ).exists()


@pytest.mark.django_db
def test_all_annotators_finalized():
    data = _create_project_with_batch()
    batch = data["batch"]
    annotator1, annotator2 = data["annotators"]

    assert batch.all_annotators_finalized() is False

    _finalize(batch, annotator1)
    assert batch.all_annotators_finalized() is False

    _finalize(batch, annotator2)
    assert batch.all_annotators_finalized() is True


@pytest.mark.django_db
def test_advance_no_op_when_not_all_finalized():
    data = _create_project_with_batch()
    batch = data["batch"]
    annotator1, _ = data["annotators"]

    _finalize(batch, annotator1)
    assert batch.advance_from_annotation_if_finalized() is None
    assert batch.current_phase == BatchPhase.ANNOTATION


@pytest.mark.django_db
def test_advance_to_discussion_when_disagreements_exist():
    data = _create_project_with_batch()
    batch = data["batch"]
    annotator1, annotator2 = data["annotators"]

    _finalize(batch, annotator1, annotator2)
    result = batch.advance_from_annotation_if_finalized()

    assert result == BatchPhase.DISCUSSION
    assert batch.current_phase == BatchPhase.DISCUSSION


@pytest.mark.django_db
def test_advance_to_final_when_no_disagreements():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1 = data["examples"][0]
    label1 = data["labels"][0]
    annotator1, annotator2 = data["annotators"]

    # remove the only disagreement so both annotators agree on every example
    a12 = ExampleAssignment.objects.get(example=ex1, user=annotator2)
    a12.annotations.all().delete()
    Annotation.objects.create(assignment=a12, label=label1)
    assert batch.disagreements(BatchPhase.ANNOTATION).count() == 0

    _finalize(batch, annotator1, annotator2)
    result = batch.advance_from_annotation_if_finalized()

    assert result == BatchPhase.FINAL
    assert batch.current_phase == BatchPhase.FINAL


@pytest.mark.django_db
def test_advance_no_op_when_not_in_annotation_phase():
    data = _create_project_with_batch()
    batch = data["batch"]
    annotator1, annotator2 = data["annotators"]
    batch.current_phase = BatchPhase.DISCUSSION
    batch.save()

    _finalize(batch, annotator1, annotator2)
    assert batch.advance_from_annotation_if_finalized() is None
    assert batch.current_phase == BatchPhase.DISCUSSION


def _add_setup_batch(project, with_examples=True):
    batch = Batch.objects.create(project=project, current_phase=BatchPhase.SETUP)
    for user in project.users.all():
        role = (
            ProjectRole.ANNOTATOR
            if ProjectUser.objects.get(project=project, user=user).default_role
            == ProjectRole.ANNOTATOR
            else ProjectRole.EXPERT
        )
        batch.users.add(user, through_defaults={"role": role})
    if with_examples:
        Example.objects.create(batch=batch, content="Next batch example")
    return batch


def _resolve_all_disagreements(data):
    """Make both annotators agree on every example (annotation phase)."""
    ex1 = data["examples"][0]
    label1 = data["labels"][0]
    a12 = ExampleAssignment.objects.get(example=ex1, user=data["annotators"][1])
    a12.annotations.all().delete()
    Annotation.objects.create(assignment=a12, label=label1)


@pytest.mark.django_db
def test_finalize_without_disagreements_starts_next_setup_batch():
    data = _create_project_with_batch()
    batch = data["batch"]
    next_batch = _add_setup_batch(data["project"])

    _resolve_all_disagreements(data)
    _finalize(batch, *data["annotators"])
    result = batch.advance_from_annotation_if_finalized()

    assert result == BatchPhase.FINAL
    next_batch.refresh_from_db()
    assert next_batch.current_phase == BatchPhase.ANNOTATION
    # Starting the next batch must create its annotation assignments.
    assert ExampleAssignment.objects.filter(
        batch=next_batch,
        phase=BatchPhase.ANNOTATION,
    ).exists()


@pytest.mark.django_db
def test_finalize_without_next_setup_batch_is_harmless():
    data = _create_project_with_batch()
    batch = data["batch"]

    _resolve_all_disagreements(data)
    _finalize(batch, *data["annotators"])
    result = batch.advance_from_annotation_if_finalized()

    assert result == BatchPhase.FINAL
    assert batch.start_next_setup_batch() is None


@pytest.mark.django_db
def test_setup_batch_with_smaller_number_is_never_started():
    # A skipped batch (still in SETUP but numbered before the finalizing
    # batch) must not be resurrected; only later batches are auto-started.
    data = _create_project_with_batch()
    batch = data["batch"]
    skipped = _add_setup_batch(data["project"])
    Batch.objects.filter(pk=skipped.pk).update(batch_number=batch.batch_number - 1)

    _resolve_all_disagreements(data)
    _finalize(batch, *data["annotators"])
    result = batch.advance_from_annotation_if_finalized()

    assert result == BatchPhase.FINAL
    skipped.refresh_from_db()
    assert skipped.current_phase == BatchPhase.SETUP
    assert batch.start_next_setup_batch() is None


@pytest.mark.django_db
def test_setup_batch_without_examples_is_not_started():
    data = _create_project_with_batch()
    batch = data["batch"]
    empty_batch = _add_setup_batch(data["project"], with_examples=False)

    _resolve_all_disagreements(data)
    _finalize(batch, *data["annotators"])
    batch.advance_from_annotation_if_finalized()

    empty_batch.refresh_from_db()
    assert empty_batch.current_phase == BatchPhase.SETUP


@pytest.mark.django_db
def test_advance_from_discussion_to_expert_when_disagreements_remain():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1 = data["examples"][0]
    label1, label2 = data["labels"]

    batch.set_phase(BatchPhase.DISCUSSION)
    disc = ExampleAssignment.objects.filter(example=ex1, phase=BatchPhase.DISCUSSION).order_by(
        "id",
    )
    # still disagreeing after discussion
    Annotation.objects.create(assignment=disc[0], label=label1)
    Annotation.objects.create(assignment=disc[1], label=label2)

    result = batch.advance_from_discussion()

    assert result == BatchPhase.EXPERT
    assert batch.current_phase == BatchPhase.EXPERT
    assert ExampleAssignment.objects.filter(
        batch=batch,
        phase=BatchPhase.EXPERT,
        example=ex1,
    ).exists()


@pytest.mark.django_db
def test_advance_from_discussion_to_final_when_resolved_starts_next_batch():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1 = data["examples"][0]
    label1 = data["labels"][0]
    next_batch = _add_setup_batch(data["project"])

    batch.set_phase(BatchPhase.DISCUSSION)
    disc = ExampleAssignment.objects.filter(example=ex1, phase=BatchPhase.DISCUSSION)
    # both annotators agree after discussion -> no expert decisions needed
    for assignment in disc:
        Annotation.objects.create(assignment=assignment, label=label1)

    result = batch.advance_from_discussion()

    assert result == BatchPhase.FINAL
    assert batch.current_phase == BatchPhase.FINAL
    assert not ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.EXPERT).exists()
    next_batch.refresh_from_db()
    assert next_batch.current_phase == BatchPhase.ANNOTATION


@pytest.mark.django_db
def test_advance_from_discussion_no_op_outside_discussion_phase():
    data = _create_project_with_batch()
    batch = data["batch"]

    assert batch.advance_from_discussion() is None
    assert batch.current_phase == BatchPhase.ANNOTATION


@pytest.mark.django_db
def test_project_batch_state_indicators():
    data = _create_project_with_batch()
    project = data["project"]
    batch = data["batch"]

    # fixture batch is in ANNOTATION phase
    assert project.annotator_n_active_batches == 1
    assert project.annotator_any_annotation_batches is True
    assert project.annotator_any_discussion_batches is False

    batch.set_phase(BatchPhase.DISCUSSION)
    assert project.annotator_n_active_batches == 1
    assert project.annotator_any_annotation_batches is False
    assert project.annotator_any_discussion_batches is True

    batch.current_phase = BatchPhase.FINAL
    batch.save()
    assert project.annotator_n_active_batches == 0
    assert project.annotator_any_annotation_batches is False
    assert project.annotator_any_discussion_batches is False


@pytest.mark.django_db
def test_batch_disagreements_for_phase():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, _ = data["examples"]

    disagreements = batch.disagreements(BatchPhase.ANNOTATION)

    assert list(disagreements.values_list("id", flat=True)) == [ex1.id]
