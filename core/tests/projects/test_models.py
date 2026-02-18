from collections import defaultdict
import uuid

from django.contrib.auth import get_user_model
import pytest

from data.models import Example
from data.models.example_assignment import ExampleAssignment
from data.models.models import Annotation
from data.models.models import Label
from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import Project
from projects.models import ProjectUser

User = get_user_model()


def _create_project_with_batch():
    suffix = uuid.uuid4().hex[:8]
    annotator1 = User.objects.create_user(username=f"ann1_{suffix}", password="123")
    annotator2 = User.objects.create_user(username=f"ann2_{suffix}", password="123")
    expert = User.objects.create_user(username=f"exp1_{suffix}", password="123")

    project = Project.objects.create(
        name=f"Project {suffix}",
        description="Test project",
    )
    ProjectUser.objects.create(
        project=project,
        user=annotator1,
        default_role=ProjectUser.Role.ANNOTATOR,
    )
    ProjectUser.objects.create(
        project=project,
        user=annotator2,
        default_role=ProjectUser.Role.ANNOTATOR,
    )
    ProjectUser.objects.create(
        project=project,
        user=expert,
        default_role=ProjectUser.Role.EXPERT,
    )

    label1 = Label.objects.create(project=project, name=f"Label A {suffix}")
    label2 = Label.objects.create(project=project, name=f"Label B {suffix}")

    batch = Batch.objects.create(project=project, current_phase=Batch.Phase.ANNOTATION)

    ex1 = Example.objects.create(batch=batch, content="Example 1")
    ex2 = Example.objects.create(batch=batch, content="Example 2")

    batch.set_phase(
        Batch.Phase.ANNOTATION,
        user_role_mapping={
            annotator1: ProjectUser.Role.ANNOTATOR,
            annotator2: ProjectUser.Role.ANNOTATOR,
        },
    )

    a11 = ExampleAssignment.objects.filter(example=ex1, batch_assignment__user=annotator1).get()
    a12 = ExampleAssignment.objects.filter(example=ex1, batch_assignment__user=annotator2).get()
    a21 = ExampleAssignment.objects.filter(example=ex2, batch_assignment__user=annotator1).get()
    a22 = ExampleAssignment.objects.filter(example=ex2, batch_assignment__user=annotator2).get()

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

    ba = BatchAssignment.objects.filter(batch=batch, phase=Batch.Phase.ANNOTATION)
    assert ba.count() == 2
    users = {a.user for a in ba}
    assert users == {annotator1, annotator2}

    ea = ExampleAssignment.objects.filter(
        batch_assignment__batch=batch,
        batch_assignment__phase=Batch.Phase.ANNOTATION,
    )
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

    batch.set_phase(Batch.Phase.DISCUSSION)
    disagreements = batch.disagreements(phase=Batch.Phase.ANNOTATION).count()
    assert disagreements == 1

    ba = BatchAssignment.objects.filter(batch=batch, phase=Batch.Phase.DISCUSSION)
    assert ba.count() == 2
    users = {a.user for a in ba}
    assert users == {annotator1, annotator2}

    ea = ExampleAssignment.objects.filter(
        batch_assignment__batch=batch,
        batch_assignment__phase=Batch.Phase.DISCUSSION,
    )
    assert ea.count() == 2
    counter = defaultdict(int)
    for assignment in ea:
        counter[assignment.user.id] += 1
    assert counter == {annotator1.id: 1, annotator2.id: 1}

    discussion_ex1 = ExampleAssignment.objects.filter(
        example=ex1,
        batch_assignment__phase=Batch.Phase.DISCUSSION,
    )
    discussion_ex2 = ExampleAssignment.objects.filter(
        example=ex2,
        batch_assignment__phase=Batch.Phase.DISCUSSION,
    )

    assert discussion_ex1.count() == 2
    assert discussion_ex2.count() == 0


@pytest.mark.django_db
def test_batch_set_phase_expert_creates_assignments_for_discussion_disagreements():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, ex2 = data["examples"]
    label1, label2 = data["labels"]

    assert batch.disagreements(Batch.Phase.ANNOTATION).count() == 1
    batch.set_phase(phase=Batch.Phase.DISCUSSION)

    # create discussion labels (disagreement on ex1 only)
    disc_ex1 = ExampleAssignment.objects.filter(
        example=ex1,
        batch_assignment__phase=Batch.Phase.DISCUSSION,
    ).order_by("id")
    disc_ex2 = ExampleAssignment.objects.filter(
        example=ex2,
        batch_assignment__phase=Batch.Phase.DISCUSSION,
    ).order_by("id")

    assert disc_ex1.count() == 2
    assert disc_ex2.count() == 0

    Annotation.objects.create(assignment=disc_ex1[0], label=label1)
    Annotation.objects.create(assignment=disc_ex1[1], label=label2)

    batch.set_phase(Batch.Phase.EXPERT)

    expert_assignments = ExampleAssignment.objects.filter(
        batch_assignment__phase=Batch.Phase.EXPERT,
        example__batch=batch,
    )
    assert expert_assignments.count() == 1
    assert expert_assignments.first().example_id == ex1.id

    # expert batch assignment should exist
    assert BatchAssignment.objects.filter(
        batch=batch,
        user=data["expert"],
        role=ProjectUser.Role.EXPERT,
    ).exists()


@pytest.mark.django_db
def test_batch_assignment_get_disagreements_for_phase():
    data = _create_project_with_batch()
    batch = data["batch"]
    ex1, _ = data["examples"]

    disagreements = batch.disagreements(Batch.Phase.ANNOTATION)

    assert list(disagreements.values_list("id", flat=True)) == [ex1.id]
