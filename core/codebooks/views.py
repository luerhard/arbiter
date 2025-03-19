import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views import View

from .models import CodebookVersion
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
