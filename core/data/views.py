import logging

from data.models import Example
from codebook.models import Codebook
from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views.generic.edit import UpdateView


from data.models import Example
from data.models import ExampleAssignment
from core.mixins import ExpertRequiredMixin

from .forms import MultiLabelFormExpert


log = logging.getLogger(__name__)


class SaveLabelsExpert(ExpertRequiredMixin, UpdateView):
    def post(self, request, codebook_id, batch_id, example_id, *args, **kwargs):
        user = request.user
        example = get_object_or_404(Example, pk=example_id, batch=batch_id)
        assignment = ExampleAssignment.objects.filter(example=example, user=user).first()
        codebook = get_object_or_404(Codebook, pk=codebook_id)
        if not assignment:
            max_order = ExampleAssignment.objects.filter(
                user=user, example__batch=example.batch
            ).aggregate(models.Max("order", default=0))["order__max"]
            assignment = ExampleAssignment.objects.create(
                example=example, user=user, order=max_order + 1
            )
        form = MultiLabelFormExpert(request.POST, codebook=codebook, example=example, user=user)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Saved.")
        else:
            messages.error(self.request, f"Something was invalid: {form}")

        all_examples = Example.objects.filter(
            has_disagreement=True,
            has_disagreement_after_discussion=True,
            has_expert_decision=False,
            batch_id=batch_id,
            batch__project_id=codebook.project.id,
        ).order_by("id")
        next_example = all_examples.filter(id__gt=example.id).order_by("id").first()
        if next_example:
            return redirect("expert-dialogue", codebook_id, batch_id, next_example.id)
        else:
            return redirect("/")