from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from data.forms import MultiLabelForm
from data.models import ExampleAssignment
from projects.models import Batch


def get_progress(user, batch):
    """helper function to calculate current progress"""
    done = batch.examples.filter(
        assignments__user=user,
        assignments__is_annotated=1,
    ).count()
    total = batch.examples.count()
    try:
        current = int(done / total * 100)
    except ZeroDivisionError:
        current = 100

    return {"done": done, "total": total, "current": current}


def create_context(request, assignment, skip_annotated: bool = False):
    """helper function to create context needed in multiple views"""
    example = assignment.example

    previous_annotations = (
        assignment.annotations.filter(phase="ANNOTATION").select_related("label").all()
    )

    sub_context = {}
    sub_context["assignment"] = assignment
    sub_context["has_next"] = bool(assignment.next(skip_annotated=skip_annotated))
    sub_context["has_prev"] = bool(assignment.previous(skip_annotated=skip_annotated))
    sub_context["example"] = assignment.example
    sub_context["batch"] = example.batch
    sub_context["progress"] = get_progress(request.user, example.batch)

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
    """view is displayed when user clicks on <-"""
    filter = request.GET.get("filter", "none")
    if filter == "unfinished":
        skip_annotated = True
    else:
        skip_annotated = False
    context = {}
    assignment = ExampleAssignment.objects.get(id=assignment_id).previous(
        skip_annotated=skip_annotated,
    )
    context.update(create_context(request, assignment, skip_annotated=skip_annotated))
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
    """view is displayed when user clicks on ->"""
    context = {}
    filter = request.GET.get("filter", "none")
    if filter == "unfinished":
        skip_annotated = True
    else:
        skip_annotated = False
    assignment = ExampleAssignment.objects.get(id=assignment_id).next(skip_annotated=skip_annotated)
    context.update(create_context(request, assignment, skip_annotated=skip_annotated))
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


def annotate_batch(
    request,
    batch_id,
    assignment_id: int = None,
):
    batch = Batch.objects.get(id=batch_id)

    if assignment_id:
        assignment = ExampleAssignment.objects.get(id=assignment_id)
    else:
        assignment = (
            ExampleAssignment.objects.filter(user=request.user, example__batch=batch)
            .order_by("order")
            .first()
        )

    context = create_context(request, assignment)
    return render(request, "annotation/batch.html", context)


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
        "has_prev": bool(assignment.previous()),
        "has_next": bool(assignment.next()),
        "saved": True,
        "assignment": assignment,
        "progress": get_progress(request.user, batch),
    }

    partials = [
        "annotation/batch.html#nav-block",
        "annotation/batch.html#pbar",
    ]
    response = ""
    for partial in partials:
        response += render_to_string(partial, context)

    return HttpResponse(response)
