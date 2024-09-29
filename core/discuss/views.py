from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse

from data.models import Example
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser

# Create your views here.


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


def done(request):  # noqa: ARG001
    return HttpResponse("ALL DONE.")


def chat_simple(request, batch_id):
    if request.method == "POST":
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))
    else:
        return render(request, "discuss/room.html", {"batch_id": batch_id})


def discuss_batch(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    context = {"sentences": batch.discuss_disagreement_sentences}
    return render(request, "discuss/discuss_batch.html", context)
