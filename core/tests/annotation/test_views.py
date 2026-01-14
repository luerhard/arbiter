from django.urls import reverse
import pytest

# Update the tuples to have just the assignment id (not a tuple)
URLS_WITH_URL_PARAMS = [
    ("annotate-batch", 1),
    ("annotate-edit", 81),
]

URLS_WITH_GET_PARAMS = [
    ("annotate-next", 1),
    ("annotate-prev", 11),
    ("annotate-reload", 11),
]


@pytest.mark.skip
@pytest.mark.django_db
@pytest.mark.usefixtures("populatedb")
class TestViews:
    pytestmarks = pytest.mark.django_db

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

    @pytest.mark.parametrize(("slug", "param"), URLS_WITH_URL_PARAMS)
    def test_login_required_as_annotator_url_params(self, slug, param, client):
        url = reverse(slug, args=(param,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200
