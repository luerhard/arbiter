from typing import Literal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse

from data.forms import MultiLabelForm
from data.models import ExampleAssignment
from projects.models import Batch


def create_context(request, assignment):
    example = assignment.example

    previous_annotations = (
        assignment.annotations.filter(phase="ANNOTATION").select_related("label").all()
    )

    sub_context = {}
    sub_context["assignment"] = assignment
    sub_context["has_next"] = True if assignment.next() else False
    sub_context["has_prev"] = True if assignment.previous() else False
    sub_context["example"] = assignment.example
    sub_context["batch"] = example.batch

    done = example.batch.examples.filter(
        assignments__user=request.user,
        assignments__is_annotated=1,
    ).count()
    total = example.batch.examples.count()
    progress = {"done": done, "total": total, "current": (done / total * 100) if total > 0 else 0}

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
    sub_context["labels"] = labels

    form = MultiLabelForm(assignment=assignment)
    sub_context["label_form"] = form

    return sub_context


def prev_sentence(request, assignment_id):
    context = {}
    assignment = ExampleAssignment.objects.get(id=assignment_id).previous()
    context.update(create_context(request, assignment))
    response = ""
    partials = [
        "annotation/batch.html#sentence",
        "annotation/batch.html#nav-block",
        "annotation/batch.html#labels",
        "annotation/batch.html#pbar",
    ]
    for partial in partials:
        response += render_to_string(partial, context)

    return HttpResponse(response)


def next_sentence(request, assignment_id):
    context = {}
    assignment = ExampleAssignment.objects.get(id=assignment_id).next()
    context.update(create_context(request, assignment))
    response = ""
    partials = [
        "annotation/batch.html#sentence",
        "annotation/batch.html#nav-block",
        "annotation/batch.html#labels",
        "annotation/batch.html#pbar",
    ]
    for partial in partials:
        response += render_to_string(partial, context)

    return HttpResponse(response)


# Create your views here.
def annotate_batch(
    request,
    batch_id,
    assignment_id: int = None,
):
    """This is some text - wow"""
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

    context = create_context(request, assignment)

    response = render(request, "annotation/batch.html", context)
    if request.htmx:
        response["Hx-Replace-Url"] = reverse(
            "annotate-batch",
            kwargs={"batch_id": batch.id, "assignment_id": assignment.id},
        )
    return response


def edit(request, assignment_id):
    assignment = ExampleAssignment.objects.get(id=assignment_id)
    batch = assignment.example.batch
    if batch.phase != Batch.Phase.ANNOTATION:
        raise PermissionDenied()
    if assignment.user != request.user:
        raise PermissionDenied()

    if request.method == "POST":
        form = MultiLabelForm(request.POST, assignment=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
        else:
            messages.error(request, f"Something was invalid: {form}")

    submitted_labels = [int(i) for i in request.POST.getlist("labels") if i.strip()]
    assignment.set_user_annotations(label_ids=submitted_labels, phase="ANNOTATION")

    context = {
        "has_prev": True if assignment.previous() else False,
        "has_next": True if assignment.next() else False,
        "saved": True,
        "assignment": assignment,
    }

    return render(request, "annotation/batch.html#nav-block", context)
