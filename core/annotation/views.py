import logging

from django.contrib import messages
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView
from django.views.generic import View

from core.mixins import BatchAnnotatorRequiredMixin
from data.forms import MultiLabelForm
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import ProjectRole
from projects.models.batch import BatchUser

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


def _next_unfinished_with_wraparound(assignment):
    nxt = assignment.next(skip_annotated=True)
    if nxt is not None:
        return nxt
    return (
        ExampleAssignment.objects.filter(
            batch=assignment.batch,
            user=assignment.user,
            phase=assignment.phase,
            done__isnull=True,
        )
        .exclude(id=assignment.id)
        .order_by("order")
        .first()
    )


def _annotation_panel_context(batch, assignment, skip_annotated: bool = False):
    prev_assignment = assignment.previous(skip_annotated=skip_annotated)
    next_assignment = assignment.next(skip_annotated=skip_annotated)
    qs = "?skip_annotated=1" if skip_annotated else ""

    context = {
        "batch": batch,
        "assignment": assignment,
        "assignment_id": assignment.id,
        "example": assignment.example,
        "label_form": MultiLabelForm(assignment=assignment),
        "skip_annotated": skip_annotated,
        "has_prev": bool(prev_assignment),
        "has_next": bool(next_assignment),
        "post_url": reverse(
            "annotate-assignment",
            kwargs={"batch_id": batch.id, "assignment_id": assignment.id},
        )
        + qs,
        "prev_url": (
            reverse(
                "annotate-assignment",
                kwargs={"batch_id": batch.id, "assignment_id": prev_assignment.id},
            )
            + qs
            if prev_assignment
            else ""
        ),
        "next_url": (
            reverse(
                "annotate-assignment",
                kwargs={"batch_id": batch.id, "assignment_id": next_assignment.id},
            )
            + qs
            if next_assignment
            else ""
        ),
    }

    return context


class AnnotateView(BatchAnnotatorRequiredMixin, DetailView):
    template_name = "annotation/index.html"
    model = Batch

    def _get_batch(self, request, batch_id: int) -> Batch:
        batch = Batch.objects.prefetch_related("users").get(id=batch_id)
        if request.user not in batch.users.all():
            raise PermissionError
        return batch

    def _get_assignment(self, request, batch: Batch, assignment_id: int) -> ExampleAssignment:
        assignment = get_object_or_404(ExampleAssignment, id=assignment_id)
        if assignment.user != request.user or assignment.example.batch_id != batch.id:
            raise PermissionError
        # The annotation UI must only ever touch annotation-phase assignments;
        # saving here against e.g. a discussion assignment would overwrite
        # labels of a later phase.
        if assignment.phase != BatchPhase.ANNOTATION:
            raise PermissionError
        return assignment

    def _render_assignment(self, request, batch: Batch, assignment: ExampleAssignment):
        skip_annotated = request.GET.get("skip_annotated") == "1"
        context = _annotation_panel_context(batch, assignment, skip_annotated=skip_annotated)
        context["progress"] = get_progress(request.user, batch)

        if context["has_next"] and context["progress"]["done"] >= context["progress"]["total"]:
            redirect("annotate-done", batch_id=batch.id)

        if request.htmx:
            return render(request, "annotation/panel.html", context)

        codebook = batch.project.codebook.get()
        context.update(codebook.get_as_context(batch.batch_number))
        return render(request, "annotation/index.html", context)

    def get(
        self,
        request,
        batch_id,
        assignment_id: int | None = None,
    ):
        try:
            batch = self._get_batch(request, batch_id)
        except PermissionError:
            return HttpResponseForbidden()

        if assignment_id:
            try:
                assignment = self._get_assignment(request, batch, assignment_id)
            except PermissionError:
                return HttpResponseForbidden()

            skip_annotated = request.GET.get("skip_annotated") == "1"
            if skip_annotated and assignment.done is not None:
                target = _next_unfinished_with_wraparound(assignment)
                if target is None:
                    return redirect("annotate-done", batch_id=batch.id)
                return redirect(
                    reverse(
                        "annotate-assignment",
                        kwargs={"batch_id": batch.id, "assignment_id": target.id},
                    )
                    + "?skip_annotated=1",
                )
        else:
            assignment = (
                ExampleAssignment.objects.filter(
                    user=request.user,
                    example__batch=batch,
                    phase=BatchPhase.ANNOTATION,
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

        return self._render_assignment(request, batch, assignment)

    def post(self, request, batch_id, assignment_id: int | None = None):
        if assignment_id is None:
            return HttpResponse(status=400)

        try:
            batch = self._get_batch(request, batch_id)
            assignment = self._get_assignment(request, batch, assignment_id)
        except PermissionError:
            return HttpResponseForbidden()

        form = MultiLabelForm(request.POST, assignment=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
        else:
            messages.error(request, f"Something was invalid: {form}")

        skip_annotated = request.GET.get("skip_annotated") == "1"
        progress = get_progress(request.user, batch)
        if skip_annotated:
            next_assignment = _next_unfinished_with_wraparound(assignment)
        else:
            next_assignment = assignment.next()
        if not next_assignment and progress["done"] >= progress["total"]:
            return redirect("annotate-done", batch_id=batch.id)

        context = _annotation_panel_context(batch, next_assignment, skip_annotated=skip_annotated)
        context["progress"] = progress

        push_url = reverse(
            "annotate-assignment",
            kwargs={"batch_id": batch.id, "assignment_id": next_assignment.id},
        )
        if skip_annotated:
            push_url += "?skip_annotated=1"

        if request.htmx:
            resp = render(request, "annotation/panel.html", context, status=200)
            resp["HX-Push-Url"] = push_url
            return resp
        return redirect(push_url)


class AnnotationDoneView(BatchAnnotatorRequiredMixin, View):
    def _context(self, request, batch):
        batch_user = BatchUser.objects.filter(batch=batch, user=request.user).first()
        return {
            "batch": batch,
            "project": batch.project,
            "progress": get_progress(request.user, batch),
            "finalized": batch_user is not None and batch_user.finalized_at is not None,
            "finalized_count": BatchUser.objects.filter(
                batch=batch,
                role=ProjectRole.ANNOTATOR,
                finalized_at__isnull=False,
            ).count(),
            "annotator_count": batch.assignees(role=ProjectRole.ANNOTATOR).count(),
            "phase_advanced": batch.current_phase != BatchPhase.ANNOTATION,
        }

    def get(self, request, batch_id):
        batch = Batch.objects.get(id=batch_id)
        return render(request, "annotation/done.html", self._context(request, batch))

    def post(self, request, batch_id):
        batch = Batch.objects.get(id=batch_id)
        progress = get_progress(request.user, batch)
        done = progress["done"] >= progress["total"]
        if done and batch.current_phase == BatchPhase.ANNOTATION:
            BatchUser.objects.filter(
                batch=batch,
                user=request.user,
                finalized_at__isnull=True,
            ).update(finalized_at=timezone.now())
            batch.advance_from_annotation_if_finalized()
        return redirect("annotate-done", batch_id=batch.id)
