import logging

from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.views.generic import View

from core.mixins import BatchAnnotatorRequiredMixin
from projects.models import Batch
from projects.models import BatchPhase

log = logging.getLogger(__name__)


class DiscussView(BatchAnnotatorRequiredMixin, View):
    template_name = "annotation/index.html"
    model = Batch

    def post(self, request, batch_id):  # noqa: ARG002
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))

    def get(self, request, batch_id):
        context = {}
        context["batch_id"] = batch_id

        batch = Batch.objects.select_related("project").get(id=batch_id)
        if batch.current_phase != BatchPhase.DISCUSSION:
            messages.info(request, "This batch is not in the discussion phase.")
            return redirect("project-detail", batch.project_id)
        context["batch"] = batch

        codebook = batch.project.codebook.get()
        # the annotators last worked on this batch: what changed since it started
        context.update(codebook.get_as_context(batch.batch_number))

        return render(request, "discuss/index.html", context)
