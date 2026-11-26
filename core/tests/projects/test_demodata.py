from django.core.management import call_command
import pytest

from projects.management.commands.demodata import CLASSIFICATION
from projects.management.commands.demodata import SPANS
from projects.models import BatchPhase
from projects.models import Project


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stage", "phase"),
    [
        ("annotation", BatchPhase.ANNOTATION),
        ("discussion", BatchPhase.DISCUSSION),
        ("expert", BatchPhase.EXPERT),
        ("final", BatchPhase.FINAL),
    ],
)
def test_demodata_has_one_batch_in_progress_per_project(stage, phase):
    call_command("demodata", stage=stage)
    call_command("demodata", stage=stage)  # again: replaces, does not add

    project = Project.objects.get(name=CLASSIFICATION)
    phases = list(project.batches.order_by("batch_number").values_list("current_phase", flat=True))
    assert phases == [BatchPhase.FINAL, phase]
    # the expert's decision in batch 1 changed the codebook
    assert "so-called experts" in project.codebook.get().content
    # the span project's only batch has got as far
    assert Project.objects.get(name=SPANS).batches.get().current_phase == phase
