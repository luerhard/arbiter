import json
import re
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.text import slugify
import pytest

from data.models import ExampleAssignment
from discuss.models import Message
from discuss.models import Room
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser
from users.models import User

URLS_ANYROLE = [("project-list", None)]
URLS_EXPERT = [
    ("project-detail-expert", (1,)),
    ("project-export-batch", (1,)),
    ("project-export-project", (1,)),
]
URLS_ANNOTATOR = [("project-detail-annotator", (1,))]


@pytest.mark.django_db
class TestProjectAndBatchCreationViews:
    def test_create_project_creates_project_users(self, client):
        suffix = uuid.uuid4().hex[:8]
        annotator_1 = User.objects.create_user(username=f"ann_{suffix}", password="123")
        annotator_2 = User.objects.create_user(username=f"ann2_{suffix}", password="123")
        expert = User.objects.create_user(username=f"exp_{suffix}", password="123")

        login = client.login(username="expert1", password="123")
        assert login == True

        url = reverse("project-create")
        data = {
            "name": f"Created Project {suffix}",
            "description": "Created in test",
            "annotators": [annotator_1.id, annotator_2.id],
            "experts": [expert.id],
            "label_name": ["Label A"],
            "label_color": ["#111111"],
            "label_hotkey": ["a"],
        }
        response = client.post(url, data)

        assert response.status_code == 302
        project = Project.objects.get(name=f"Created Project {suffix}")
        assert (
            ProjectUser.objects.filter(project=project, default_role=ProjectRole.ANNOTATOR).count()
            == 2
        )
        assert (
            ProjectUser.objects.filter(project=project, default_role=ProjectRole.EXPERT).count()
            == 1
        )

    def test_create_batch_creates_batch_and_assignments(self, client):
        suffix = uuid.uuid4().hex[:8]
        annotator_1 = User.objects.create_user(username=f"batch_ann_{suffix}", password="123")
        annotator_2 = User.objects.create_user(username=f"batch_ann2_{suffix}", password="123")
        expert = User.objects.create_user(username=f"batch_exp_{suffix}", password="123")

        project = Project.objects.create(
            name=f"Batch Project {suffix}",
            description="For batch test",
            owner=expert,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator_1,
            default_role=ProjectRole.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator_2,
            default_role=ProjectRole.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=expert,
            default_role=ProjectRole.EXPERT,
        )

        login = client.login(username=expert.username, password="123")
        assert login == True

        upload = SimpleUploadedFile(
            "examples.csv",
            b"text\nFirst example\nSecond example\n",
            content_type="text/csv",
        )
        url = reverse("project-batch-create", args=(project.id,))
        response = client.post(
            url,
            {
                "file": upload,
                "annotators": [annotator_1.id, annotator_2.id],
                "experts": [expert.id],
            },
        )

        assert response.status_code == 302

        batch = Batch.objects.get(project=project)
        batch.set_phase(BatchPhase.ANNOTATION)
        example_assignments = ExampleAssignment.objects.filter(batch=batch)
        assert example_assignments.count() == 4
        assert set(example_assignments.values_list("user_id", flat=True)) == {
            annotator_1.id,
            annotator_2.id,
        }

    def test_batch_create_invalid_keeps_selected_users_context(self, client):
        suffix = uuid.uuid4().hex[:8]
        annotator = User.objects.create_user(username=f"batch_ann_ctx_{suffix}", password="123")
        expert = User.objects.create_user(username=f"batch_exp_ctx_{suffix}", password="123")

        project = Project.objects.create(
            name=f"Batch Project Context {suffix}",
            description="For batch context test",
            owner=expert,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator,
            default_role=ProjectRole.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=expert,
            default_role=ProjectRole.EXPERT,
        )

        login = client.login(username=expert.username, password="123")
        assert login == True

        url = reverse("project-batch-create", args=(project.id,))
        response = client.post(
            url,
            {
                # Deliberately omit file to keep the form invalid.
                "annotators": [annotator.id],
                "experts": [expert.id],
            },
        )

        assert response.status_code == 200
        assert response.context["annotators_selected_users"] == (
            f'[{{"id": {annotator.id}, "username": "{annotator.username}"}}]'
        )
        assert response.context["experts_selected_users"] == (
            f'[{{"id": {expert.id}, "username": "{expert.username}"}}]'
        )


@pytest.mark.django_db
class TestViews:
    @pytest.mark.parametrize("params", set(URLS_EXPERT + URLS_ANNOTATOR + URLS_ANYROLE))
    def test_login_required_not_logged_in(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.parametrize("params", URLS_ANNOTATOR + URLS_ANYROLE)
    def test_http_200_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_EXPERT + URLS_ANYROLE)
    def test_http_200_as_expert(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_ANNOTATOR)
    def test_http_403_as_expert(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 403

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_http_403_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 403

    def test_change_batch_phase_as_annotator(self, client):
        url = reverse("change-batch-phase", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        data = {"current_phase": "A"}
        req = client.post(url, data)
        assert req.status_code == 403

    def test_change_batch_phase_as_expert(self, client):
        url = reverse("change-batch-phase", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login == True
        data = {"current_phase": "A"}
        req = client.post(url, data)
        assert req.status_code == 204

    def test_delete_batch_as_annotator(self, client):
        url = reverse("delete-batch", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.post(url)
        assert req.status_code == 403
        assert Batch.objects.filter(id=1).exists()

    def test_delete_batch_as_expert(self, client):
        url = reverse("delete-batch", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.post(url)
        assert req.status_code == 204
        assert req.headers["HX-Refresh"] == "true"
        assert not Batch.objects.filter(id=1).exists()

    def test_redirect_project_detail_expert(self, client):
        url = reverse("project-detail", args=(1,))
        login = client.login(username="expert1", password="123")
        req = client.get(url)
        assert req.status_code == 302
        assert req.url == reverse("project-detail-expert", args=(1,))

    def test_redirect_project_detail_annotator(self, client):
        url = reverse("project-detail", args=(1,))
        login = client.login(username="annotator1", password="123")
        req = client.get(url)
        assert req.status_code == 302
        assert req.url == reverse("project-detail-annotator", args=(1,))


@pytest.mark.django_db
def test_delete_batch_cascades_related_objects(client, project_annotation):
    data = project_annotation
    batch = data["batch"]
    expert = data["expert"]
    codebook = data["project"].codebook.get()
    tag = f"batch_{batch.batch_number}"
    assert ExampleAssignment.objects.filter(batch=batch).exists()
    assert tag in codebook.repo.tags

    login = client.login(username=expert.username, password="123")
    assert login is True

    resp = client.post(reverse("delete-batch", args=(batch.id,)))

    assert resp.status_code == 204
    assert not Batch.objects.filter(id=batch.id).exists()
    assert not ExampleAssignment.objects.filter(batch_id=batch.id).exists()
    assert tag not in codebook.repo.tags


@pytest.mark.django_db
class TestExportBatchView:
    ISO_WITH_MS_TZ_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}$",
    )

    def test_export_batch_returns_expected_jsonl(self, client, project_annotation):
        data = project_annotation
        batch = data["batch"]
        example = data["example"]
        expert = data["expert"]
        annotator_1, annotator_2 = data["annotators"]
        label_1, label_2 = data["labels"]

        a1 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_1,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        a2 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_2,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        a1.set_user_annotations(label_ids=[label_1.id])
        a2.set_user_annotations(label_ids=[label_2.id])

        batch.set_phase(BatchPhase.DISCUSSION)
        d1 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_1,
            example=example,
            phase=BatchPhase.DISCUSSION,
        )
        d2 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_2,
            example=example,
            phase=BatchPhase.DISCUSSION,
        )
        d1.set_user_annotations(label_ids=[label_1.id])
        d2.set_user_annotations(label_ids=[label_2.id])

        batch.set_phase(BatchPhase.EXPERT)
        ex = ExampleAssignment.objects.get(
            batch=batch,
            user=expert,
            example=example,
            phase=BatchPhase.EXPERT,
        )
        ex.set_user_annotations(label_ids=[label_1.id])

        room = Room.objects.create()
        Message.objects.create(
            room=room,
            user=annotator_1.username,
            example=example,
            message="first message",
        )
        Message.objects.create(
            room=room,
            user=annotator_2.username,
            example=example,
            message="second message",
        )

        login = client.login(username=expert.username, password="123")
        assert login == True
        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        assert response.status_code == 200
        assert response["Content-Disposition"] == (
            f"attachment; filename=batch_{batch.batch_number}.jsonl"
        )
        assert response["Content-Type"] == "application/text"

        lines = response.content.decode("utf-8").splitlines()
        assert len(lines) == 1

        row = json.loads(lines[0])
        assert row["text_id"] == example.id
        assert row["text"] == example.content
        assert row["batch_number"] == batch.batch_number
        assert row["batch_annotators"] == sorted([annotator_1.username, annotator_2.username])
        assert row["batch_experts"] == [expert.username]

        assert len(row["labels_annotation"]) == 2
        assert len(row["labels_discussion"]) == 2
        assert len(row["labels_expert"]) == 1

        for key in ["labels_annotation", "labels_discussion", "labels_expert"]:
            for entry in row[key]:
                assert set(entry.keys()) == {"user", "labels", "at"}
                assert self.ISO_WITH_MS_TZ_RE.match(entry["at"])

        assert len(row["messages_discussion"]) == 2
        assert row["messages_discussion"][0]["content"] == "first message"
        assert row["messages_discussion"][1]["content"] == "second message"
        for msg in row["messages_discussion"]:
            assert set(msg.keys()) == {"user", "at", "content"}
            assert self.ISO_WITH_MS_TZ_RE.match(msg["at"])

    def test_export_batch_empty_when_no_assignment_completed(self, client, project_annotation):
        data = project_annotation
        batch = data["batch"]
        expert = data["expert"]

        login = client.login(username=expert.username, password="123")
        assert login == True
        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == ""

    def test_export_project_returns_jsonl_with_slugified_filename(self, client, project_annotation):
        data = project_annotation
        batch = data["batch"]
        project = data["project"]
        expert = data["expert"]
        annotator = data["annotators"][0]
        label = data["labels"][0]
        example = data["example"]

        assignment = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        assignment.set_user_annotations(label_ids=[label.id])

        project.name = "My Project 2026 !!!"
        project.save()

        login = client.login(username=expert.username, password="123")
        assert login == True
        response = client.get(reverse("project-export-project", args=(project.id,)))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/text"
        assert response["Content-Disposition"] == (
            f"attachment; filename=project_{slugify(project.name)}.jsonl"
        )

        lines = response.content.decode("utf-8").splitlines()
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["batch_number"] == batch.batch_number
        assert row["text_id"] == example.id
        assert row["labels_annotation"][0]["user"] == annotator.username
