from codebook.models import Codebook
from django.shortcuts import reverse
import pytest

from data.models import Example, Label, ExampleAssignment
from projects.models import Batch


@pytest.fixture
def project_setup():
    # Assumes populatedb creates at least one project, batch, example, and label
    # and that the example has disagreement for the expert view to work.
    example = next(
        (
            e
            for e in Example.objects.all()
            if e.has_disagreement and e.has_disagreement_after_discussion and not e.has_expert_decision
        ),
        None,
    )

    return {
        "batch": example.batch,
        "example": example,
        "codebook": Codebook.objects.filter(project=example.batch.project).first(),
    }


@pytest.mark.django_db
class TestExpertViews:
    def test_expert_dialogue_view_get_as_expert(self, client, project_setup):
        """Tests that an expert can access the expert dialogue view."""
        login = client.login(username="expert1", password="123")
        assert login is True

        codebook = project_setup["codebook"]
        batch = project_setup["batch"]
        example = project_setup["example"]

        assert example is not None, "No suitable example with disagreement found in populatedb"

        url = reverse("expert-dialogue", args=[codebook.id, batch.id, example.id])
        response = client.get(url)

        assert response.status_code == 200
        assert "expert/dialogue.html" in (t.name for t in response.templates)
        assert response.context["codebook"] == codebook
        assert response.context["sentence"] == example

    def test_expert_dialogue_view_get_as_annotator(self, client, project_setup):
        """Tests that an annotator is denied access to the expert dialogue view."""
        login = client.login(username="annotator1", password="123")
        assert login is True

        codebook = project_setup["codebook"]
        batch = project_setup["batch"]
        example = project_setup["example"]

        assert example is not None, "No suitable example with disagreement found in populatedb"

        url = reverse("expert-dialogue", args=[codebook.id, batch.id, example.id])
        response = client.get(url)

        assert response.status_code == 403

@pytest.mark.django_db
class TestSaveLabelsExpertView:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_setup):
        self.client = client
        self.client.login(username="expert1", password="123")

        self.example = project_setup["example"]
        self.batch = project_setup["batch"]
        self.codebook = project_setup["codebook"]
        self.url = reverse(
            "expert-label-save",
            args=[self.codebook.id, self.batch.id, self.example.id],
        )

    def test_post_correct_labels(self):
        assert not self.example.has_expert_decision
        labels = Label.objects.filter(project=self.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:2])

        response = self.client.post(self.url, data={"labels": label_ids})

        assert response.status_code == 302
        self.example.refresh_from_db()
        assert self.example.has_expert_decision
        expert_assignment = ExampleAssignment.objects.get(
            example=self.example,
            batch_assignment__user__username="expert1",
            batch_assignment__phase=Batch.Phase.EXPERT,
        )
        assert expert_assignment.annotations.count() == 2
        assert sorted(expert_assignment.annotations.values_list("label_id", flat=True)) == sorted(
            label_ids,
        )

    def test_post_no_labels_parameter(self):
        # Set some annotations first to test their removal
        labels = Label.objects.filter(project=self.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        response = self.client.post(self.url, data={"labels": label_ids})
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert self.example.has_expert_decision

        response = self.client.post(self.url, data={})
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert not self.example.has_expert_decision

    def test_post_empty_labels_list(self):
        # Set some annotations first to test their removal
        labels = Label.objects.filter(project=self.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        response = self.client.post(self.url, data={"labels": label_ids})
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert self.example.has_expert_decision

        response = self.client.post(self.url, data={"assignment_id": self.example.id, "labels": []})
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert not self.example.has_expert_decision

    def test_post_invalid_label_id(self):
        """
        The form is invalid, but the view logic proceeds and saves the annotation,
        ignoring the invalid label.
        """
        assert not self.example.has_expert_decision
        invalid_label_id = 9999
        response = self.client.post(
            self.url,
            data={"labels": [invalid_label_id]},
        )
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert not self.example.has_expert_decision

    def test_post_mixed_valid_and_invalid_label_ids(self):
        assert not self.example.has_expert_decision
        labels = Label.objects.filter(project=self.example.batch.project)
        valid_label_id = labels.first().id
        invalid_label_id = 9999
        response = self.client.post(
            self.url,
            data={
                "labels": [valid_label_id, invalid_label_id],
            },
        )
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert not self.example.has_expert_decision
        expert_assignment = ExampleAssignment.objects.get(
            example=self.example,
            batch_assignment__user__username="expert1",
            batch_assignment__phase=Batch.Phase.EXPERT,
        )
        assert expert_assignment.annotations.count() == 0

    def test_post_non_integer_label_id(self):
        with pytest.raises(ValueError):  # noqa: PT011
            self.client.post(
                self.url,
                data={"labels": ["not-a-number"]},
            )

    def test_post_wrong_parameter_name(self):
        # Set some annotations first to test they are not removed
        labels = Label.objects.filter(project=self.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        response = self.client.post(self.url, data={"labels": label_ids})
        assert response.status_code == 302
        self.example.refresh_from_db()
        assert self.example.has_expert_decision

        response = self.client.post(
            self.url,
            data={"wrong_labels": [1, 2]},
        )
        assert response.status_code == 302
        self.example.refresh_from_db()
        # The annotations are cleared because `getlist("labels")` is empty
        assert not self.example.has_expert_decision