from codebook.models import Codebook
from django.db.models import OuterRef
from django.db.models import Subquery

from projects.models import Batch
from projects.models import ProjectUser


def navigation(request):
    """Data for the sidebar: the user's projects and which one is open."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    latest_phase = (
        Batch.objects.filter(project=OuterRef("project"))
        .order_by("-batch_number")
        .values("current_phase")[:1]
    )
    memberships = (
        ProjectUser.objects.filter(user=user)
        .select_related("project")
        .annotate(latest_phase=Subquery(latest_phase))
        .order_by("project__name")
    )

    match = request.resolver_match
    url_kwargs = match.kwargs if match else {}
    project_id = url_kwargs.get("project_id")
    if project_id is None and "batch_id" in url_kwargs:
        project_id = (
            Batch.objects.filter(id=url_kwargs["batch_id"])
            .values_list("project_id", flat=True)
            .first()
        )
    if project_id is None and "codebook_id" in url_kwargs:
        project_id = (
            Codebook.objects.filter(id=url_kwargs["codebook_id"])
            .values_list("project_id", flat=True)
            .first()
        )

    codebook_id = None
    if project_id is not None:
        codebook_id = (
            Codebook.objects.filter(project_id=project_id).values_list("id", flat=True).first()
        )

    return {
        "nav_projects": memberships,
        "nav_project_id": project_id,
        "nav_codebook_id": codebook_id,
        "nav_url_name": match.url_name if match else "",
    }
