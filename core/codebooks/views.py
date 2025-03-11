import asyncio
import logging
from django.http import HttpResponse
from django.http import Http404
from django.views import View
from django.core.exceptions import ObjectDoesNotExist

from projects.models import ProjectUser


log = logging.getLogger(__name__)
log.debug("------Reload-------")


class CodebookVersionView(View):
    def get(self, request, project_id, codebookversion=None, *args, **kwargs):
        log.debug("------Request-------")
        try:
            # Check if the requesting user is tied to the specified project
            project_user = ProjectUser.objects.get(user=request.user, project__id=project_id)

            # Attempt to get the CodebookVersion for the specified project
            if codebookversion:
                codebookv = project_user.project.codebook_set.get(codebookversion__version=codebookversion)
            else:
                codebookv = project_user.project.codebook_set.latest("codebookversion__date")

        except ObjectDoesNotExist as e:
            log.debug("Object does not exist.")
            raise Http404("Page not found.")

        return HttpResponse("Hello World!")
