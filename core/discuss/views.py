from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.views.generic import View

from core.mixins import AnnotatorRequiredMixin
from data.models import ExampleAssignment


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
    def post(self, request, batch_id):  # noqa: ARG002
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))

    def get(self, request, batch_id):
        return render(request, "discuss/index.html", {"batch_id": batch_id})
