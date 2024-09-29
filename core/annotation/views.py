from typing import Literal
from typing import Optional

from django.core.exceptions import PermissionDenied
from django.shortcuts import HttpResponse
from django.shortcuts import render

from data.models import Example
from data.models import ExampleAssignment
from projects.models import Batch


# Create your views here.
def annotate_batch(
    request, batch_id, assignment_id: int = None, cursor: Literal["next", "prev"] | None = None,
):
    batch = Batch.objects.get(id=batch_id)
    project = batch.project

    if assignment_id:
        assignment = ExampleAssignment.objects.get(id=assignment_id)
    else:
        assignment = (
            ExampleAssignment.objects.filter(user=request.user, example__batch=batch)
            .order_by("order")
            .first()
        )

    if cursor == "next":
        assignment = assignment.next()
    elif cursor == "prev":
        assignment = assignment.previous()

    has_next = True if assignment.next() else False
    has_prev = True if assignment.previous() else False
    example = assignment.example
    labels = project.labels.all()

    # Progress Bar
    done = batch.examples.filter(
        assignments__user=request.user, assignments__is_annotated=1,
    ).count()
    total = batch.examples.count()
    progress = {"done": done, "total": total, "current": (done / total * 100) if total > 0 else 0}

    previous_annotations = (
        assignment.annotations.filter(phase="ANNOTATION").select_related("label").all()
    )

    labels = []
    for label in example.labels.all():
        new = {
            "name": label.name,
            "id": label.id,
        }
        if label in previous_annotations:
            new["is_set"] = True
        else:
            new["is_set"] = False
        labels.append(new)

    context = {
        "project_id": project.id,
        "batch": batch,
        "example": example,
        "labels": labels,
        "assignment": assignment,
        "progress": progress,
        "has_next": has_next,
        "has_prev": has_prev,
    }

    if request.htmx:
        return render(request, "annotation/partials/annotation.html", context)
    else:
        return render(request, "annotation/batch.html", context)


def edit(request, assignment_id):
    assignment = ExampleAssignment.objects.get(id=assignment_id)
    batch = assignment.example.batch
    if batch.annotation_done:
        raise PermissionDenied()
    if assignment.user != request.user:
        raise PermissionDenied()

    submitted_labels = [int(i) for i in request.POST.getlist("labels") if i.strip()]
    assignment.set_user_annotations(label_ids=submitted_labels, phase="ANNOTATION")

    # Progress Bar
    # Progress Bar
    done = batch.examples.filter(
        assignments__user=request.user, assignments__is_annotated=1,
    ).count()
    total = batch.examples.count()
    progress = {"done": done, "total": total, "current": (done / total * 100) if total > 0 else 0}
    context = {
        "progress": progress,
        "saved": True,
    }
    return render(request, "annotation/partials/edit.html", context)
