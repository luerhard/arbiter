import json

from codebook.models import Codebook
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.generic import View
from django.views.generic.detail import DetailView

from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example
from data.models import ExampleAssignment
from discuss.models import Message


def save_resolution_labels(request, codebook_id, batch_id, example_id):
    if request.method != "POST":
        return
    user = request.user
    example = get_object_or_404(Example, pk=example_id, batch=batch_id)
    assignment = ExampleAssignment.objects.filter(example=example, user=user).first()
    codebook = get_object_or_404(Codebook, pk=codebook_id)
    project = codebook.project
    if not assignment:
        max_order = ExampleAssignment.objects.filter(
            user=user, example__batch=example.batch
        ).aggregate(models.Max("order", default=0))["order__max"]
        assignment = ExampleAssignment.objects.create(
            example=example, user=user, order=max_order + 1
        )
    label_ids = [int(i) for i in request.POST.getlist("selected_labels") if i.strip()]
    assignment.set_user_annotations(label_ids=label_ids, phase="EXPERT")

    all_examples = Example.objects.filter(
        has_disagreement=True,
        has_disagreement_after_discussion=True,
        has_expert_decision=False,
        batch_id=batch_id,
        batch__project_id=project.id,
    ).order_by("id")
    next_example = all_examples.filter(id__gt=example.id).order_by("id").first()
    if next_example:
        return redirect("expert-dialogue", codebook_id, batch_id, next_example.id)
    else:
        return redirect("/")


class CodebookPartialView(View):
    def get(self, request, pk):
        codebook = get_object_or_404(Codebook, pk=pk)
        return render(request, "expert/partials/codebook_rendered.html", {"codebook": codebook})


class CodebookUpdateView(View):
    def post(self, request, pk):
        codebook = get_object_or_404(Codebook, pk=pk)
        content = request.POST.get("content", "")
        rationale = request.POST.get("definition_correction", "")
        sentence = request.POST.get("sentence", "")
        example_id = request.POST.get("example_id", "")
        batch_id = request.POST.get("batch_id", "")
        selected_labels_ids = request.POST.get("selected_labels")
        current_example = get_object_or_404(Example, pk=example_id, batch=batch_id)
        project = codebook.project

        label_id_array = [int(i) for i in selected_labels_ids.split(",") if i.strip()]
        selected_labels = project.labels.filter(id__in=label_id_array)
        selected_label_names = [label.name for label in selected_labels]
        annotations_before_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            phase=Annotation.Phase.ANNOTATION,
        )
        annotations_after_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            phase=Annotation.Phase.DISCUSSION,
        )
        messages = (
            Message.objects.filter(example=current_example)
            .exclude(user="system")
            .order_by("created_at")
        )
        chat_history_list = [f"{msg.user}: {msg.message}" for msg in messages]
        chat_history_str = "\n".join(chat_history_list)

        labels_before_str = ""
        for ann in annotations_before_discussion:
            labels_before_str += f"{ann.label} (assigned by: {ann.assignment.user})\n"

        labels_after_list = [
            f"{ann.label} (assigned by: {ann.assignment.user})"
            for ann in annotations_after_discussion
        ]
        labels_after_str = "\n".join(labels_after_list)
        commit_info = {
            "rationale": rationale,
            "sentence": sentence,
            "labels_before": labels_before_str,
            "labels_after": labels_after_str,
            "chat_history": chat_history_str,
            "selected_labels_ids": selected_label_names,
        }
        commit_message = json.dumps(commit_info, ensure_ascii=False)
        if content:
            codebook.save(content=content, commit_message=commit_message)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        return render(request, "expert/partials/codebook_rendered.html", {"codebook": codebook})


class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "expert/dialogue.html"

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
            raise PermissionDenied("Access denied: No examples meet the criteria.")
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

        return context
