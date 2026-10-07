from django.urls import reverse
import pytest

from data.models import ExampleAssignment
from projects.models import BatchPhase


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

    def test_home_discussion_task_counts_the_examples_to_discuss(self, client, project_discussion):
        # The discussion works through the examples that got DISCUSSION assignments.
        # A label changing afterwards (here: the disagreement disappears from the
        # annotation labels) must not make the discussion task vanish.
        a1, a2 = project_discussion["annotators"]
        label1, _label2 = project_discussion["labels"]
        ExampleAssignment.objects.get(
            user=a2,
            example=project_discussion["example"],
            phase=BatchPhase.ANNOTATION,
        ).set_user_annotations([label1.id])
        client.login(username=a1.username, password="123")

        [task] = client.get(reverse("home")).context["tasks"]

        assert task["kind"] == "discuss"
        assert (task["done"], task["total"]) == (0, 1)
