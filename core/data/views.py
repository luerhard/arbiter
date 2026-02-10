import logging

from codebook.models import Codebook
from django.contrib import messages
from django.db import models
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views.generic.edit import UpdateView

from .forms import MultiLabelFormExpert
from core.mixins import ExpertRequiredMixin
from data.models import Example
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import ProjectUser

log = logging.getLogger(__name__)


class SaveLabelsExpert(ExpertRequiredMixin, UpdateView):
    def post(self, request, codebook_id, batch_id, example_id):
        user = request.user
        batch = get_object_or_404(Batch, pk=batch_id)
        example = get_object_or_404(Example, pk=example_id, batch=batch_id)
        assignment = ExampleAssignment.objects.filter(
            example=example,
            batch_assignment__user=user,
        ).first()
        codebook = get_object_or_404(Codebook, pk=codebook_id)
        if not assignment:
            if not BatchAssignment.objects.filter(
                batch=batch,
                user=user,
                role=ProjectUser.Role.EXPERT,
            ).exists():
                return HttpResponseForbidden("You are not assigned to this batch.")

            batch_assignment = BatchAssignment.objects.get(
                batch=batch,
                user=user,
                role=ProjectUser.Role.EXPERT,
            )
            max_order = ExampleAssignment.objects.filter(
                batch_assignment__user=user,
                example__batch=example.batch,
            ).aggregate(models.Max("order", default=0))["order__max"]
            assignment = ExampleAssignment.objects.create(
                example=example,
                batch_assignment=batch_assignment,
                order=max_order + 1,
                phase=Batch.Phase.EXPERT,
            )
        form = MultiLabelFormExpert(request.POST, codebook=codebook, example=example, user=user)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Saved.")
        else:
            messages.error(self.request, f"Something was invalid: {form}")

        all_examples = [
            e
            for e in Example.objects.filter(
                batch_id=batch_id,
                batch__project_id=codebook.project.id,
            ).order_by("id")
            if e.has_disagreement
            and e.has_disagreement_after_discussion
            and not e.has_expert_decision
        ]
        next_example = next((e for e in all_examples if e.id > example.id), None)
        if next_example:
            return redirect("expert-dialogue", codebook_id, batch_id, next_example.id)
        else:
            batch.set_phase(Batch.Phase.FINAL)

            return redirect("project-detail", codebook.project.id)
