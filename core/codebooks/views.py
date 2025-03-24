import logging

from django.contrib import messages
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views import View
from django.views.generic.edit import DeleteView
from django.views.generic.edit import FormView
from django.views.generic.edit import UpdateView
from django_htmx.http import HttpResponseClientRefresh

from .forms import ExampleForm
from .models import CodebookVersion
from .models import Definition
from .models import Example
from projects.models import Project

log = logging.getLogger(__name__)
log.debug("------Reload-------")


class CodebookVersionView(View):
    def get(self, request, project_id, version_name=None, *args, **kwargs):  # noqa: ARG002
        log.debug(f"Request: {request}")

        project = get_object_or_404(Project, id=project_id)

        if version_name:
            codebookv = (
                get_object_or_404(
                    CodebookVersion,
                    codebook__project=project,
                    version_name=version_name,
                )
                .prefetch_related("definitions", "definitions_examples")
                .prefetch_related("descriptions")
            )
        else:
            try:
                codebookv = (
                    CodebookVersion.objects.filter(codebook__project=project)
                    .order_by("date")
                    .prefetch_related("definitions__examples")
                    .prefetch_related("descriptions")[0]
                )
            except IndexError:
                msg = "No codebooks exist."
                raise Http404(msg)  # noqa: B904

        context = {
            "project": project,
            "codebook": codebookv.codebook,
            "codebookv": codebookv,
        }

        return render(request, "codebooks/codebook-view.html", context)


def edit(request, codebook_id):
    context = {}
    codebook = get_object_or_404(CodebookVersion, id=codebook_id)
    context["codebook"] = codebook
    return render(request, "codebooks/edit.html", context)


def sort_examples(request):
    example_order = request.POST.getlist("example_order")
    definition_id = request.POST.get("definition_id")
    to_save = []
    for i, example_pk in enumerate(example_order, 1):
        ex = Example.objects.get(pk=example_pk)
        ex.order = i
        to_save.append(ex)
    Example.objects.bulk_update(to_save, fields=["order"])
    context = {}
    definition = Definition.objects.filter(pk=definition_id).prefetch_related("examples").get()
    context["definition"] = definition
    return render(request, "codebooks/partials/edit_example_list.html", context)


class AddExample(FormView):
    template_name = "codebooks/partials/add-example-modal.html"
    form_class = ExampleForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["action"] = "add"
        kwargs["pk"] = self.kwargs.get("definition_id")
        return kwargs

    def form_valid(self, form):  # noqa: ARG002
        definition_id = form.pk
        definition = get_object_or_404(Definition, id=definition_id)

        example = form.save(commit=False)
        example.definition = definition
        max_order = definition.examples.aggregate(Max("order")).get("order__max", 0)
        example.order = max_order + 1
        example.save()
        messages.success(self.request, "Example added")
        return HttpResponseClientRefresh()


class UpdateExample(UpdateView):
    template_name = "codebooks/partials/add-example-modal.html"
    form_class = ExampleForm
    model = Example
    pk_url_kwarg = "example_id"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["action"] = "update"
        kwargs["pk"] = self.kwargs.get("example_id")
        return kwargs

    def form_valid(self, form):
        form.save()
        return HttpResponseClientRefresh()


class DeleteExample(DeleteView):
    model = Example
    pk_url_kwarg = "example_id"

    def delete(self, request, *args, **kwargs):  # noqa: ARG002
        self.obj = self.get_object()
        self.obj.delete()
        messages.success(request, "Example deleted.")
        return HttpResponseClientRefresh()
