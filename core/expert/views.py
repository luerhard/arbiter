import logging

from codebook.models import Codebook
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic.detail import DetailView

from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example
from discuss.models import Message
from projects.models import Batch

log = logging.getLogger(__name__)


class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "expert/dialogue.html"

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
        codebook = self.object
        project = codebook.project
        context["codebook"] = codebook
        batch_id = self.kwargs.get("batch_id")
        context["batch_id"] = batch_id

        current_example_id = self.kwargs.get("example_id")
        all_examples = [
            e
            for e in Example.objects.filter(
                batch_id=batch_id,
                batch__project_id=project.id,
            ).order_by("id")
            if e.has_disagreement
            and e.has_disagreement_after_discussion
            and not e.has_expert_decision
        ]

        if not all_examples:
            return None
        if current_example_id:
            current_example = get_object_or_404(
                Example,
                pk=current_example_id,
                batch__project_id=project.id,
            )
            if not (
                current_example.has_disagreement_after_discussion
                and not current_example.has_expert_decision
            ):
                current_example = all_examples[0]
        else:
            current_example = all_examples[0]

        next_example = next((e for e in all_examples if e.id > current_example.id), None)
        context["example_id"] = current_example_id
        context["sentence"] = current_example
        context["next_example"] = next_example
        context["all_examples"] = all_examples

        annotations_before_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            assignment__batch_assignment__phase=Batch.Phase.ANNOTATION,
        )
        annotations_after_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            assignment__batch_assignment__phase=Batch.Phase.DISCUSSION,
        )
        messages = (
            Message.objects.filter(
                example=current_example,
            )
            .exclude(user="system")
            .order_by("created_at")
        )

        prev_label_ids = [a.label.id for a in annotations_after_discussion]
        context["disagreements_remaining"] = len(all_examples)
        context["prev_annotations"] = annotations_before_discussion
        context["post_annotations"] = annotations_after_discussion
        context["chat_messages"] = messages
        context["prev_label_ids"] = prev_label_ids
        context["labels"] = project.labels.all()

        log.debug("Providing the following context for the expert resolution")
        log.debug(context)
        return context
