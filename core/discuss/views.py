import logging

from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.views.generic import View

from core.mixins import BatchAnnotatorRequiredMixin
from projects.models import Batch

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
        context["batch"] = batch

        codebook = batch.project.codebook.get()
        context.update(codebook.get_as_context(batch.batch_number))

        return render(request, "discuss/index.html", context)
