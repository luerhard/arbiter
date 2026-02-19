import logging

from codebook.models import Codebook
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
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


class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "batch_id"
    model = Batch
    template_name = "expert/index.html"

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if not context:
            batch_id = self.kwargs.get("batch_id")
            project_id = get_object_or_404(Batch, id=batch_id).project.id
            return redirect(reverse("project-detail", kwargs={"project_id": project_id}))
        return self.render_to_response(context)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        batch = self.object
        project = batch.project
        context["codebook"] = project.codebook.get()

        disagreements = batch.disagreements(phase=Batch.Phase.DISCUSSION)

        n_disagreements = disagreements.count()
        current_example = disagreements.first()
        current_assignment = ExampleAssignment.objects.filter(
            example=current_example,
            batch_assignment__user=self.request.user,
        ).get()

        context["example_id"] = current_example.id
        context["sentence"] = current_example
        context["assignment"] = current_assignment

        annotations_before_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            assignment__batch_assignment__phase=Batch.Phase.ANNOTATION,
        )
        annotations_after_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            assignment__batch_assignment__phase=Batch.Phase.DISCUSSION,
        )
        messages = (
            Message.objects
            .filter(
                example=current_example,
            )
            .exclude(user="system")
            .order_by("created_at")
        )

        prev_label_ids = [a.label.id for a in annotations_after_discussion]
        context["disagreements_remaining"] = n_disagreements
        context["prev_annotations"] = annotations_before_discussion
        context["post_annotations"] = annotations_after_discussion
        context["chat_messages"] = messages
        context["prev_label_ids"] = prev_label_ids
        context["labels"] = project.labels.all()

        log.debug("Providing the following context for the expert resolution")
        log.debug(context)
        return context


class SaveLabelsExpert(ExpertRequiredMixin, UpdateView):
    def post(self, *args, **kwargs):  # noqa: ARG002
        assignment_id = kwargs.get("assignment_id")
        assignment = get_object_or_404(
            ExampleAssignment.objects.select_related(
                "example__batch__project",
                "batch_assignment",
            ),
            pk=assignment_id,
        )

        user = self.request.user
        example = assignment.example
        batch = example.batch
        project = batch.project
        codebook = project.codebook.get()

        form = MultiLabelFormExpert(
            self.request.POST,
            codebook=codebook,
            example=example,
            user=user,
        )
        if form.is_valid():
            form.save()
            messages.success(self.request, "Saved.")
        else:
            messages.error(self.request, f"Something was invalid: {form}")

        any_remaining = any(
            e.has_disagreement and e.has_disagreement_after_discussion and not e.has_expert_decision
            for e in Example.objects.filter(batch=batch).order_by("id")
        )

        if any_remaining:
            return redirect("expert-dialogue", batch_id=batch.id)

        batch.set_phase(Batch.Phase.FINAL)
        batch.save(update_fields=["current_phase"])
        return redirect("project-detail", project_id=project.id)
