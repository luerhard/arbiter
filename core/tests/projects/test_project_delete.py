import re

from django.urls import reverse
import pytest

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from discuss.models import Message
from discuss.models import Room
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser
from users.models import User


def _delete(client, user, project):
    client.login(username=user.username, password="123")
    return client.post(reverse("project-delete", args=[project.pk]))


@pytest.mark.django_db
class TestProjectDelete:
    def test_owner_deletes_project_with_everything_in_it(self, client, project_discussion):
        project = project_discussion["project"]
        batch = project_discussion["batch"]
        codebook = project.codebook.get()
        codebook_dir = codebook.file.parent
        room = Room.objects.create(pk=batch.pk)
        Message.objects.create(room=room, user="system", message="Discussion started")
        Message.objects.create(
            room=room, user="someone", example=project_discussion["example"], message="Hi"
        )
        assert codebook_dir.is_dir()

        response = _delete(client, project_discussion["expert"], project)

        assert response.status_code == 302
        assert response.url == reverse("project-list")
        assert not Project.objects.filter(pk=project.pk).exists()
        assert not Batch.objects.filter(pk=batch.pk).exists()
        assert not Example.objects.filter(batch_id=batch.pk).exists()
        assert not ExampleAssignment.objects.filter(batch_id=batch.pk).exists()
        assert not Label.objects.filter(project_id=project.pk).exists()
        assert not ProjectUser.objects.filter(project_id=project.pk).exists()
        assert not Room.objects.filter(pk=batch.pk).exists()
        assert not Message.objects.filter(room_id=batch.pk).exists()
        assert not codebook_dir.exists()

    def test_other_projects_are_untouched(self, client, project_annotation):
        other = Project.objects.exclude(pk=project_annotation["project"].pk).first()
        other_codebook_dir = other.codebook.get().file.parent
        n_other_batches = other.batches.count()

        _delete(client, project_annotation["expert"], project_annotation["project"])

        assert Project.objects.filter(pk=other.pk).exists()
        assert other.batches.count() == n_other_batches
        assert other_codebook_dir.is_dir()

    def test_other_expert_cannot_delete(self, client, project_annotation):
        project = project_annotation["project"]
        expert = User.objects.create_user(username=f"other_expert_{project.pk}", password="123")
        ProjectUser.objects.create(project=project, user=expert, default_role=ProjectRole.EXPERT)

        response = _delete(client, expert, project)

        assert response.status_code == 403
        assert Project.objects.filter(pk=project.pk).exists()
        assert project.codebook.get().file.parent.is_dir()

    def test_annotator_cannot_delete(self, client, project_annotation):
        project = project_annotation["project"]

        response = _delete(client, project_annotation["annotators"][0], project)

        assert response.status_code == 403
        assert Project.objects.filter(pk=project.pk).exists()

    def test_get_does_not_delete(self, client, project_annotation):
        project = project_annotation["project"]
        client.login(username=project_annotation["expert"].username, password="123")

        response = client.get(reverse("project-delete", args=[project.pk]))

        assert response.status_code == 405
        assert Project.objects.filter(pk=project.pk).exists()


@pytest.mark.django_db
class TestDeleteButton:
    def _list(self, client, user):
        client.login(username=user.username, password="123")
        return client.get(reverse("project-list")).content.decode()

    def test_owner_sees_button_and_dialog(self, client, project_annotation):
        project = project_annotation["project"]

        content = self._list(client, project_annotation["expert"])

        assert f'commandfor="delete-project-{project.pk}"' in content
        assert f'id="delete-project-{project.pk}"' in content
        assert f'action="{reverse("project-delete", args=[project.pk])}"' in content
        assert "csrfmiddlewaretoken" in content
        assert re.search(r"its\s+1\s+batch:", content)
        assert reverse("project-export-project", args=[project.pk]) in content

    def test_other_members_do_not_see_it(self, client, project_annotation):
        project = project_annotation["project"]
        expert = User.objects.create_user(username=f"other_expert_{project.pk}", password="123")
        ProjectUser.objects.create(project=project, user=expert, default_role=ProjectRole.EXPERT)

        for user in (expert, project_annotation["annotators"][0]):
            content = self._list(client, user)
            assert f"delete-project-{project.pk}" not in content
