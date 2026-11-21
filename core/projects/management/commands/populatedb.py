import random

from codebook.models import Codebook
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import pandas as pd

from data.models import Example
from data.models import Label
from project_types import PROJECT_TYPES
from project_types.span import tokens
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole


def uniform_choices(elementary_events: list):
    """Makes a uniform choice over the power set of `elementary_space` (event_space)
    by using a Poisson process modelled as a stream of bits."""
    events = []
    for event in elementary_events:
        if random.getrandbits(1):
            events.append(event)
    return events


def create_batch(project, examples_file="examples.csv"):
    batch = Batch.objects.create(
        project=project,
        current_phase=BatchPhase.ANNOTATION,
    )
    test_df = pd.read_csv(settings.BASE_DIR / "core/tests/testdata" / examples_file)

    batch.users.add(*project.annotators, through_defaults={"role": ProjectRole.ANNOTATOR})
    batch.users.add(*project.experts, through_defaults={"role": ProjectRole.EXPERT})

    examples = []
    for _i, row in test_df.iterrows():
        examples.append(Example(batch=batch, content=row["text"]))
    Example.objects.bulk_create(examples, ignore_conflicts=False)

    batch.set_phase(BatchPhase.ANNOTATION)

    return batch


def random_spans(example, label_ids):
    """One or two spans over a few words that every annotator marks (chosen by the
    example), sometimes plus one of their own: some examples are disagreements."""
    words = tokens(example.content)

    def span(rng):
        first = rng.randrange(len(words))
        last = min(len(words) - 1, first + rng.randint(0, 4))
        return [rng.choice(label_ids), words[first][0], words[last][1]]

    shared = random.Random(example.id)
    spans = [span(shared) for _ in range(shared.randint(1, 2))]
    if random.random() < 0.4:  # noqa: PLR2004
        spans.append(span(random))
    return PROJECT_TYPES["span"].validated_value(example, spans)


def create_project(name, description, labels, annotators, experts, project_type="classification"):
    project = Project.objects.create(
        name=name,
        description=description,
        owner=experts[0],
        project_type=project_type,
    )

    project.users.add(*annotators, through_defaults={"default_role": ProjectRole.ANNOTATOR})
    project.users.add(*experts, through_defaults={"default_role": ProjectRole.EXPERT})

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
        # User without any access
        annotator3 = User.objects.create_user("annotator3", password="123")
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

        # create populism batch 1, annotate, and change codebook
        batch = create_batch(project)
        label_ids = [label.id for label in project.labels.all()]
        random.seed(123)
        for assignment in batch.assignments.all():
            labels = uniform_choices(label_ids)
            assignment.set_user_annotations(labels)
        batch.set_phase(BatchPhase.DISCUSSION)

        # change codebook
        codebook_content = (
            settings.BASE_DIR / "core/tests/testdata/codebook_populism_long_v2.md"
        ).read_text()
        codebook.save(content=codebook_content)

        # create populism batch 2
        batch = create_batch(project)
        for assignment in batch.assignments.all():
            assignment.set_user_annotations([label_ids[0]])
        batch.set_phase(BatchPhase.DISCUSSION)

        # create populism batch 3 with disagreement after discussion
        batch = create_batch(project)
        label_ids = [label.id for label in project.labels.all()]
        random.seed(43)
        assignments = batch.assignments.all()
        for assignment in assignments:
            labels = uniform_choices(label_ids)
            assignment.set_user_annotations(labels)
        batch.set_phase(BatchPhase.DISCUSSION)

        examples_disagreement = batch.disagreements(phase=BatchPhase.ANNOTATION)
        assignments = batch.assignments.filter(
            phase=BatchPhase.DISCUSSION,
            example__in=examples_disagreement,
        ).select_related("example", "user")
        for assignment in assignments:
            labels = uniform_choices(label_ids)
            assignment.set_user_annotations(labels)
        batch.set_phase(BatchPhase.EXPERT)

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

        # span project: one batch per phase
        project = create_project(
            "Populist rhetoric (spans)",
            "Mark the passages of populist rhetoric in the text.",
            ["People-centrism", "Anti-elitism", "Sovereignty"],
            annotators,
            experts,
            project_type="span",
        )
        colors = ["#16a34a", "#dc2626", "#2563eb"]
        for label, color in zip(project.labels.order_by("pk"), colors, strict=True):
            label.color = color
            label.save()
        label_ids = [label.id for label in project.labels.all()]
        random.seed(7)
        create_batch(project, "examples_populism.csv")
        for phase in (BatchPhase.DISCUSSION, BatchPhase.EXPERT):
            batch = create_batch(project, "examples_populism.csv")
            for assignment in batch.assignments.select_related("example"):
                assignment.set_user_annotations(random_spans(assignment.example, label_ids))
            batch.set_phase(BatchPhase.DISCUSSION)
            if phase == BatchPhase.EXPERT:
                discussion = batch.assignments.filter(phase=BatchPhase.DISCUSSION)
                for assignment in discussion.select_related("example"):
                    assignment.set_user_annotations(random_spans(assignment.example, label_ids))
                batch.set_phase(BatchPhase.EXPERT)
