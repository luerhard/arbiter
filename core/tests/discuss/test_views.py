from django.urls import reverse
import pytest

URLS_LOGIN_REQUIRED = [
    ("discuss-batch", (1,)),
]


@pytest.mark.django_db
@pytest.mark.usefixtures("populatedb")
class TestViews:
    @pytest.mark.parametrize("params", URLS_LOGIN_REQUIRED)
    def test_login_required_not_logged_in(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.parametrize("params", URLS_LOGIN_REQUIRED)
    def test_http_200_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200
