from codebook.models import Codebook
from django.shortcuts import reverse
import pytest

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import Batch


@pytest.mark.django_db
class TestExpertViews:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects
            .from_project(project=self.data["batch"].project)
            .filter(batch_assignment__user=self.data["expert"])
            .first()
        )
        self.url = reverse("expert-dialogue", args=[self.data["batch"].id])

    def test_expert_dialogue_view_get_as_expert(self):
        """Tests that an expert can access the expert dialogue view."""

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert "expert/index.html" in (t.name for t in response.templates)
        assert "codebook" in response.context
        assert "sentence" in response.context
        assert response.context["sentence"] == self.data["example"]

    def test_expert_dialogue_view_get_as_annotator(self, client):
        """Tests that an annotator is denied access to the expert dialogue view."""
        login = client.login(username=self.data["annotators"][0], password="123")
        assert login is True

        url = reverse("expert-dialogue", args=[self.data["batch"].id])
        response = client.get(url)

        assert response.status_code == 403


@pytest.mark.django_db
class TestSaveLabelsExpertView:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects
            .from_project(project=self.data["batch"].project)
            .filter(batch_assignment__user=self.data["expert"])
            .first()
        )
        self.url = reverse("expert-label-save", args=[self.assignment.id])

    def test_post_correct_labels(self):
        example = self.data["example"]
        assert not example.has_expert_decision
        label_ids = [label.id for label in self.data["labels"]]

        response = self.client.post(self.url, data={"labels": label_ids})

        assert response.status_code == 302
        example.refresh_from_db()
        assert example.has_expert_decision
        assignment = self.assignment
        assert assignment.annotations.count() == 2
        assert sorted(assignment.annotations.values_list("label_id", flat=True)) == sorted(
            label_ids,
        )

    def test_post_empty_labels_list(self):
        # Set some annotations first to test their removal
        example = self.data["example"]
        response = self.client.post(self.url, data={"labels": []})
        assert response.status_code == 302
        assert example.has_expert_decision

    def test_post_invalid_label_id(self):
        """
        The form is invalid, but the view logic proceeds and saves the annotation,
        ignoring the invalid label.
        """
        example = self.data["example"]
        assert not example.has_expert_decision
        invalid_label_id = 9999
        response = self.client.post(
            self.url,
            data={"labels": [invalid_label_id]},
        )
        assert response.status_code == 302
        assert not example.has_expert_decision

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
        assert not example.has_expert_decision
        assert self.assignment.annotations.count() == 0
