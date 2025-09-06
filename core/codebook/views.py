import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView

from .forms import CodebookForm
from .models import Codebook
from core.mixins import AnyRoleRequiredMixin
from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example
from discuss.models import Message
from projects.models import ProjectUser

log = logging.getLogger(__name__)


class CodebookView(AnyRoleRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "codebook/view.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        user = self.request.user
        project_user = get_object_or_404(ProjectUser, user=user, project=self.object.project)
        context["role"] = project_user.role
        context["content"] = context["codebook"].content
        return context


class CodebookDiffView(AnyRoleRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "codebook/view-diff.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        batch_new = self.request.GET.get("batch_new", self.object.project.max_batch_number)
        batch_old = self.request.GET.get("batch_old", max(0, batch_new - 1))
        context["content_diff"] = self.object.diff(batch_old, batch_new)
        return context


class CodebookUpdateView(ExpertRequiredMixin, UpdateView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    form_class = CodebookForm
    template_name = "codebook/edit.html"

    def post(self, request, codebook_id):
        codebook = get_object_or_404(Codebook, pk=codebook_id)
        content = request.POST.get("content", "")
        rationale = request.POST.get("rationale", "")
        sentence = request.POST.get("sentence", "")
        example_id = request.POST.get("example_id", "")
        batch_id = request.POST.get("batch_id", "")
        selected_labels_ids = request.POST.get("selected_labels", "")

        current_example = None
        if example_id or batch_id:
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
        log.debug(f"{commit_info = }")
        log.debug(f"{commit_message = }")
        if content:
            codebook.save(content=content, commit_message=commit_message)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        return redirect(codebook.get_absolute_url())

    def get_initial(self):
        initial = super().get_initial()
        initial["content"] = self.object.content
        return initial

    def form_valid(self, form):
        log.debug(f"{form.cleaned_data = }")
        content = form.cleaned_data["content"]
        commit_message = form.cleaned_data["rationale"]
        self.object.save(content=content, commit_message=commit_message)
        return redirect(self.object.get_absolute_url())
