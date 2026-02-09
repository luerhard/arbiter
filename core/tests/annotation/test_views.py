from django.urls import reverse
import pytest

from data.models import ExampleAssignment
from projects.models import Batch

# Update the tuples to have just the assignment id (not a tuple)
URLS_WITH_URL_PARAMS = [
    ("annotate-batch", 1),
]

URLS_WITH_GET_PARAMS = [
    ("annotate-next", 1),
    ("annotate-prev", 11),
]


class TestViews:
    pytestmark = pytest.mark.django_db

    @pytest.mark.parametrize(("slug", "assignment_id"), URLS_WITH_GET_PARAMS)
    def test_login_required_not_logged_in_get_params_urls(self, slug, assignment_id, client):
        url = reverse(slug)
        req = client.get(url, data={"assignment_id": assignment_id})
        assert req.status_code == 302

    @pytest.mark.parametrize(("slug", "assignment_id"), URLS_WITH_GET_PARAMS)
    def test_login_required_as_annotator_get_params_urls(self, slug, assignment_id, client):
        url = reverse(slug)
        login = client.login(username="annotator1", password="123")
        assert login is True
        req = client.get(url, data={"assignment_id": assignment_id})
        assert req.status_code == 200

    @pytest.mark.parametrize(("slug", "param"), URLS_WITH_URL_PARAMS)
    def test_login_required_not_logged_in_url_params(self, slug, param, client):
        url = reverse(slug, args=(param,))
        req = client.get(url)
        assert req.status_code == 302

    def test_annotation_view_of_unfinished_batch(self, client):
        url = reverse("annotate-batch", args=(4,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    def test_annotation_view_of_finished_batch(self, client):
        url = reverse("annotate-batch", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 302
        assert req.url == "/annotation/batch/1/done"

    def test_annotation_view_context_includes_labels(self, client):
        login = client.login(username="annotator1", password="123")
        assert login is True

        # Ensure batch 1 is treated as unfinished for this user.
        ExampleAssignment.objects.filter(
            example__batch_id=1,
            batch_assignment__user__username="annotator1",
            phase=Batch.Phase.ANNOTATION,
        ).update(done=None)

        url = reverse("annotate-batch", args=(1,))
        req = client.get(url)
        assert req.status_code == 200
        assert req.context is not None
        assignment_id = req.context["assignment_id"]

        labels_url = reverse("annotate-labels")
        labels_resp = client.get(labels_url, data={"assignment_id": assignment_id})
        assert labels_resp.status_code == 200
        assert labels_resp.context is not None
        labels = labels_resp.context["labels"]
        assert isinstance(labels, list)
        assert len(labels) > 0
