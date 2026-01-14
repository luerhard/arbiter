import random

from codebook.models import Codebook
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import pandas as pd

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser


def uniform_choices(elementary_events: list):
    """Makes a uniform choice over the power set of `elementary_space` (event_space)
    by using a Poisson process modelled as a stream of bits."""
    events = []
    for event in elementary_events:
        if random.getrandbits(1):
            events.append(event)
    return events


def create_batch(project):
    batch = Batch.objects.create(
        project=project,
        phase=Batch.Phase.ANNOTATION,
    )
    test_df = pd.read_csv(settings.BASE_DIR / "core/tests/testdata/examples.csv")

    for i, row in test_df.iterrows():
        ex = Example.objects.create(batch=batch, content=row["text"])
        for user in project.annotators:
            ExampleAssignment.objects.create(example=ex, user=user, order=i)

    batch.set_phase(Batch.Phase.ANNOTATION)
    return batch


def create_project(name, description, labels, annotators, experts):
    project = Project.objects.create(
        name=name,
        description=description,
    )

    for u in annotators:
        ProjectUser.objects.create(project=project, user=u, role=ProjectUser.Role.ANNOTATOR)

    for u in experts:
        ProjectUser.objects.create(project=project, user=u, role=ProjectUser.Role.EXPERT)

    for i, label in enumerate(labels, 1):
        Label.objects.create(project=project, name=label, hotkey=str(i))

    return project


class Command(BaseCommand):
    help = "Load test data into database"

    def handle(self, *args, **kwargs):  # noqa: ARG002
        User = get_user_model()  # noqa: N806

        # create users
        admin = User.objects.create_superuser("admin", password="123")
        annotator1 = User.objects.create_user("annotator1", password="123")
        annotator2 = User.objects.create_user("annotator2", password="123")
        expert1 = User.objects.create_user("expert1", password="123")
        expert2 = User.objects.create_user("expert2", password="123")

        annotators = [annotator1, annotator2]
        experts = [expert1, expert2]

        # Populism Project
        project = create_project(
            "Populism",
            "A project about populism detection. Has a very long codebook.",
            ["Anti-Elitism", "People-Centrism"],
            annotators,
            experts,
        )
        codebook = Codebook.objects.get(project=project)
        codebook_content = (
            settings.BASE_DIR / "core/tests/testdata/codebook_populism_long_v1.md"
        ).read_text()
        codebook.save(content=codebook_content)

        batch = create_batch(project)
        label_ids = [label.id for label in project.labels.all()]
        random.seed(123)
        for example in batch.examples.all():
            for assignment in example.assignments.all():
                labels = uniform_choices(label_ids)
                assignment.set_user_annotations(labels, "ANNOTATION")
        batch.set_phase(Batch.Phase.DISCUSSION)

        codebook_content = (
            settings.BASE_DIR / "core/tests/testdata/codebook_populism_long_v2.md"
        ).read_text()
        codebook.save(content=codebook_content)
        batch = create_batch(project)

        for example in batch.examples.all():
            for assignment in example.assignments.all():
                assignment.set_user_annotations([label_ids[0]], "ANNOTATION")
        batch.set_phase(Batch.Phase.DISCUSSION)

        # Create a disagreement batch after discussion
        batch = create_batch(project)
        label_ids = [label.id for label in project.labels.all()]
        random.seed(42)
        for example in batch.examples.all():
            for assignment in example.assignments.all():
                labels = uniform_choices(label_ids)
                assignment.set_user_annotations(labels, "ANNOTATION")
        batch.set_phase(Batch.Phase.DISCUSSION)
        for example in batch.examples.filter(has_disagreement=True).all():
            for assignment in example.assignments.all():
                labels = uniform_choices(label_ids)
                assignment.set_user_annotations(labels, "DISCUSSION")
        batch.set_phase(Batch.Phase.EXPERT)

        batch = create_batch(project)

        # too many labels project
        project = create_project(
            "Emotion Detection",
            "A Project with a lot of labels",
            ["Anger", "Fear", "Hate", "Disgust", "Joy", "Ecstasy", "Sadness", "Surprise"],
            annotators,
            experts,
        )

        codebook = Codebook.objects.get(project=project)
        codebook_content = (
            settings.BASE_DIR / "core/tests/testdata/codebook_emotions_short.md"
        ).read_text()
        codebook.save(content=codebook_content)
        batch = create_batch(project)
