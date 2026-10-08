from django.urls import reverse
import pytest


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("page", "who", "status"),
    [
        ("login", "anonymous", 200),
        ("user-profile", "anonymous", 302),
        ("user-profile", "annotator", 200),
    ],
)
def test_access(get_as, project_annotation, page, who, status):
    assert get_as(reverse(page), who, project_annotation).status_code == status


@pytest.mark.django_db
def test_logout_redirects_to_login(client):
    url = reverse("logout")
    login = client.login(username="annotator1", password="123")
    assert login == True
    req = client.get(url)
    assert req.status_code == 302
    assert req.url == reverse("login")
