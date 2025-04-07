import logging
import re

from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView

from .forms import CodebookForm
from .models import Codebook
from core.mixins import AnyRoleRequiredMixin
from core.mixins import ExpertRequiredMixin
from projects.models import ProjectUser

log = logging.getLogger(__name__)


# Create your views here.
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
        return context


class CodebookDiffView(AnyRoleRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "codebook/view-diff.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        batch_old = self.request.GET.get("batch_old", 0)
        batch_new = self.request.GET.get("batch_new", self.object.project.max_batch_number)
        context["content"] = self.object.diff(batch_old, batch_new)
        log.debug(f"{context['content'] = }")
        return context


class CodebookUpdateView(ExpertRequiredMixin, UpdateView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    form_class = CodebookForm
    template_name = "codebook/edit.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["content"] = self.object.content
        return initial

    def form_valid(self, form):
        content = form.cleaned_data["content"]
        self.object.save(content=content, commit_message="edited.")
        return redirect(self.object.get_absolute_url())
