import pytest

from projects.models import Project
from users.models import User


class TestUserModel:
    pytestmark = pytest.mark.django_db

    def test_annotator1(self):
        annotator = User.objects.filter(username="annotator1").first()
        assert annotator.is_annotator == True
        assert annotator.is_expert == False
        assert annotator.is_admin == False

        projects = annotator.assigned_projects
        exp_annotator_projects = Project.objects.filter(pk__in=[1, 2, 3])
        exp = {"Annotator": set(exp_annotator_projects), "Expert": set()}
        assert projects == exp

    def test_discuss_batches(self):
        annotator = User.objects.filter(username="annotator1").first()
        discuss_batches = annotator.discuss_batches
        batches_count = sum(len(discuss_batches[project]) for project in discuss_batches)
        assert batches_count == 2

    def test_expert1(self):
        annotator = User.objects.filter(username="expert1").first()
        assert annotator.is_annotator == False
        assert annotator.is_expert == True
        assert annotator.is_admin == True

        projects = annotator.assigned_projects
        exp_annotator_projects = Project.objects.filter(pk__in=[1, 2, 3])
        exp = {"Expert": set(exp_annotator_projects), "Annotator": set()}
        assert projects == exp
