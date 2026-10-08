from collections import defaultdict
import json
import uuid

from django.contrib.auth import get_user_model
from django.utils import timezone
from expert.models import CodebookDraft
import pytest

from data.models import Example
from data.models.example_assignment import ExampleAssignment
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
    a11.set_user_annotations([label1.id])
    a12.set_user_annotations([label2.id])
    a21.set_user_annotations([label1.id])
    a22.set_user_annotations([label1.id])

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

    disc_ex1[0].set_user_annotations([label1.id])
    disc_ex1[1].set_user_annotations([label2.id])

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
    a12.set_user_annotations([label1.id])
    assert batch.disagreements(BatchPhase.ANNOTATION).count() == 0

    _finalize(batch, annotator1, annotator2)
    result = batch.advance_from_annotation_if_finalized()

    assert result == BatchPhase.FINAL
    assert batch.current_phase == BatchPhase.FINAL
    # the project has no batch waiting in SETUP: there is nothing to start
    assert batch.start_next_setup_batch() is None


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
    a12.set_user_annotations([label1.id])


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
    disc[0].set_user_annotations([label1.id])
    disc[1].set_user_annotations([label2.id])

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
        assignment.set_user_annotations([label1.id])

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
def test_moving_on_by_hand_discusses_what_an_annotator_has_not_labeled():
    """The expert moves the batch on while annotator2 has not labeled example 3, which
    annotator1 saved without labels: that must not count as both choosing no labels."""
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, ex2 = data["examples"]
    annotator1, annotator2 = data["annotators"]
    ex3 = Example.objects.create(batch=batch, content="Example 3")
    batch.set_phase(BatchPhase.ANNOTATION)  # hands out example 3
    _assignment(batch, ex3, annotator1, BatchPhase.ANNOTATION).set_user_annotations([])

    batch.set_phase(BatchPhase.DISCUSSION)

    assert set(batch.discussion_examples()) == {ex1, ex3}
    assert set(batch.disagreements(BatchPhase.ANNOTATION)) == {ex1, ex3}


@pytest.mark.django_db
@pytest.mark.parametrize("saved_by", [(), (0,)], ids=["nobody-saved", "one-saved"])
def test_moving_to_expert_by_hand_sends_undiscussed_examples_to_the_expert(saved_by):
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, _ = data["examples"]
    label1, _ = data["labels"]
    batch.set_phase(BatchPhase.DISCUSSION)
    for index in saved_by:
        annotator = data["annotators"][index]
        _assignment(batch, ex1, annotator, BatchPhase.DISCUSSION).set_user_annotations([label1.id])

    batch.set_phase(BatchPhase.EXPERT)

    assert ExampleAssignment.objects.filter(
        batch=batch,
        phase=BatchPhase.EXPERT,
        example=ex1,
        user=data["expert"],
    ).exists()


@pytest.mark.django_db
def test_batch_disagreements_for_phase():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, _ = data["examples"]

    disagreements = batch.disagreements(BatchPhase.ANNOTATION)

    assert list(disagreements.values_list("id", flat=True)) == [ex1.id]


def _assignment(batch, example, user, phase):
    return ExampleAssignment.objects.get(batch=batch, example=example, user=user, phase=phase)


def _labels(assignment):
    return sorted(assignment.annotations.values_list("label_id", flat=True))


@pytest.fixture
def batch_moved_back_to_annotation(project_annotation):
    """Three examples: 1 and 2 disagreed, 3 agreed. Both annotators finalized, example
    1 was decided in the discussion, then the batch was moved back to annotation."""
    data = project_annotation
    batch, (a1, a2), (l1, l2) = data["batch"], data["annotators"], data["labels"]
    ex1 = data["example"]
    ex2 = Example.objects.create(batch=batch, content="Example 2")
    ex3 = Example.objects.create(batch=batch, content="Example 3")
    batch.set_phase(BatchPhase.ANNOTATION)  # assignments for the new examples
    for example, labels1, labels2 in (
        (ex1, [l1.id], [l2.id]),
        (ex2, [l1.id], [l2.id]),
        (ex3, [l1.id], [l1.id]),
    ):
        _assignment(batch, example, a1, BatchPhase.ANNOTATION).set_user_annotations(labels1)
        _assignment(batch, example, a2, BatchPhase.ANNOTATION).set_user_annotations(labels2)
    _finalize(batch, a1, a2)
    batch.set_phase(BatchPhase.DISCUSSION)
    for user in (a1, a2):
        _assignment(batch, ex1, user, BatchPhase.DISCUSSION).set_user_annotations([l1.id])
    annotations_before = {
        a.pk: (a.done, _labels(a))
        for a in ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.ANNOTATION)
    }
    batch.set_phase(BatchPhase.ANNOTATION)
    return {**data, "examples": [ex1, ex2, ex3], "annotations_before": annotations_before}


@pytest.mark.django_db
def test_moving_back_to_annotation_clears_finalize_but_keeps_labels(batch_moved_back_to_annotation):
    # Before, everyone stayed finalized: nobody could change a label, and as only
    # finalizing advances the batch, it was stuck in the annotation phase.
    data = batch_moved_back_to_annotation
    batch = data["batch"]

    assert not batch.all_annotators_finalized()
    for user in data["annotators"]:
        assert BatchUser.objects.get(batch=batch, user=user).finalized_at is None
    annotations_after = {
        a.pk: (a.done, _labels(a))
        for a in ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.ANNOTATION)
    }
    assert annotations_after == data["annotations_before"]


@pytest.mark.django_db
def test_entering_discussion_again_keeps_decisions_and_syncs_open_examples(
    batch_moved_back_to_annotation,
    redis_client,
    django_capture_on_commit_callbacks,
):
    data = batch_moved_back_to_annotation
    batch, (a1, a2), (l1, l2) = data["batch"], data["annotators"], data["labels"]
    ex1, ex2, ex3 = data["examples"]
    # the earlier discussion had ended: that room state must not survive
    redis_client.set(f"room:{batch.id}", json.dumps({"discussion_ended": "DISCUSSION_END"}))
    # the annotators changed their minds: 2 is agreed now, 3 disagreed
    _assignment(batch, ex2, a2, BatchPhase.ANNOTATION).set_user_annotations([l1.id])
    _assignment(batch, ex3, a2, BatchPhase.ANNOTATION).set_user_annotations([l2.id])

    with django_capture_on_commit_callbacks(execute=True):
        batch.set_phase(BatchPhase.DISCUSSION)

    assert list(batch.discussion_examples().order_by("id")) == [ex1, ex3]
    for user in (a1, a2):  # the decision on example 1 stays, it is not discussed again
        decided = _assignment(batch, ex1, user, BatchPhase.DISCUSSION)
        assert decided.done is not None
        assert _labels(decided) == [l1.id]
    assert list(batch.open_discussion_examples()) == [ex3]
    assert redis_client.get(f"room:{batch.id}") is None


@pytest.mark.django_db
@pytest.mark.parametrize("draft", [False, True])
def test_entering_expert_phase_again_removes_only_untouched_stale_assignments(
    project_expert,
    draft,
):
    data = project_expert
    batch, (a1, a2), (l1, _l2) = data["batch"], data["annotators"], data["labels"]
    example, expert = data["example"], data["expert"]
    stale = _assignment(batch, example, expert, BatchPhase.EXPERT)
    if draft:
        CodebookDraft.objects.create(assignment=stale, content="edited", base_revision="x")
    # moved back to the discussion, where the pair now agrees
    batch.set_phase(BatchPhase.DISCUSSION)
    _assignment(batch, example, a2, BatchPhase.DISCUSSION).set_user_annotations([l1.id])

    batch.set_phase(BatchPhase.EXPERT)

    still_there = ExampleAssignment.objects.filter(pk=stale.pk).exists()
    assert still_there == draft  # an expert's codebook draft is never deleted
    assert _labels(_assignment(batch, example, a1, BatchPhase.DISCUSSION)) == [l1.id]
