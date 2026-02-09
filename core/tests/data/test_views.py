from codebook.models import Codebook
from django.contrib.auth import get_user_model
from django.shortcuts import reverse
import pytest

from data.models import Annotation
from data.models import Example

User = get_user_model()


@pytest.fixture
def data_setup():
    """
    Fixture to provide data for expert view tests.
    Finds an example that is ready for expert decision from the populatedb data.
    """
    example = next(
        (
            e
            for e in Example.objects.all()
            if e.has_disagreement
            and e.has_disagreement_after_discussion
            and not e.has_expert_decision
        ),
        None,
    )
    assert example is not None, "No suitable example for expert decision found in populatedb"

    return {
        "example": example,
        "batch": example.batch,
        "codebook": Codebook.objects.get(project=example.batch.project),
        "labels": example.batch.project.labels.all(),
    }


@pytest.mark.django_db
class TestDataViews:
    def test_save_labels_expert_requires_login(self, client, data_setup):
        url = reverse(
            "expert-label-save",
            kwargs={
                "codebook_id": data_setup["codebook"].id,
                "batch_id": data_setup["batch"].id,
                "example_id": data_setup["example"].id,
            },
        )
        data = {"labels": [data_setup["labels"].first().id]}
        response = client.post(url, data)
        assert response.status_code == 302

    def test_save_labels_expert_view(self, client, data_setup):
        client.login(username="expert1", password="123")
        example = data_setup["example"]
        assert example.has_expert_decision is False

        url = reverse(
            "expert-label-save",
            kwargs={
                "codebook_id": data_setup["codebook"].id,
                "batch_id": data_setup["batch"].id,
                "example_id": example.id,
            },
        )
        label_ids = [label.id for label in data_setup["labels"]]
        data = {"labels": label_ids}

        response = client.post(url, data)

        assert response.status_code == 302  # Redirects
        for label_id in label_ids:
            assert Annotation.objects.filter(
                assignment__example=example,
                label_id=label_id,
            ).exists()

        example.refresh_from_db()
        assert example.has_expert_decision is True

    def test_save_labels_expert_annotator_access_denied(self, client, data_setup):
        client.login(username="annotator1", password="123")
        url = reverse(
            "expert-label-save",
            kwargs={
                "codebook_id": data_setup["codebook"].id,
                "batch_id": data_setup["batch"].id,
                "example_id": data_setup["example"].id,
            },
        )
        data = {"labels": [data_setup["labels"].first().id]}
        response = client.post(url, data)
        assert response.status_code == 403
