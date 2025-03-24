import logging

from crispy_forms.utils import render_crispy_form
from django.contrib import messages
from django.db.models import Max
from django.http import Http404
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template.context_processors import csrf
from django.views import View
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


class AddExample(View):
    def post(self, request, definition_id):  # noqa: ARG002
        definition = get_object_or_404(Definition, id=definition_id)
        form = ExampleForm(definition, self.request.POST)

        if form.is_valid():
            if form.cleaned_data["example_id"] is None:
                example = form.save(commit=False)
                example.definition = definition
                max_order = definition.examples.aggregate(Max("order")).get("order__max", 0)
                example.order = max_order + 1
                example.save()
                messages.success(request, "Example added")
                return HttpResponseClientRefresh()
            else:
                example = Example.objects.get(id=form.cleaned_data["example_id"])
                form = ExampleForm(definition, self.request.POST, instance=example)
                if form.is_valid():
                    form.instance = example
                    form.save()
                    messages.success(request, "Example modified")
                    return HttpResponseClientRefresh()

        messages.error(request, "Error occurred. Is identifier unique?")
        context = {}
        context.update(csrf(request))
        form_html = render_crispy_form(form)
        return HttpResponse(form_html)

    def get(self, request, definition_id, example_id: int | None = None):
        definition = get_object_or_404(Definition, id=definition_id)
        if example_id:
            example = get_object_or_404(Example, id=example_id)
            form = ExampleForm(definition, instance=example, initial={"example_id": example.id})
        else:
            form = ExampleForm(definition)
        return render(request, "codebooks/partials/add-example-modal.html", {"form": form})

    def delete(self, request, definition_id, example_id):
        example = Example.objects.get(id=example_id)
        example.delete()
        messages.success(request, "")
        context = {}
        definition = Definition.objects.filter(pk=definition_id).prefetch_related("examples").get()
        context["definition"] = definition
        return render(request, "codebooks/partials/edit_example_list.html", context)
