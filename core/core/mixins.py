from django.core.exceptions import PermissionDenied

from projects.models import ProjectRole
from projects.models import ProjectUser
from projects.models.batch import BatchUser


class RoleRequiredMixin:
    """Project-level check against ProjectUser.default_role.

    Use for project pages and for managing a project or its batches
    (create, export, change phase, delete).
    """

    def dispatch(self, request, *args, **kwargs):
        project_id = kwargs.get("project_id")
        assignment_id = (
            kwargs.get("assignment_id")
            or request.GET.get("assignment_id")
            or request.POST.get("assignment_id")
        )
        batch_id = kwargs.get("batch_id")
        codebook_id = kwargs.get("codebook_id")

        if project_id:
            membership = ProjectUser.objects.filter(
                project_id=project_id,
                user=request.user,
                default_role__in=self.roles,
            ).first()
        elif assignment_id:
            membership = ProjectUser.objects.filter(
                project__batches__examples__assignments__id=assignment_id,
                user=request.user,
                default_role__in=self.roles,
            ).first()
        elif batch_id:
            membership = ProjectUser.objects.filter(
                project__batches__id=batch_id,
                user=request.user,
                default_role__in=self.roles,
            ).first()
        elif codebook_id:
            membership = ProjectUser.objects.filter(
                project__codebook__id=codebook_id,
                user=request.user,
                default_role__in=self.roles,
            ).first()
        else:
            msg = "This page belongs to no project."
            raise PermissionDenied(msg)

        if not membership:
            msg = "You don't have the role this page needs in this project."
            raise PermissionDenied(msg)

        return super().dispatch(request, *args, **kwargs)


class BatchRoleRequiredMixin:
    """Batch-level check against BatchUser.role.

    Use for views where a user works on a batch (annotate, discuss, decide as
    expert). Roles are assigned per batch, so a project expert may annotate
    one batch, and project members who are not part of a batch get no access.
    """

    def dispatch(self, request, *args, **kwargs):
        has_role = BatchUser.objects.filter(
            batch_id=kwargs["batch_id"],
            user_id=request.user.id,
            role__in=self.roles,
        ).exists()
        if not has_role:
            msg = "You are not part of this batch in the role this page needs."
            raise PermissionDenied(msg)

        return super().dispatch(request, *args, **kwargs)


class AnnotatorRequiredMixin(RoleRequiredMixin):
    roles = (ProjectRole.ANNOTATOR,)


class ExpertRequiredMixin(RoleRequiredMixin):
    roles = (ProjectRole.EXPERT,)


class AnyRoleRequiredMixin(RoleRequiredMixin):
    roles = (ProjectRole.ANNOTATOR, ProjectRole.EXPERT)


class BatchAnnotatorRequiredMixin(BatchRoleRequiredMixin):
    roles = (ProjectRole.ANNOTATOR,)


class BatchExpertRequiredMixin(BatchRoleRequiredMixin):
    roles = (ProjectRole.EXPERT,)
