from codebook.models import Codebook
from django.urls import reverse
import pytest

from data.models import Example
from data.models import Label
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
