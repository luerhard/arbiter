from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse

from data.models import Example
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser

# Create your views here.


def get_progress(request, batch_id):
    query = ExampleAssignment.objects.filter(
        example__batch=batch_id,
        example__has_disagreement=True,
        user=request.user,
    )
    context = {}
    context["batch_id"] = batch_id
    context["done"] = query.filter(is_discussed=True).count()
    context["total"] = query.count()
    try:
        context["progress"] = int(context["done"] / context["total"] * 100)
    except ZeroDivisionError:
        context["progress"] = 100

    return render(request, "discuss/room.html#pbar", context)


def overview(request):
    user = request.user
    context = {"projects": {}}
    projects = Project.objects.filter(
        project_users__user=user,
        project_users__role=ProjectUser.Role.ANNOTATOR,
    )
    for project in projects.prefetch_related("batches"):
        batches = []
        for batch in project.batches.all():
            if not batch.phase == Batch.Phase.DISCUSSION:
                continue

            batch_data = {
                "batch": batch,
                "length": batch.examples.count(),
                "disagreement": Example.objects.filter(batch=batch, has_disagreement=True).count(),
            }
            batches.append(batch_data)

        context["projects"][project] = batches

    return render(request, "discuss/overview.html", context)


def chat_simple(request, batch_id):
    if request.method == "POST":
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))
    else:
        return render(request, "discuss/room.html", {"batch_id": batch_id})


def discuss_batch(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    context = {"sentences": batch.discuss_disagreement_sentences}
    return render(request, "discuss/discuss_batch.html", context)
