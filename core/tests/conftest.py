from pathlib import Path

from django.contrib.auth.models import Group
import pandas as pd
import pytest

from annotation.models import Batch
from annotation.models import Sentence
from core.models import Project


@pytest.fixture
def create_user(django_user_model, db):
    def make_user(username, group=None):
        user = django_user_model.objects.create_user(username=username, password="123")
        if group:
            group = Group.objects.filter(name=group).get()
            user.groups.add(group)
        return user

    return make_user


@pytest.fixture
def create_project(db):
    def make_project(name, n_batches=1):
        project = Project.objects.create(name=name)
        df = pd.read_csv(Path("tests/raw_data.csv"))
        for i in range(n_batches):
            batch = Batch.objects.create(project=project, batch_number=i + 1)
            for _, row in df.iterrows():
                Sentence.objects.create(batch=batch, content=row["text"])
        return project

    return make_project


@pytest.fixture
def _populate_db(db, create_user, create_project):
    for i in range(4):
        create_user(username=f"annotator{i}", group="Annotator")
    for i in range(3):
        create_user(username=f"expert{i}", group="Expert")

    create_project("testproject1", n_batches=1)
    create_project("testproject2", n_batches=2)
