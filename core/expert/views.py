import logging

from codebook.models import Codebook
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView

from .forms import MultiLabelFormExpert
from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example
from data.models import ExampleAssignment
from discuss.models import Message
from projects.models import Batch

log = logging.getLogger(__name__)


def build_dialog_context(batch, user):
    project = batch.project
    context = {
        "batch_id": batch.id,
        "codebook": project.codebook.get(),
        "labels": project.labels.all(),
    }

    open_assignments = ExampleAssignment.objects.filter(
        example__in=batch.disagreements(Batch.Phase.DISCUSSION),
        batch_assignment__user=user,
        batch_assignment__phase=Batch.Phase.EXPERT,
        done__isnull=True,
    ).select_related("example", "batch_assignment")

    current_assignment = open_assignments.first()
    if not current_assignment:
        context["disagreements_remaining"] = 0
        context["assignment"] = None
        context["sentence"] = None
        context["next_example"] = None
        context["prev_annotations"] = []
        context["post_annotations"] = []
        context["chat_messages"] = []
        context["prev_label_ids"] = []
        return context

    current_example = current_assignment.example
    next_assignment = current_assignment.next(skip_annotated=True)

    annotations_before_discussion = Annotation.objects.filter(
        assignment__example=current_example,
        assignment__batch_assignment__phase=Batch.Phase.ANNOTATION,
    )
    annotations_after_discussion = Annotation.objects.filter(
        assignment__example=current_example,
        assignment__batch_assignment__phase=Batch.Phase.DISCUSSION,
    )
    chat_messages = (
        Message.objects
        .filter(example=current_example)
        .exclude(user="system")
        .order_by("created_at")
    )

    context["disagreements_remaining"] = open_assignments.count()
    context["example_id"] = current_example.id
    context["sentence"] = current_example
    context["assignment"] = current_assignment
    context["next_example"] = next_assignment.example if next_assignment else None
    context["prev_annotations"] = annotations_before_discussion
    context["post_annotations"] = annotations_after_discussion
    context["chat_messages"] = chat_messages
    context["prev_label_ids"] = [annotation.label.id for annotation in annotations_after_discussion]
    return context


class ExpertDialog(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "batch_id"
    model = Batch
    template_name = "expert/index.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["batch_id"] = self.kwargs.get("batch_id")
        return context


class ExpertDialogueContent(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "batch_id"
    model = Batch
    template_name = "expert/partials/dialog.html"

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        batch = self.get_object()
        context = build_dialog_context(batch=batch, user=request.user)
        return render(request, self.template_name, context)


class SaveLabelsExpert(ExpertRequiredMixin, UpdateView):
    def post(self, request, **kwargs):
        assignment_id = kwargs.get("assignment_id")
        assignment = get_object_or_404(
            ExampleAssignment.objects.select_related(
                "example__batch__project",
                "batch_assignment",
            ),
            pk=assignment_id,
        )

        user = request.user
        example = assignment.example
        batch = example.batch
        project = batch.project
        codebook = project.codebook.get()

        form = MultiLabelFormExpert(
            request.POST,
            codebook=codebook,
            example=example,
            user=user,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
        else:
            messages.error(request, f"Something was invalid: {form}")

        has_open_assignments = ExampleAssignment.objects.filter(
            example__batch=batch,
            batch_assignment__user=user,
            batch_assignment__phase=Batch.Phase.EXPERT,
            done__isnull=True,
        ).exists()
        if not has_open_assignments and batch.current_phase != Batch.Phase.FINAL:
            batch.set_phase(Batch.Phase.FINAL)

        if request.htmx:
            context = build_dialog_context(batch=batch, user=user)
            return render(request, "expert/partials/dialog.html", context)

        if has_open_assignments:
            return redirect("expert-dialogue", batch_id=batch.id)
        return redirect("project-detail", project_id=project.id)
