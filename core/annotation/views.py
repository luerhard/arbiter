import json
import logging

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic import View

from core.mixins import AnnotatorRequiredMixin
from data.forms import MultiLabelFormAnnotation
from data.models import ExampleAssignment
from projects.models import Batch

log = logging.getLogger(__name__)


class AnnotateView(AnnotatorRequiredMixin, DetailView):
    template_name = "annotation/index.html"
    model = Batch

    def get(
        self,
        request,
        batch_id,
        assignment_id: int | None = None,
    ):
        batch = Batch.objects.get(id=batch_id)

        if assignment_id:
            assignment = ExampleAssignment.objects.get(id=assignment_id)
        else:
            assignment = (
                ExampleAssignment.objects
                .filter(batch_assignment__user=request.user, example__batch=batch)
                .order_by("order")
                .first()
            )
        progress = get_progress(request.user, batch)
        if not assignment or progress["done"] >= progress["total"]:
            return redirect("annotate-done", batch_id=batch.id)

        context = {}
        context["assignment_id"] = assignment.id
        codebook = batch.project.codebook.get()
        context.update(codebook.get_as_context(batch.batch_number))

        response = render(request, "annotation/index.html", context)
        response["HX-Trigger"] = json.dumps(
            {"annotation-updated": {"assignment_id": assignment.id}},
        )

        return response


class EditAssignment(View):
    def get(self, request):  # noqa: ARG002
        assignment_id = request.GET.get("assignment_id")
        if assignment_id:
            assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
            submitted_labels = [int(i) for i in self.request.POST.getlist("labels") if i.strip()]
            assignment.set_user_annotations(label_ids=submitted_labels, phase="ANNOTATION")

            payload = {"assignment_id": assignment.pk}
        else:
            msg = "ass"
            raise Exception(msg)

        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({"annotation-updated": payload})
        return resp

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        assignment_id = request.POST.get("assignment_id")
        assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
        form = MultiLabelFormAnnotation(request.POST, assignment=assignment)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Saved.")
        else:
            messages.error(self.request, f"Something was invalid: {form}")

        batch = assignment.example.batch
        submitted_labels = [int(i) for i in self.request.POST.getlist("labels") if i.strip()]
        assignment.set_user_annotations(label_ids=submitted_labels, phase="ANNOTATION")

        next_assignment = assignment.next()
        if not next_assignment:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = reverse("annotate-done", kwargs={"batch_id": batch.id})
            return resp

        payload = {"assignment_id": next_assignment.pk, "batch_id": batch.id}
        resp = HttpResponse(status=204)
        resp["HX-Trigger"] = json.dumps({"annotation-updated": payload})
        return resp


class AnnotationDoneView(AnnotatorRequiredMixin, View):
    def get(self, request, batch_id):
        batch = Batch.objects.get(id=batch_id)
        context = {
            "batch": batch,
            "project": batch.project,
            "progress": get_progress(request.user, batch),
        }
        return render(request, "annotation/done.html", context)


def get_progress(user, batch):
    """helper function to calculate current progress"""
    done = (
        batch.examples
        .filter(
            assignments__batch_assignment__user=user,
            assignments__phase=Batch.Phase.ANNOTATION,
            assignments__done__isnull=False,
        )
        .distinct()
        .count()
    )
    total = batch.examples.count()
    try:
        current = int(done / total * 100)
    except ZeroDivisionError:
        current = 100

    return {"done": done, "total": total, "current": current}


class HtmxPbar(View):
    def get(self, request):
        assignment_id = request.GET.get("assignment_id")
        if assignment_id:
            assignment = ExampleAssignment.objects.get(id=assignment_id)
            ctx = {
                "progress": get_progress(request.user, assignment.example.batch),
            }
        else:
            ctx = {"progress": 0}
        return render(request, "annotation/partials/pbar.html", ctx)


class HtmxSentence(View):
    def get(self, request):
        assignment_id = request.GET.get("assignment_id")
        context = {}
        if assignment_id:
            assignment = ExampleAssignment.objects.get(id=assignment_id)
            context["example"] = assignment.example

        return render(request, "annotation/partials/sentence.html", context)


class HtmxLabels(View):
    def get(self, request):
        assignment_id = request.GET.get("assignment_id")
        context = {}
        if assignment_id:
            assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
            previous_annotations = assignment.annotations.select_related("label").all()

            example = assignment.example
            labels = []
            for label in example.labels.all():
                new = {
                    "name": label.name,
                    "id": label.id,
                }
                if label in previous_annotations:
                    new["is_set"] = True
                else:
                    new["is_set"] = False
                labels.append(new)
            context["labels"] = labels

            form = MultiLabelFormAnnotation(assignment=assignment)
            context["label_form"] = form

        return render(request, "annotation/partials/labels.html", context)


class HtmxNavBlock(View):
    def get(self, request):
        assignment_id = request.GET.get("assignment_id")
        context = {}
        if assignment_id:
            a = ExampleAssignment.objects.get(id=assignment_id)
            ctx = {
                "assignment_id": a.id,
                "has_prev": bool(a.previous()),
                "has_next": bool(a.next()),
            }
            context.update(ctx)
        return render(request, "annotation/partials/nav.html", context)


class PrevSentence(AnnotatorRequiredMixin, View):
    def get(self, request):
        skip_annotated = request.GET.get("filter") == "unfinished"
        assignment_id = request.GET.get("assignment_id")

        current = ExampleAssignment.objects.get(id=assignment_id)
        nxt = current.previous(skip_annotated=skip_annotated) or current

        resp = HttpResponse(
            f'<input id="assignmentId" name="assignment_id" value="{nxt.id}" '
            'hx-swap-oob="true" hidden>',
            status=200,
        )
        resp["HX-Trigger"] = json.dumps({"annotation-updated": {"assignment_id": nxt.id}})
        return resp


class NextSentence(AnnotatorRequiredMixin, View):
    def get(self, request):
        skip_annotated = request.GET.get("filter") == "unfinished"
        assignment_id = request.GET.get("assignment_id")

        current = ExampleAssignment.objects.get(id=assignment_id)
        nxt = current.next(skip_annotated=skip_annotated) or current

        payload = {
            "assignment_id": nxt.id,
            "has_next": bool(nxt.next(skip_annotated=skip_annotated)),
            "has_prev": bool(nxt.previous(skip_annotated=skip_annotated)),
        }

        resp = HttpResponse(
            f'<input id="assignmentId" name="assignment_id" value="{nxt.id}" '
            'hx-swap-oob="true" hidden>',
            status=200,
        )
        resp["HX-Trigger"] = json.dumps({"annotation-updated": payload})
        return resp
