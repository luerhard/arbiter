import pytest

from projects.models import Project
from users.models import User


class TestUserModel:
    pytestmark = pytest.mark.django_db

    @pytest.mark.skip
    def test_annotator1(self):
        annotator = User.objects.filter(username="annotator1").get()

        projects = annotator.assigned_projects
        exp_annotator_projects = Project.objects.filter(pk__in=[1, 2, 3])
        exp = {"Annotator": set(exp_annotator_projects), "Expert": set()}
        assert projects == exp

    @pytest.mark.skip
    def test_expert1(self):
        annotator = User.objects.filter(username="expert1").first()

        projects = annotator.assigned_projects
        exp_annotator_projects = Project.objects.filter(pk__in=[1, 2, 3])
        exp = {"Expert": set(exp_annotator_projects), "Annotator": set()}
        assert projects == exp
