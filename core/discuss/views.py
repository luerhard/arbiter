from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.views.generic import View

from core.mixins import AnnotatorRequiredMixin
from data.models import ExampleAssignment
from projects.models import Batch


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
        context["content"] = codebook.content
        context["content_diff"] = codebook.diff(batch.batch_number - 1, batch.batch_number)

        return render(request, "discuss/index.html", context)
