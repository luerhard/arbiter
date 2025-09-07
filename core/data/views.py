import logging

from codebook.models import Codebook
from django.db import models
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect

from data.models import Example
from data.models import ExampleAssignment

log = logging.getLogger(__name__)


def expert_save_labels(request, codebook_id, batch_id, example_id):
    if request.method != "POST":
        return
    user = request.user
    example = get_object_or_404(Example, pk=example_id, batch=batch_id)
    assignment = ExampleAssignment.objects.filter(example=example, user=user).first()
    codebook = get_object_or_404(Codebook, pk=codebook_id)
    project = codebook.project
    if not assignment:
        max_order = ExampleAssignment.objects.filter(
            user=user, example__batch=example.batch
        ).aggregate(models.Max("order", default=0))["order__max"]
        assignment = ExampleAssignment.objects.create(
            example=example, user=user, order=max_order + 1
        )
    label_ids = [int(i) for i in request.POST.getlist("selected_labels") if i.strip()]
    assignment.set_user_annotations(label_ids=label_ids, phase="EXPERT")

    all_examples = Example.objects.filter(
        has_disagreement=True,
        has_disagreement_after_discussion=True,
        has_expert_decision=False,
        batch_id=batch_id,
        batch__project_id=project.id,
    ).order_by("id")
    next_example = all_examples.filter(id__gt=example.id).order_by("id").first()
    if next_example:
        return redirect("expert-dialogue", codebook_id, batch_id, next_example.id)
    else:
        return redirect("/")
