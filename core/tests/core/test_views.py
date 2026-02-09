from django.urls import reverse
import pytest


@pytest.mark.django_db
class TestCoreViews:
    def test_home_view_no_login_required(self, client):
        url = reverse("home")
        response = client.get(url)
        assert response.status_code == 200
