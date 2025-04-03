from django.urls import reverse
import pytest

URLS_ANYROLE = [("project-list", None)]
URLS_EXPERT = [
    ("project-detail-expert", (1,)),
    ("export-batch", (1,)),
]
URLS_ANNOTATOR = [("project-detail-annotator", (1,))]

# TODO: write test for change batch phase
# TODO: write test for download batch results


@pytest.mark.django_db()
@pytest.mark.usefixtures("populatedb")
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
        data = {"phase": "A"}
        req = client.post(url, data)
        assert req.status_code == 403

    def test_change_batch_phase_as_expert(self, client):
        url = reverse("change-batch-phase", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login == True
        data = {"phase": "A"}
        req = client.post(url, data)
        assert req.status_code == 204
