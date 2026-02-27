import json
import logging

from django.contrib import messages
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic import View

from core.mixins import AnnotatorRequiredMixin
from data.forms import MultiLabelForm
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchPhase

log = logging.getLogger(__name__)


def get_progress(user, batch):
    """helper function to calculate current progress"""
    all_assignments = batch.assignments.filter(user=user, phase=BatchPhase.ANNOTATION)
    done = all_assignments.filter(done__isnull=False).count()
    total = all_assignments.count()
    try:
        current = int(done / total * 100)
    except ZeroDivisionError:
        current = 100

    return {"done": done, "total": total, "current": current}


def _annotation_panel_context(request, batch, assignment):
    prev_assignment = assignment.previous()
    next_assignment = assignment.next()

    context = {
        "batch": batch,
        "assignment_id": assignment.id,
        "progress": get_progress(request.user, batch),
        "example": assignment.example,
        "label_form": MultiLabelForm(phase=BatchPhase.ANNOTATION, assignment=assignment),
        "has_prev": bool(prev_assignment),
        "has_next": bool(next_assignment),
        "prev_url": (
            reverse(
                "annotate-assignment",
                kwargs={"batch_id": batch.id, "assignment_id": prev_assignment.id},
            )
            if prev_assignment
            else ""
        ),
        "next_url": (
            reverse(
                "annotate-assignment",
                kwargs={"batch_id": batch.id, "assignment_id": next_assignment.id},
            )
            if next_assignment
            else ""
        ),
    }

    return context


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

        progress = get_progress(request.user, batch)
        if progress["done"] >= progress["total"]:
            return redirect("annotate-done", batch_id=batch.id)

        if assignment_id:
            assignment = ExampleAssignment.objects.get(id=assignment_id)
            if assignment.user != request.user or assignment.example.batch_id != batch.id:
                return HttpResponseForbidden()
        else:
            assignment = (
                ExampleAssignment.objects.filter(
                    user=request.user,
                    example__batch=batch,
                )
                .order_by("order")
                .first()
            )
            if not assignment:
                return redirect("annotate-done", batch_id=batch.id)
            return redirect(
                "annotate-assignment",
                batch_id=batch.id,
                assignment_id=assignment.id,
            )

        context = _annotation_panel_context(request, batch, assignment)

        if request.headers.get("HX-Request") == "true":
            return render(request, "annotation/panel.html", context)
        codebook = batch.project.codebook.get()
        context.update(codebook.get_as_context(batch.batch_number))
        return render(request, "annotation/index.html", context)


class EditAssignment(View):
    def get(self, request):  # noqa: ARG002
        assignment_id = request.GET.get("assignment_id")
        if assignment_id:
            assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
            if assignment.user != request.user:
                return HttpResponseForbidden()
            submitted_labels = [int(i) for i in self.request.POST.getlist("labels") if i.strip()]
            assignment.set_user_annotations(label_ids=submitted_labels)

            payload = {"assignment_id": assignment.pk}
        else:
            msg = "No assignment id found in request"
            raise Exception(msg)

        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({"annotation-updated": payload})
        return resp

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        assignment_id = request.POST.get("assignment_id")
        assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
        if assignment.user != request.user:
            return HttpResponseForbidden()
        form = MultiLabelForm(request.POST, assignment=assignment, phase=BatchPhase.ANNOTATION)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Saved.")
        else:
            messages.error(self.request, f"Something was invalid: {form}")
            submitted_labels = [int(i) for i in self.request.POST.getlist("labels") if i.strip()]
            assignment.set_user_annotations(label_ids=submitted_labels)

        batch = assignment.example.batch
        next_assignment = assignment.next()
        if not next_assignment:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = reverse("annotate-done", kwargs={"batch_id": batch.id})
            return resp

        batch = next_assignment.example.batch
        context = _annotation_panel_context(request, batch, next_assignment)
        resp = render(request, "annotation/panel.html", context, status=200)
        resp["HX-Push-Url"] = reverse(
            "annotate-assignment",
            kwargs={"batch_id": batch.id, "assignment_id": next_assignment.id},
        )
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


# class HtmxLabels(View):
#     def get(self, request):
#         assignment_id = request.GET.get("assignment_id")
#         context = {}
#         if assignment_id:
#             assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
#             if assignment.user != request.user:
#                 return HttpResponseForbidden()
#             previous_annotations = assignment.annotations.select_related("label").all()

#             example = assignment.example
#             labels = []
#             for label in example.labels.all():
#                 new = {
#                     "name": label.name,
#                     "id": label.id,
#                 }
#                 if label in previous_annotations:
#                     new["is_set"] = True
#                 else:
#                     new["is_set"] = False
#                 labels.append(new)
#             context["labels"] = labels

#             form = MultiLabelForm(phase=BatchPhase.ANNOTATION, assignment=assignment)
#             context["label_form"] = form

#         return render(request, "annotation/partials/labels.html", context)
