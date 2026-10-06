from django.urls import reverse
import pytest


@pytest.mark.django_db
class TestCoreViews:
    def test_home_redirects_anonymous_users_to_login(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert response.url == reverse("login")

    def test_home_lists_open_annotation_work(self, client, project_annotation):
        annotator = project_annotation["annotators"][0]
        batch = project_annotation["batch"]
        client.login(username=annotator.username, password="123")

        response = client.get(reverse("home"))

        assert response.status_code == 200
        [task] = response.context["tasks"]
        assert task["kind"] == "annotate"
        assert task["batch"] == batch
        assert reverse("annotate-batch", args=(batch.id,)) in response.content.decode()

    def test_home_has_no_tasks_for_expert_during_annotation(self, client, project_annotation):
        client.login(username=project_annotation["expert"].username, password="123")

        response = client.get(reverse("home"))

        assert response.status_code == 200
        assert response.context["tasks"] == []
