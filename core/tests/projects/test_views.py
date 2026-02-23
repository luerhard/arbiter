import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import pytest

from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import Project
from projects.models import ProjectUser
from users.models import User

URLS_ANYROLE = [("project-list", None)]
URLS_EXPERT = [
    ("project-detail-expert", (1,)),
    ("export-batch", (1,)),
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
            ProjectUser.objects.filter(
                project=project,
                default_role=ProjectUser.Role.ANNOTATOR,
            ).count()
            == 2
        )
        assert (
            ProjectUser.objects.filter(
                project=project,
                default_role=ProjectUser.Role.EXPERT,
            ).count()
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
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator_1,
            default_role=ProjectUser.Role.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator_2,
            default_role=ProjectUser.Role.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=expert,
            default_role=ProjectUser.Role.EXPERT,
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
        batch_assignments = BatchAssignment.objects.filter(batch=batch)
        assert batch_assignments.count() == 2
        assert set(batch_assignments.values_list("user_id", flat=True)) == {
            annotator_1.id,
            annotator_2.id,
        }

        example_assignments = ExampleAssignment.objects.filter(example__batch=batch)
        assert example_assignments.count() == 4
        assert set(example_assignments.values_list("batch_assignment__user_id", flat=True)) == {
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
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator,
            default_role=ProjectUser.Role.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=expert,
            default_role=ProjectUser.Role.EXPERT,
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
