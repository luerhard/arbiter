"""Roles are assigned per batch (BatchUser.role); the project role
(ProjectUser.default_role) only defines membership, the landing page and who
manages the project. These tests cover the three ways the two levels used to
disagree."""

import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import pytest

from projects.models import Batch
from projects.models import BatchPhase
from projects.models import ProjectRole
from projects.models import ProjectUser
from projects.models.batch import BatchUser
from users.models import User


def _user(prefix):
    return User.objects.create_user(username=f"{prefix}_{uuid.uuid4().hex[:8]}", password="123")


def _project_member(project, prefix, role):
    user = _user(prefix)
    ProjectUser.objects.create(project=project, user=user, default_role=role)
    return user


def _assign(batch, user, role):
    """Add the user to the batch and create their assignments for the current phase."""
    batch.users.add(user, through_defaults={"role": role})
    batch._create_example_assignments(phase=batch.current_phase)


def _login(client, user):
    assert client.login(username=user.username, password="123")


def _csv():
    return SimpleUploadedFile("batch.csv", b"text\nFirst\nSecond\n", content_type="text/csv")


# --- Scenario 1: users outside the project ----------------------------------


@pytest.mark.django_db
class TestOutsiderCannotBeAssigned:
    def test_batch_create_rejects_annotator_outside_project(self, client, project_annotation):
        project = project_annotation["project"]
        expert = project_annotation["expert"]
        outsider = _user("outsider")
        _login(client, expert)

        response = client.post(
            reverse("project-batch-create", args=(project.id,)),
            {"file": _csv(), "annotators": [outsider.id], "experts": [expert.id]},
        )

        assert response.status_code == 200
        assert response.context["form"].errors
        assert not BatchUser.objects.filter(user=outsider).exists()
        assert project.batches.count() == 1

    def test_user_search_only_returns_project_members(self, client, project_annotation):
        project = project_annotation["project"]
        expert = project_annotation["expert"]
        member = project_annotation["annotators"][0]
        outsider = _user("outsider")
        _login(client, expert)

        response = client.get(
            reverse("project-user-search"),
            {"q": "", "project_id": project.id},
        )

        content = response.content.decode()
        assert member.username in content
        assert outsider.username not in content

    def test_user_search_without_project_returns_everyone(self, client, project_annotation):
        # project creation still needs to find users that are in no project yet
        expert = project_annotation["expert"]
        outsider = _user("outsider")
        _login(client, expert)

        response = client.get(reverse("project-user-search"), {"q": outsider.username})

        assert outsider.username in response.content.decode()


# --- Scenario 2: a different role in a single batch -------------------------


@pytest.mark.django_db
class TestDifferentRolePerBatch:
    def test_batch_create_accepts_project_expert_as_annotator(self, client, project_annotation):
        project = project_annotation["project"]
        expert = project_annotation["expert"]
        expert2 = _project_member(project, "expert2", ProjectRole.EXPERT)
        _login(client, expert)

        response = client.post(
            reverse("project-batch-create", args=(project.id,)),
            {"file": _csv(), "annotators": [expert2.id], "experts": [expert.id]},
        )

        assert response.status_code == 302
        batch = project.batches.order_by("-batch_number").first()
        assert BatchUser.objects.get(batch=batch, user=expert2).role == ProjectRole.ANNOTATOR

    def test_project_expert_can_annotate_batch(self, client, project_annotation):
        batch = project_annotation["batch"]
        expert2 = _project_member(batch.project, "expert2", ProjectRole.EXPERT)
        _assign(batch, expert2, ProjectRole.ANNOTATOR)
        _login(client, expert2)

        entry = client.get(reverse("annotate-batch", args=(batch.id,)))
        assert entry.status_code == 302
        assert "/assignment/" in entry.url

        assert client.get(entry.url).status_code == 200
        assert client.get(reverse("annotate-done", args=(batch.id,))).status_code == 200

    def test_project_expert_can_join_discussion(self, client, project_discussion):
        batch = project_discussion["batch"]
        expert2 = _project_member(batch.project, "expert2", ProjectRole.EXPERT)
        batch.users.add(expert2, through_defaults={"role": ProjectRole.ANNOTATOR})
        _login(client, expert2)

        response = client.get(reverse("discuss-batch", args=(batch.id,)))

        assert response.status_code == 200

    def test_discussion_page_only_in_discussion_phase(self, client, project_annotation):
        batch = project_annotation["batch"]
        _login(client, project_annotation["annotators"][0])

        response = client.get(reverse("discuss-batch", args=(batch.id,)))

        assert response.status_code == 302
        assert response.url == reverse("project-detail", args=(batch.project_id,))

    def test_project_annotator_can_make_expert_decisions(self, client, project_expert):
        batch = project_expert["batch"]
        annotator3 = _project_member(batch.project, "annotator3", ProjectRole.ANNOTATOR)
        _assign(batch, annotator3, ProjectRole.EXPERT)
        _login(client, annotator3)

        entry = client.get(reverse("expert-batch", args=(batch.id,)))
        assert entry.status_code == 302
        assert "/assignment/" in entry.url

        assignment_page = client.get(entry.url)
        assert assignment_page.status_code == 200

    def test_my_work_page_links_expert_to_annotation(self, client, project_annotation):
        batch = project_annotation["batch"]
        expert2 = _project_member(batch.project, "expert2", ProjectRole.EXPERT)
        _assign(batch, expert2, ProjectRole.ANNOTATOR)
        _login(client, expert2)

        response = client.get(reverse("project-detail-annotator", args=(batch.project.id,)))

        assert response.status_code == 200
        assert reverse("annotate-batch", args=(batch.id,)) in response.content.decode()

    def test_my_work_page_links_annotator_to_expert_decisions(self, client, project_expert):
        batch = project_expert["batch"]
        annotator3 = _project_member(batch.project, "annotator3", ProjectRole.ANNOTATOR)
        _assign(batch, annotator3, ProjectRole.EXPERT)
        _login(client, annotator3)

        response = client.get(reverse("project-detail-annotator", args=(batch.project.id,)))

        assert response.status_code == 200
        assert reverse("expert-batch", args=(batch.id,)) in response.content.decode()

    def test_expert_page_links_to_my_work_when_expert_annotates(self, client, project_annotation):
        project = project_annotation["project"]
        expert = project_annotation["expert"]
        batch2 = Batch.objects.create(project=project, current_phase=BatchPhase.ANNOTATION)
        batch2.users.add(expert, through_defaults={"role": ProjectRole.ANNOTATOR})
        _login(client, expert)

        response = client.get(reverse("project-detail-expert", args=(project.id,)))

        assert reverse("project-detail-annotator", args=(project.id,)) in (
            response.content.decode()
        )

    def test_expert_page_progress_shows_batch_annotators(self, client, project_annotation):
        batch = project_annotation["batch"]
        expert = project_annotation["expert"]
        expert2 = _project_member(batch.project, "expert2", ProjectRole.EXPERT)
        _assign(batch, expert2, ProjectRole.ANNOTATOR)
        _login(client, expert)

        response = client.get(reverse("project-detail-expert", args=(batch.project.id,)))

        [batch_data] = response.context["batches"]
        shown = {row["user"] for row in batch_data["users"]}
        assert shown == {*project_annotation["annotators"], expert2}


# --- Scenario 3: project members that are not part of the batch -------------


@pytest.mark.django_db
class TestProjectMemberOutsideBatch:
    def test_annotator_not_in_batch_cannot_annotate(self, client, project_annotation):
        batch = project_annotation["batch"]
        annotator3 = _project_member(batch.project, "annotator3", ProjectRole.ANNOTATOR)
        _login(client, annotator3)

        assert client.get(reverse("annotate-batch", args=(batch.id,))).status_code == 403
        assert client.get(reverse("annotate-done", args=(batch.id,))).status_code == 403

    def test_annotator_not_in_batch_cannot_join_discussion(self, client, project_discussion):
        batch = project_discussion["batch"]
        annotator3 = _project_member(batch.project, "annotator3", ProjectRole.ANNOTATOR)
        _login(client, annotator3)

        assert client.get(reverse("discuss-batch", args=(batch.id,))).status_code == 403

    def test_expert_not_in_batch_cannot_make_expert_decisions(self, client, project_expert):
        batch = project_expert["batch"]
        expert2 = _project_member(batch.project, "expert2", ProjectRole.EXPERT)
        _login(client, expert2)

        assert client.get(reverse("expert-batch", args=(batch.id,))).status_code == 403

    def test_expert_not_in_batch_can_still_manage_it(self, client, project_annotation):
        # managing batches (export, phase change, delete) stays a project-level right
        batch = project_annotation["batch"]
        expert2 = _project_member(batch.project, "expert2", ProjectRole.EXPERT)
        _login(client, expert2)

        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        assert response.status_code == 200

    def test_my_work_page_hides_batches_without_role(self, client, project_annotation):
        batch = project_annotation["batch"]
        annotator3 = _project_member(batch.project, "annotator3", ProjectRole.ANNOTATOR)
        _login(client, annotator3)

        response = client.get(reverse("project-detail-annotator", args=(batch.project.id,)))

        assert response.status_code == 200
        assert response.context["batches"] == []
