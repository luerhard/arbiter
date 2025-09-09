from codebook.models import Codebook
from django.shortcuts import reverse
import pytest

from data.models import Example


@pytest.fixture
def project_setup():
    # Assumes populatedb creates at least one project, batch, example, and label
    # and that the example has disagreement for the expert view to work.
    example = Example.objects.filter(
        has_disagreement=True, has_disagreement_after_discussion=True
    ).first()

    return {
        "batch": example.batch,
        "example": example,
        "codebook": Codebook.objects.filter(project=example.batch.project).first(),
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("populatedb")
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
