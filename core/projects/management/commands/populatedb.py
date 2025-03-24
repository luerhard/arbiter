from pathlib import Path

from codebook.models import Codebook
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
import pandas as pd

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser


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

        project1 = Project.objects.create(
            name="Populism",
            description="Example Project about Populism",
        )
        Label.objects.create(project=project1, name="Anti-Elitism", hotkey="1")
        Label.objects.create(project=project1, name="People-Centrism", hotkey="2")
        codebook = Codebook.objects.create(project=project1)

        codebook_content = """
= Introduction

== Anti-Elitism

This is how anti-elitism works.

== People-Centrism

This is when to annotate People-Centrism
"""

        codebook.save(content=codebook_content)

        for u in annotators:
            ProjectUser.objects.create(project=project1, user=u, role=ProjectUser.Role.ANNOTATOR)

        for u in experts:
            ProjectUser.objects.create(project=project1, user=u, role=ProjectUser.Role.EXPERT)

        batch1 = Batch.objects.create(
            project=project1,
            batch_number=1,
            phase=Batch.Phase.ANNOTATION,
        )
        test_df = pd.read_csv(settings.BASE_DIR / "../tests/raw_data.csv")

        for i, row in test_df.iterrows():
            ex = Example.objects.create(batch=batch1, content=row["text"])
            for user in annotators:
                ExampleAssignment.objects.create(example=ex, user=user, order=i)
