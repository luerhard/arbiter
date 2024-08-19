from django.urls import reverse
import pytest

URLS_NO_LOGIN_REQUIRED = [("login", None)]
URLS_LOGIN_REQUIRED = [("user-profile", None)]


class TestViews:
    @pytest.mark.parametrize("params", URLS_LOGIN_REQUIRED)
    def test_login_required_not_logged_in(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.django_db
    @pytest.mark.parametrize("params", URLS_LOGIN_REQUIRED)
    def test_login_required_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_NO_LOGIN_REQUIRED)
    def test_no_login_required(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.django_db
    def test_logout_redirects_to_login(self, client):
        url = reverse("logout")
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 302
        assert req.url == reverse("login")
