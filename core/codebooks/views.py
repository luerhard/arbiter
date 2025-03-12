import logging

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import render
from django.views import View

from projects.models import ProjectUser

log = logging.getLogger(__name__)
log.debug("------Reload-------")


class CodebookVersionView(View):
    def get(self, request, project_id, version_name=None, *args, **kwargs):
        log.debug(f"Request: {request}")
        try:
            # Check if the requesting user is tied to the specified project
            project_user = ProjectUser.objects.get(user=request.user, project__id=project_id)
            # Attempt to get the codebook associated with the project
            codebook = project_user.project.codebook_set.get()
            # Get the RelatedManager for codebookversions
            codebookversions = codebook.codebookversion_set
            # Attempt to get the CodebookVersion for the specified project
            if version_name:
                codebookv = codebookversions.get(version_name=version_name)
            else:
                codebookv = codebookversions.latest("date")
        except ObjectDoesNotExist as e:
            log.debug(f"Object does not exist. {request.path}")
            raise Http404("Page not found.")

        codebook_fields = []
        for field in codebookv.codebookfield_set.order_by("order_index"):
            if hasattr(field, "definitionfield"):
                codebook_fields.append((field.definitionfield, "definitionfield"))
            elif hasattr(field, "examplefield"):
                codebook_fields.append((field.examplefield, "examplefield"))
            elif hasattr(field, "descriptionfield"):
                codebook_fields.append((field.descriptionfield, "descriptionfield"))

        context = {
            "project_name": project_user.project.name,
            "codebook_name": codebook.name,
            "version_name": codebookv.version_name,
            "codebook_description": codebookv.codebook_description,
            "date": codebookv.date,
            "fields": codebook_fields,
        }

        return render(request, "codebooks/codebook-view.html", context)
