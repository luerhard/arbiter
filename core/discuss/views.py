import logging

from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.views.generic import View

from core.mixins import AnnotatorRequiredMixin
from data.models import ExampleAssignment
from projects.models import Batch


log = logging.getLogger(__name__)


class GetProgress(AnnotatorRequiredMixin, View):
    def get(self, request, batch_id):
        query = ExampleAssignment.objects.filter(
            example__batch=batch_id,
            example__has_disagreement=True,
            user=request.user,
        )
        context = {}
        context["batch_id"] = batch_id
        context["done"] = query.filter(is_discussed=True).count()
        context["total"] = query.count()
        try:
            context["progress"] = int(context["done"] / context["total"] * 100)
        except ZeroDivisionError:
            context["progress"] = 100

        return render(request, "discuss/index.html#pbar", context)


class HtmxPbar(View):
    def get(self, request):
        log.debug(f"{list(request.GET.items()) = }")
        assignment_id = request.GET.get("assignment_id")

        if assignment_id:
            ctx = {
                # TODO: get the actual progress
                "progress": 2,# get_progress(request.user, assignment.example.batch),
            }
        else:
            ctx = {"progress": 0}
        return render(request, "discuss/partials/pbar.html", ctx)


class DiscussView(AnnotatorRequiredMixin, View):
    template_name = "annotation/index.html"
    model = Batch

    def post(self, request, batch_id):  # noqa: ARG002
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))

    def get(self, request, batch_id):
        context = {}
        context["batch_id"] = batch_id

        batch = Batch.objects.get(id=batch_id)

        codebook = batch.project.codebook.get()
        context.update(codebook.get_as_context(batch.batch_number))

        return render(request, "discuss/index.html", context)
