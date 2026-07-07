import logging
from typing import Any

from codebook.forms import CodebookForm
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.generic.detail import DetailView

from .forms import MultiLabelFormExpert
from core.mixins import ExpertRequiredMixin
from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from discuss.models import Message
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import ProjectUser

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


def build_dialog_context(
    batch: Batch,
    user: ProjectUser,
    labels_form: MultiLabelFormExpert,
    codebook_form: CodebookForm,
) -> dict[str, Any]:
    project = batch.project
    context = {
        "batch_id": batch.id,
        "codebook": project.codebook.get(),
        "labels": project.labels.all(),
        "success": True,
        "labels_form": labels_form,
        "codebook_form": codebook_form,
    }

    open_assignments = ExampleAssignment.objects.filter(
        example__in=batch.disagreements(BatchPhase.DISCUSSION),
        user=user,
        phase=BatchPhase.EXPERT,
        done__isnull=True,
    ).select_related("example")

    current_assignment = open_assignments.first()
    if not current_assignment:
        context["disagreements_remaining"] = 0
        context["assignment"] = None
        context["sentence"] = None
        context["next_example"] = None
        context["prev_annotations"] = {}
        context["annotator"] = None
        context["post_annotations"] = {}
        context["chat_messages"] = []
        return context

    current_example = current_assignment.example
    before_assignments = (
        ExampleAssignment.objects.filter(
            batch=batch,
            example=current_example,
            phase=BatchPhase.ANNOTATION,
        )
        .select_related("user")
        .prefetch_related("annotations__label")
        .order_by("user__username")
    )
    before_by_user = {a.user.username: list(a.annotations.all()) for a in before_assignments}
    # Presentational only (right-aligns this user's chat messages); an example
    # without annotation-phase assignments must not crash the dialogue.
    context["annotator"] = next(iter(before_by_user), None)

    after_assignments = (
        ExampleAssignment.objects.filter(
            batch=batch,
            example=current_example,
            phase=BatchPhase.DISCUSSION,
        )
        .select_related("user")
        .prefetch_related("annotations__label")
        .order_by("user__username")
    )
    after_by_user = {a.user.username: list(a.annotations.all()) for a in after_assignments}

    context["prev_annotations"] = before_by_user
    context["post_annotations"] = after_by_user
    next_assignment = current_assignment.next(skip_annotated=True)

    chat_messages = (
        Message.objects.filter(example=current_example)
        .exclude(user="system")
        .order_by("created_at")
    )

    context["disagreements_remaining"] = open_assignments.count()
    context["example_id"] = current_example.id
    context["sentence"] = current_example
    context["assignment"] = current_assignment
    context["next_example"] = next_assignment.example if next_assignment else None
    context["chat_messages"] = chat_messages
    return context


class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "batch_id"
    model = Batch
    template_name = "expert/index.html"
    htmx_template_name = "expert/partials/dialogue.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["batch_id"] = self.kwargs.get("batch_id")
        codebook_form = CodebookForm(prefix="codebook")
        context.update(
            build_dialog_context(
                batch=self.object,
                user=self.request.user,
                labels_form=None,
                codebook_form=codebook_form,
            ),
        )
        if context.get("sentence"):
            context["labels_form"] = MultiLabelFormExpert(
                prefix="labels",
                codebook=context["codebook"],
                example=context["sentence"],
                user=self.request.user,
            )
        return context

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)

        if request.htmx:
            return render(request, self.htmx_template_name, context)

        return super().render_to_response(context)

    def post(self, request, assignment_id, codebook_id, **kwargs):
        assignment = get_object_or_404(
            ExampleAssignment.objects.select_related("example"),
            pk=assignment_id,
        )

        user = request.user
        example = assignment.example
        batch = example.batch
        project = batch.project
        codebook = project.codebook.get()

        labels_form = MultiLabelFormExpert(
            request.POST,
            codebook=codebook,
            example=example,
            user=user,
            prefix="labels",
        )

        codebook_form = CodebookForm(request.POST, prefix="codebook", codebook=codebook)

        forms_are_valid = labels_form.is_valid() and codebook_form.is_valid()
        if forms_are_valid:
            labels_form.save()
            metadata = build_decision_metadata(example, labels_form.cleaned_data["labels"])
            codebook_form.save(codebook, metadata=metadata)
            messages.success(request, "Saved.")
        else:
            if labels_form.errors:
                log.debug(f"Following errors: {labels_form.errors}")
            if codebook_form.errors:
                log.debug(f"Following errors: {codebook_form.errors}")
            messages.error(request, "Something was invalid")

        has_open_assignments = ExampleAssignment.objects.filter(
            batch=batch,
            user=user,
            phase=BatchPhase.EXPERT,
            done__isnull=True,
        ).exists()
        if not has_open_assignments and batch.current_phase != BatchPhase.FINAL:
            batch.set_phase(BatchPhase.FINAL)

        if request.htmx:
            context = build_dialog_context(
                batch=batch,
                user=user,
                labels_form=labels_form,
                codebook_form=codebook_form,
            )
            if forms_are_valid:
                # The response renders the NEXT open example; the saved form is
                # bound to the previous one and would leak its checkbox state.
                context["codebook_form"] = CodebookForm(prefix="codebook")
                if context.get("sentence"):
                    context["labels_form"] = MultiLabelFormExpert(
                        prefix="labels",
                        codebook=codebook,
                        example=context["sentence"],
                        user=user,
                    )
            else:
                context["draft_codebook"] = codebook_form.data.get(
                    codebook_form.add_prefix("content"),
                    context["codebook"].content,
                )
                context["success"] = False
            return render(request, self.htmx_template_name, context)

        if has_open_assignments:
            return redirect("expert-dialogue", batch_id=batch.id)
        return redirect("project-detail", project_id=project.id)
