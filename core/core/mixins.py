from django.core.exceptions import PermissionDenied

from projects.models import ProjectRole
from projects.models import ProjectUser
from projects.models.batch import BatchUser


class RoleRequiredMixin:
    """Project-level check against ProjectUser.default_role.

    Use for project pages and for managing a project or its batches
    (create, export, change phase, delete).

    The project comes from the URL alone, never from what the request sends along:
    an id in the query string or form would let a member of one project into another.
    """

    def dispatch(self, request, *args, **kwargs):
        if "project_id" in kwargs:
            project = {"project_id": kwargs["project_id"]}
        elif "batch_id" in kwargs:
            project = {"project__batches__id": kwargs["batch_id"]}
        elif "codebook_id" in kwargs:
            project = {"project__codebook__id": kwargs["codebook_id"]}
        else:
            msg = "This page belongs to no project."
            raise PermissionDenied(msg)

        membership = ProjectUser.objects.filter(
            user=request.user,
            default_role__in=self.roles,
            **project,
        ).exists()
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
