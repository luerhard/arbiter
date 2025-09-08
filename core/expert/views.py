import logging

from codebook.models import Codebook
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views.generic.detail import DetailView

from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example
from data.models import Batch
from discuss.models import Message

log = logging.getLogger(__name__)


class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "expert/dialogue.html"

    def get(self, request, codebook_id, batch_id, example_id):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if not context:
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
        all_examples = Example.objects.filter(
            has_disagreement=True,
            has_disagreement_after_discussion=True,
            has_expert_decision=False,
            batch_id=batch_id,
            batch__project_id=project.id,
        ).order_by("id")

        if not all_examples.exists():
            return None
        if current_example_id:
            current_example = get_object_or_404(
                Example, pk=current_example_id, batch__project_id=project.id
            )
            if not (
                current_example.has_disagreement_after_discussion
                and not current_example.has_expert_decision
            ):
                current_example = all_examples.first()
        else:
            current_example = all_examples.first()

        next_example = all_examples.filter(id__gt=current_example.id).order_by("id").first()
        context["example_id"] = current_example_id
        context["sentence"] = current_example
        context["next_example"] = next_example
        context["all_examples"] = all_examples

        annotations_before_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            assignment__example__batch_id=batch_id,
            assignment__example__batch__project_id=project.id,
            phase=Annotation.Phase.ANNOTATION,
        )
        annotations_after_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            assignment__example__batch_id=batch_id,
            assignment__example__batch__project_id=project.id,
            phase=Annotation.Phase.DISCUSSION,
        )
        messages = (
            Message.objects.filter(
                example=current_example,
                example__batch_id=batch_id,
                example__batch__project_id=project.id,
            )
            .exclude(user="system")
            .order_by("created_at")
        )

        prev_label_ids = [a.label.id for a in annotations_after_discussion]
        context["disagreements_remaining"] = all_examples.count()
        context["prev_annotations"] = annotations_before_discussion
        context["post_annotations"] = annotations_after_discussion
        context["chat_messages"] = messages
        context["prev_label_ids"] = prev_label_ids
        context["labels"] = project.labels.all()

        return context
