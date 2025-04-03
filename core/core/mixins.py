from django.http import HttpResponseForbidden

from projects.models import ProjectUser


class RoleRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        project_id = kwargs.get("project_id")
        assignment_id = kwargs.get("assignment_id")
        batch_id = kwargs.get("batch_id")
        codebook_id = kwargs.get("codebook_id")

        if project_id:
            membership = ProjectUser.objects.filter(
                project_id=project_id,
                user=request.user,
                role__in=self.roles,
            ).first()
        elif assignment_id:
            membership = ProjectUser.objects.filter(
                project__batches__examples__assignments__id=assignment_id,
                user=request.user,
                role__in=self.roles,
            ).first()
        elif batch_id:
            membership = ProjectUser.objects.filter(
                project__batches__id=batch_id,
                user=request.user,
                role__in=self.roles,
            ).first()
        elif codebook_id:
            membership = ProjectUser.objects.filter(
                project__codebook__id=codebook_id,
                user=request.user,
                role__in=self.roles,
            ).first()
        else:
            return HttpResponseForbidden("Project ID not provided.")

        if not membership:
            return HttpResponseForbidden("You do not have annotator permissions on this project.")

        return super().dispatch(request, *args, **kwargs)


class AnnotatorRequiredMixin(RoleRequiredMixin):
    roles = (ProjectUser.Role.ANNOTATOR,)


class ExpertRequiredMixin(RoleRequiredMixin):
    roles = (ProjectUser.Role.EXPERT,)


class AnyRoleRequiredMixin(RoleRequiredMixin):
    roles = (ProjectUser.Role.ANNOTATOR, ProjectUser.Role.EXPERT)
