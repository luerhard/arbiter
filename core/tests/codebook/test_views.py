import io
import zipfile

from codebook.models import Codebook
from django.urls import reverse
import pytest

from projects.models import Batch
from projects.models import Project

URLS_EXPERT = [("codebook-view", (1,)), ("codebook-diff", (1,)), ("codebook-edit", (1,))]

URLS_ANNOTATOR = [("codebook-view", (1,)), ("codebook-diff", (1,))]


@pytest.fixture
def project_setup():
    return {
        "project": Project.objects.first(),
        "batch": Batch.objects.first(),
        "codebook": Codebook.objects.first(),
    }


@pytest.mark.django_db
class TestViews:
    @pytest.mark.parametrize("params", set(URLS_EXPERT + URLS_ANNOTATOR))
    def test_login_required_not_logged_in(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.parametrize("params", URLS_ANNOTATOR)
    def test_http_200_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_http_200_as_expert(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", [("codebook-edit", (1,))])
    def test_codebook_update_view_annotator_access_denied(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 403

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_codebook_update_view_post_all_data(self, params, client, project_setup):
        login = client.login(username="expert1", password="123")
        assert login is True

        codebook = project_setup["codebook"]

        new_content = "Updated codebook content test 1."
        post_data = {
            "content": new_content,
            "rationale": "Test rationale",
        }
        response = client.post(reverse("codebook-edit", args=[codebook.id]), post_data)

        assert response.status_code == 302
        assert response.url == codebook.get_absolute_url()

        codebook.refresh_from_db()
        assert codebook.content == new_content + "\n"

    def test_codebook_export_not_logged_in(self, client):
        url = reverse("codebook-export", args=(1,))
        req = client.get(url)
        assert req.status_code == 302

    def test_codebook_export_annotator_access_denied(self, client):
        url = reverse("codebook-export", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login is True
        req = client.get(url)
        assert req.status_code == 403

    def test_codebook_export_as_expert(self, client):
        url = reverse("codebook-export", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login is True
        req = client.get(url)

        assert req.status_code == 200
        assert req["Content-Type"] == "application/zip"
        assert "attachment" in req["Content-Disposition"]
        assert req["Content-Disposition"].endswith(".zip")

        with zipfile.ZipFile(io.BytesIO(req.content)) as zf:
            assert zf.testzip() is None
            names = zf.namelist()
            assert "main.md" in names
            assert any(name.startswith(".git/") for name in names)

    def test_get_as_context(self, client, project_setup):
        login = client.login(username="expert1", password="123")
        assert login is True

        codebook = project_setup["codebook"]
        batch = project_setup["batch"]

        # Update codebook content to create a new version
        new_content = "This is the new version of the codebook."
        codebook.save(content=new_content, commit_message="Update for batch 1")

        # Tag this version for the batch
        codebook.tag_version(batch.batch_number)

        context = codebook.get_as_context(batch.batch_number)

        assert "codebook" in context
        assert "content_diff" in context
        assert context["codebook"] == codebook
        assert new_content in context["content_diff"]

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_codebook_update_view_post_some_data(self, params, client, project_setup):
        login = client.login(username="expert1", password="123")
        assert login is True

        codebook = project_setup["codebook"]

        new_content = "Updated codebook content test 2."
        post_data = {
            "content": new_content,
            "rationale": "Test rationale",
        }
        response = client.post(reverse("codebook-edit", args=[codebook.id]), post_data)

        assert response.status_code == 302
        assert response.url == codebook.get_absolute_url()

        codebook.refresh_from_db()
        assert codebook.content == new_content + "\n"


@pytest.mark.django_db
class TestDiffAfterBatchDeletion:
    """Deleting a batch removes its codebook tag; the next batch's diff must still work."""

    def _diff(self, client, codebook, old, new):
        return client.get(
            reverse("codebook-diff", args=(codebook.pk,)), {"batch_old": old, "batch_new": new}
        )

    def test_compares_with_the_batch_before_the_deleted_one(self, client, project_annotation):
        codebook = project_annotation["project"].codebook.get()
        for number in (2, 3):
            codebook.save(content=f"Version {number}\n", commit_message=f"Batch {number}")
            codebook.tag_version(number)
        codebook.untag_version(2)
        client.login(username=project_annotation["expert"].username, password="123")

        response = self._diff(client, codebook, 2, 3)

        assert response.status_code == 200
        assert response.context["batch_old"] == 1
        assert "Version 3" in response.context["content_diff"]

    def test_deleted_batch_has_no_diff(self, client, project_annotation):
        codebook = project_annotation["project"].codebook.get()
        client.login(username=project_annotation["expert"].username, password="123")

        response = self._diff(client, codebook, 1, 2)

        assert response.status_code == 404
