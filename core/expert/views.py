import logging

from codebook.forms import CodebookForm
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.generic.detail import DetailView

from .forms import MultiLabelFormExpert
from core.mixins import ExpertRequiredMixin
from data.models import ExampleAssignment
from discuss.models import Message
from projects.models import Batch
from projects.models import BatchPhase

log = logging.getLogger(__name__)


def build_dialog_context(batch, user):
    project = batch.project
    context = {
        "batch_id": batch.id,
        "codebook": project.codebook.get(),
        "labels": project.labels.all(),
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
        context["prev_label_ids"] = []
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
    context["annotator"] = next(iter(before_by_user))

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
    context["prev_label_ids"] = sorted(
        {
            annotation.label_id
            for annotations in after_by_user.values()
            for annotation in annotations
        },
    )
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
        context.update(build_dialog_context(batch=self.object, user=self.request.user))
        context["batch_id"] = self.kwargs.get("batch_id")
        context["codebook_form"] = CodebookForm(prefix="codebook")
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
            request.POST, codebook=codebook, example=example, user=user, prefix="labels"
        )

        codebook_form = CodebookForm(request.POST, prefix="codebook")

        if labels_form.is_valid() and codebook_form.is_valid():
            labels_form.save()
            codebook_form.save(codebook)
            messages.success(request, "Saved.")
        else:
            if labels_form.errors:
                log.debug(f"Following errors: {labels_form.errors}")
            if codebook_form.errors:
                log.debug(f"Following errors: {codebook_form.errors}")
            messages.error(
                request, f"Something was invalid: {labels_form.errors} or {codebook_form.errors}"
            )

        has_open_assignments = ExampleAssignment.objects.filter(
            batch=batch,
            user=user,
            phase=BatchPhase.EXPERT,
            done__isnull=True,
        ).exists()
        if not has_open_assignments and batch.current_phase != BatchPhase.FINAL:
            batch.set_phase(BatchPhase.FINAL)

        if request.htmx:
            context = build_dialog_context(batch=batch, user=user)
            return render(request, self.htmx_template_name, context)

        if has_open_assignments:
            return redirect("expert-dialogue", batch_id=batch.id)
        return redirect("project-detail", project_id=project.id)
