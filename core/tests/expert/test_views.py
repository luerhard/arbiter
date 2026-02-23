import json

from django.shortcuts import reverse
import pytest

from data.models import ExampleAssignment
from projects.models import BatchPhase


@pytest.mark.django_db
class TestExpertViews:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects.from_project(project=self.data["batch"].project)
            .filter(user=self.data["expert"], phase=BatchPhase.EXPERT)
            .first()
        )
        self.shell_url = reverse("expert-dialogue", args=[self.data["batch"].id])
        self.content_url = reverse("expert-dialogue-content", args=[self.data["batch"].id])

    def test_expert_dialogue_shell_get_as_expert(self):
        response = self.client.get(self.shell_url)
        assert response.status_code == 200
        assert "expert/index.html" in (t.name for t in response.templates)
        assert response.context["batch_id"] == self.data["batch"].id

    def test_expert_dialogue_content_get_as_expert(self):
        response = self.client.get(
            self.content_url,
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert "expert/partials/dialog.html" in (t.name for t in response.templates)
        assert "codebook" in response.context
        assert "sentence" in response.context
        assert response.context["sentence"] == self.data["example"]
        assert response.context["assignment"] == self.assignment

    def test_expert_dialogue_view_get_as_annotator(self, client):
        login = client.login(username=self.data["annotators"][0].username, password="123")
        assert login is True

        response = client.get(self.shell_url)

        assert response.status_code == 403


@pytest.mark.django_db
class TestSaveLabelsExpertView:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects.from_project(project=self.data["project"])
            .filter(
                user=self.data["expert"],
                phase=BatchPhase.EXPERT,
            )
            .first()
        )
        self.url = reverse("expert-label-save", args=[self.assignment.id])
        self.content_url = reverse("expert-dialogue-content", args=[self.data["batch"].id])

    def test_post_correct_labels_non_htmx_redirects(self):
        example = self.data["example"]
        assert not example.has_expert_decision
        label_ids = [label.id for label in self.data["labels"]]

        response = self.client.post(self.url, data={"labels": label_ids})

        assert response.status_code == 302
        assert response.url == reverse("project-detail", args=[self.data["project"].id])
        example.refresh_from_db()
        self.assignment.refresh_from_db()
        assert example.has_expert_decision
        assert self.assignment.annotations.count() == 2
        assert sorted(self.assignment.annotations.values_list("label_id", flat=True)) == sorted(
            label_ids,
        )

    def test_post_correct_labels_htmx_returns_partial_and_trigger(self):
        label_ids = [label.id for label in self.data["labels"]]
        response = self.client.post(
            self.url,
            data={"labels": label_ids},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "expert/partials/dialog.html" in (t.name for t in response.templates)
        trigger = json.loads(response["HX-Trigger"])
        assert "messages" in trigger
        assert any(message["message"] == "Saved." for message in trigger["messages"])

    def test_post_invalid_label_id_htmx_returns_error_message(self):
        invalid_label_id = 9999
        response = self.client.post(
            self.url,
            data={"labels": [invalid_label_id]},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0
        trigger = json.loads(response["HX-Trigger"])
        assert "messages" in trigger
        assert any(
            "Something was invalid:" in message["message"] for message in trigger["messages"]
        )

    def test_post_empty_labels_list(self):
        example = self.data["example"]
        response = self.client.post(self.url, data={"labels": []})
        assert response.status_code == 302
        example.refresh_from_db()
        assert example.has_expert_decision

    def test_post_invalid_label_id(self):
        example = self.data["example"]
        assert not example.has_expert_decision
        invalid_label_id = 9999
        response = self.client.post(
            self.url,
            data={"labels": [invalid_label_id]},
        )
        assert response.status_code == 302
        example.refresh_from_db()
        self.assignment.refresh_from_db()
        assert not example.has_expert_decision
        assert self.assignment.annotations.count() == 0

    def test_post_mixed_valid_and_invalid_label_ids(self):
        example = self.data["example"]
        labels = self.data["labels"]
        assert not example.has_expert_decision
        valid_label_id = labels[0].id
        invalid_label_id = 9999
        response = self.client.post(
            self.url,
            data={
                "labels": [valid_label_id, invalid_label_id],
            },
        )
        assert response.status_code == 302
        example.refresh_from_db()
        self.assignment.refresh_from_db()
        assert not example.has_expert_decision
        assert self.assignment.annotations.count() == 0

    def test_post_non_integer_label_id(self):
        example = self.data["example"]
        assert not example.has_expert_decision
        response = self.client.post(
            self.url,
            data={
                "labels": ["not-a-number"],
            },
        )
        assert response.status_code == 302
        example.refresh_from_db()
        self.assignment.refresh_from_db()
        assert not example.has_expert_decision
        assert self.assignment.annotations.count() == 0

    def test_content_view_when_all_done_shows_finished_state(self):
        self.assignment.set_user_annotations([self.data["labels"][0].id])
        response = self.client.get(
            self.content_url,
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "All disagreements are resolved." in response.content.decode()
