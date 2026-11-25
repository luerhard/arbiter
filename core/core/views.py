from django.contrib.auth.decorators import login_not_required
from django.db.models import Prefetch
from django.shortcuts import redirect
from django.shortcuts import render

from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import BatchUser
from projects.models import ProjectUser

# discussions need the partner online, so they come first
_TASK_ORDER = {"discuss": 0, "decide": 1, "annotate": 2}


def open_tasks(user) -> list[dict]:
    """The batches where the user has something to do right now."""
    batch_users = BatchUser.objects.filter(
        user=user,
        batch__current_phase__in=[BatchPhase.ANNOTATION, BatchPhase.DISCUSSION, BatchPhase.EXPERT],
    ).select_related("batch__project")

    tasks = []
    for batch_user in batch_users:
        task = batch_user.task()
        if task is None:
            continue
        batch = batch_user.batch
        # in the discussion one assignment per example to discuss
        mine = ExampleAssignment.objects.filter(batch=batch, user=user, phase=batch.current_phase)
        done, total = mine.done().count(), mine.count()

        tasks.append(
            {
                "kind": task.kind,
                "batch": batch,
                "url": task.url,
                "done": done,
                "total": total,
                "percent": round(100 * done / total) if total else 0,
            },
        )

    return sorted(
        tasks,
        key=lambda t: (_TASK_ORDER[t["kind"]], t["batch"].project.name, t["batch"].batch_number),
    )


@login_not_required
def core(request):
    if not request.user.is_authenticated:
        return redirect("login")

    memberships = (
        ProjectUser.objects.filter(user=request.user)
        .select_related("project")
        .prefetch_related(
            Prefetch("project__batches", queryset=Batch.objects.order_by("batch_number")),
        )
        .order_by("project__name")
    )
    context = {
        "tasks": open_tasks(request.user),
        "memberships": memberships,
    }
    return render(request, "core/dashboard.html", context)
