import json
import logging
from typing import Any

from codebook.utils import normalize_content
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import View

from .forms import MultiLabelFormExpert
from .models import CodebookDraft
from core.mixins import BatchExpertRequiredMixin
from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from discuss.models import Message
from projects.models import BatchPhase

log = logging.getLogger(__name__)


def build_decision_metadata(example: Example, final_label_ids: list[str]) -> dict[str, Any]:
    """Collect the context of an expert decision to embed in the codebook commit."""
    batch = example.batch

    def labels_by_user(phase: BatchPhase) -> dict[str, list[str]]:
        assignments = (
            ExampleAssignment.objects.filter(batch=batch, example=example, phase=phase)
            .select_related("user")
            .prefetch_related("annotations__label")
            .order_by("user__username")
        )
        return {
            assignment.user.username: [
                annotation.label.name
                for annotation in assignment.annotations.all()
                if annotation.label
            ]
            for assignment in assignments
        }

    chat_history = [
        {
            "user": message.user,
            "message": message.message,
            "created_at": message.created_at.isoformat(),
        }
        for message in Message.objects.filter(example=example)
        .exclude(user="system")
        .order_by("created_at")
    ]

    final_decision = list(
        Label.objects.filter(
            id__in=[int(i) for i in final_label_ids if str(i).strip()],
        ).values_list("name", flat=True),
    )

    return {
        "text": example.content,
        "labels_before_discussion": labels_by_user(BatchPhase.ANNOTATION),
        "labels_after_discussion": labels_by_user(BatchPhase.DISCUSSION),
        "chat_history": chat_history,
        "final_decision": final_decision,
    }


def _assignment_context(assignment: ExampleAssignment) -> dict[str, Any]:
    """Pure context for one expert assignment; forms are built by the caller."""
    batch = assignment.batch
    example = assignment.example

    before_by_user = example.labels_by_user(BatchPhase.ANNOTATION)

    chat_messages = (
        Message.objects.filter(example=example).exclude(user="system").order_by("created_at")
    )

    expert_assignments = ExampleAssignment.objects.filter(
        batch=batch,
        user=assignment.user,
        phase=BatchPhase.EXPERT,
    )
    open_count = expert_assignments.filter(done__isnull=True).count()
    total_count = expert_assignments.count()

    return {
        "batch": batch,
        "batch_id": batch.id,
        "assignment": assignment,
        "example": example,
        "sentence": example,
        "prev_annotations": before_by_user,
        "post_annotations": example.labels_by_user(BatchPhase.DISCUSSION),
        # Presentational only (right-aligns this user's chat messages); an
        # example without annotation-phase assignments must not crash.
        "annotator": next(iter(before_by_user), None),
        "chat_messages": chat_messages,
        "disagreements_remaining": open_count,
        "disagreements_total": total_count,
        "disagreements_decided": total_count - open_count,
        "prev_assignment": assignment.previous(),
        "next_assignment": assignment.next(),
    }


def _codebook_panel_context(assignment: ExampleAssignment, mode: str = "view") -> dict[str, Any]:
    codebook = assignment.batch.project.codebook.get()
    draft = CodebookDraft.objects.filter(assignment=assignment).first()
    return {
        "assignment": assignment,
        "batch_id": assignment.batch_id,
        "codebook": codebook,
        "draft": draft,
        "panel_mode": mode,
        "panel_content": draft.content if draft else codebook.content,
        "draft_has_changes": bool(draft)
        and normalize_content(draft.content) != normalize_content(codebook.content),
    }


class _AssignmentAccessMixin(BatchExpertRequiredMixin):
    def get_assignment(self, request, batch_id, assignment_id):
        """Return the assignment or None when it isn't this expert's
        expert-phase assignment in this batch."""
        assignment = get_object_or_404(
            ExampleAssignment.objects.select_related("example", "batch", "batch__project"),
            pk=assignment_id,
        )
        allowed = (
            assignment.user_id == request.user.id
            and assignment.batch_id == batch_id
            and assignment.phase == BatchPhase.EXPERT
        )
        return assignment if allowed else None


class ExpertBatchView(BatchExpertRequiredMixin, View):
    """Entry point: redirect to the first open (or first) expert assignment."""

    def get(self, request, batch_id):
        assignments = ExampleAssignment.objects.filter(
            batch_id=batch_id,
            user=request.user,
            phase=BatchPhase.EXPERT,
        ).order_by("order", "id")
        assignment = assignments.filter(done__isnull=True).first() or assignments.first()
        if assignment is None:
            batch_project_id = (
                ExampleAssignment.objects.filter(batch_id=batch_id)
                .values_list("batch__project_id", flat=True)
                .first()
            )
            if batch_project_id is None:
                from projects.models import Batch

                batch = get_object_or_404(Batch, pk=batch_id)
                batch_project_id = batch.project_id
            return redirect("project-detail", project_id=batch_project_id)
        return redirect("expert-assignment", batch_id=batch_id, assignment_id=assignment.id)


class ExpertAssignmentView(_AssignmentAccessMixin, View):
    template_name = "expert/index.html"
    partial_name = "expert/partials/assignment.html"

    def _render(self, request, context, status=200):
        if request.htmx:
            return render(request, self.partial_name, context, status=status)
        return render(request, self.template_name, context, status=status)

    def _build_context(self, assignment, *, review, editing, labels_form=None):
        context = _assignment_context(assignment)
        context["review"] = review
        context["editing"] = editing
        if review:
            context["decision_annotations"] = list(
                assignment.annotations.select_related("label"),
            )
        else:
            context["labels_form"] = labels_form or MultiLabelFormExpert(assignment=assignment)
        context.update(_codebook_panel_context(assignment))
        return context

    def get(self, request, batch_id, assignment_id):
        assignment = self.get_assignment(request, batch_id, assignment_id)
        if assignment is None:
            return HttpResponseForbidden()

        editing = request.GET.get("edit") == "1" and assignment.done is not None
        review = assignment.done is not None and not editing
        context = self._build_context(assignment, review=review, editing=editing)
        return self._render(request, context)

    def post(self, request, batch_id, assignment_id):
        assignment = self.get_assignment(request, batch_id, assignment_id)
        if assignment is None:
            return HttpResponseForbidden()

        editing = request.POST.get("edit") == "1" and assignment.done is not None

        # Stale-tab guard: a completed decision can only be changed through
        # the explicit edit flow.
        if assignment.done is not None and not editing:
            messages.error(
                request,
                "This decision is already saved. Use 'Edit decision' to change it.",
            )
            context = self._build_context(assignment, review=True, editing=False)
            return self._render(request, context, status=409)

        labels_form = MultiLabelFormExpert(request.POST, assignment=assignment)
        if not labels_form.is_valid():
            log.debug(f"Invalid expert decision: {labels_form.errors}")
            messages.error(request, "Something was invalid")
            context = self._build_context(
                assignment,
                review=False,
                editing=editing,
                labels_form=labels_form,
            )
            return self._render(request, context)

        codebook = assignment.batch.project.codebook.get()
        draft = CodebookDraft.objects.filter(assignment=assignment).first()
        if draft and normalize_content(draft.content) == normalize_content(codebook.content):
            # Nothing actually changed; drop the stale draft silently.
            draft.delete()
            draft = None

        # Draft prechecks happen BEFORE anything is persisted, so a rejected
        # submission never half-saves.
        if draft:
            if not draft.rationale.strip():
                messages.error(
                    request,
                    "The codebook was changed: a rationale is required before saving.",
                )
                context = self._build_context(
                    assignment,
                    review=False,
                    editing=editing,
                    labels_form=labels_form,
                )
                return self._render(request, context)
            if draft.base_revision != codebook.repo.head.commit.hexsha:
                messages.error(
                    request,
                    "The codebook changed since this draft was started. "
                    "Review your draft against the current version.",
                )
                context = self._build_context(
                    assignment,
                    review=False,
                    editing=editing,
                    labels_form=labels_form,
                )
                return self._render(request, context)

        previous_decision = None
        if editing:
            previous_decision = sorted(
                annotation.label.name
                for annotation in assignment.annotations.select_related("label")
                if annotation.label
            )

        labels_form.save()

        metadata = build_decision_metadata(
            assignment.example,
            labels_form.cleaned_data["labels"],
        )
        if editing:
            # Append-only decision log: the original commit is never
            # rewritten, a revision entry supersedes it.
            metadata["revises"] = True
            metadata["previous_decision"] = previous_decision

        if draft:
            commit_info = {"rationale": draft.rationale, **metadata}
            codebook.save(
                content=draft.content,
                commit_message=json.dumps(commit_info, ensure_ascii=False),
            )
            draft.delete()
        elif editing:
            commit_info = {"rationale": "", **metadata}
            codebook.commit_decision_revision(json.dumps(commit_info, ensure_ascii=False))

        messages.success(request, "Saved.")

        batch = assignment.batch
        has_open_assignments = ExampleAssignment.objects.filter(
            batch=batch,
            user=request.user,
            phase=BatchPhase.EXPERT,
            done__isnull=True,
        ).exists()
        if not has_open_assignments and batch.current_phase != BatchPhase.FINAL:
            batch.set_phase(BatchPhase.FINAL)

        # An edit returns to review of the same assignment; a normal save
        # advances to the next open assignment.
        if editing:
            target = assignment
            target_url = reverse(
                "expert-assignment",
                kwargs={"batch_id": batch.id, "assignment_id": assignment.id},
            )
        else:
            target = (
                ExampleAssignment.objects.filter(
                    batch=batch,
                    user=request.user,
                    phase=BatchPhase.EXPERT,
                    done__isnull=True,
                )
                .order_by("order", "id")
                .first()
            )
            target_url = (
                reverse(
                    "expert-assignment",
                    kwargs={"batch_id": batch.id, "assignment_id": target.id},
                )
                if target
                else reverse("expert-batch", kwargs={"batch_id": batch.id})
            )

        if request.htmx:
            if target is None:
                context = {"assignment": None, "batch": batch, "batch_id": batch.id}
            else:
                review = target.done is not None
                context = self._build_context(target, review=review, editing=False)
            response = render(request, self.partial_name, context)
            response["HX-Push-Url"] = target_url
            return response

        if target is None:
            return redirect("project-detail", project_id=batch.project_id)
        return redirect(target_url)


class CodebookPanelView(_AssignmentAccessMixin, View):
    """Swap the codebook panel between view and edit mode (server-rendered)."""

    def get(self, request, batch_id, assignment_id):
        assignment = self.get_assignment(request, batch_id, assignment_id)
        if assignment is None:
            return HttpResponseForbidden()
        mode = "edit" if request.GET.get("mode") == "edit" else "view"
        context = _codebook_panel_context(assignment, mode=mode)
        return render(request, "expert/partials/codebook_panel.html", context)


class CodebookDraftSaveView(_AssignmentAccessMixin, View):
    def post(self, request, batch_id, assignment_id):
        assignment = self.get_assignment(request, batch_id, assignment_id)
        if assignment is None:
            return HttpResponseForbidden()

        content = request.POST.get("content", "")
        rationale = request.POST.get("rationale", "")
        codebook = assignment.batch.project.codebook.get()

        if not normalize_content(content):
            messages.error(request, "The codebook cannot be emptied.")
            context = _codebook_panel_context(assignment, mode="edit")
            return render(request, "expert/partials/codebook_panel.html", context)

        if normalize_content(content) == normalize_content(codebook.content):
            # Saving an unchanged codebook equals discarding the draft.
            CodebookDraft.objects.filter(assignment=assignment).delete()
        else:
            CodebookDraft.objects.update_or_create(
                assignment=assignment,
                defaults={"content": content, "rationale": rationale},
                create_defaults={
                    "content": content,
                    "rationale": rationale,
                    "base_revision": codebook.repo.head.commit.hexsha,
                },
            )

        context = _codebook_panel_context(assignment, mode="view")
        return render(request, "expert/partials/codebook_panel.html", context)


class CodebookDraftDeleteView(_AssignmentAccessMixin, View):
    def post(self, request, batch_id, assignment_id):
        assignment = self.get_assignment(request, batch_id, assignment_id)
        if assignment is None:
            return HttpResponseForbidden()
        CodebookDraft.objects.filter(assignment=assignment).delete()
        context = _codebook_panel_context(assignment, mode="view")
        return render(request, "expert/partials/codebook_panel.html", context)
