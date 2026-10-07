import io
import logging
import zipfile

from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.text import slugify
from django.views.generic import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView

from .forms import CodebookForm
from .models import Codebook
from core import settings
from core.mixins import AnyRoleRequiredMixin
from core.mixins import ExpertRequiredMixin
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
        context["role"] = project_user.default_role
        context["content"] = context["codebook"].content
        context["changes"] = context["codebook"].changes()
        context["since"] = context["codebook"].last_batch_of(user)
        return context


class CodebookDiffView(AnyRoleRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "codebook/view-diff.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        # batch_old and batch_new: what changed between the versions two batches started
        # with; batch_old alone or nothing: since then (by default since the reader's last
        # batch) up to the current text
        try:
            batch_new = self._batch_param("batch_new")
            batch_old = self._batch_param("batch_old")
        except ValueError as exc:
            raise Http404(str(exc)) from exc
        tagged = self.object.tagged_batches()
        if batch_new is not None and batch_new not in tagged:
            msg = f"Batch {batch_new} has no codebook version."
            raise Http404(msg)
        if batch_old is None:
            if batch_new is None:
                batch_old = self.object.last_batch_of(self.request.user) or 0
            else:
                batch_old = batch_new - 1
        # if that batch was deleted (or has not started), compare with the one before it
        batch_old = max((number for number in tagged if number <= batch_old), default=0)
        context["content_diff"] = self.object.diff(batch_old, batch_new)
        context["changes"] = self.object.changes_between(batch_old, batch_new)
        context["batch_old"] = batch_old
        context["batch_new"] = batch_new
        return context

    def _batch_param(self, name) -> int | None:
        value = self.request.GET.get(name, "")
        return int(value) if value else None


class CodebookChangeView(AnyRoleRequiredMixin, DetailView):
    """One change of the codebook text with its rationale."""

    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "codebook/change.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        found = self.object.change(self.kwargs["sha"])
        if found is None:
            msg = "No such change of this codebook."
            raise Http404(msg)
        context["change"], context["content_diff"] = found
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop("instance", None)
        return kwargs

    def form_valid(self, form):
        form.save(codebook=self.object)
        return redirect(self.object.get_absolute_url())


class CodebookExportView(ExpertRequiredMixin, View):
    pk_url_kwarg = "codebook_id"

    def get(self, request, codebook_id, *args, **kwargs):
        codebook = get_object_or_404(Codebook, pk=codebook_id)
        repo_dir = settings.CODEBOOKS_ROOT / codebook.git_dir

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in repo_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(repo_dir))

        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        safe_name = slugify(codebook.project.name)
        response["Content-Disposition"] = f"attachment; filename=codebook_{safe_name}.zip"
        return response
