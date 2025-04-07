from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.generic import DetailView
from django.views.generic import View

from core.mixins import AnnotatorRequiredMixin
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


class PrevSentence(AnnotatorRequiredMixin, View):
    def get(self, request):
        """view is displayed when user clicks on <-"""
        filter = request.GET.get("filter", "none")
        assignment_id = request.GET.get("assignment_id")
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
            "annotation/index.html#sentence",
            "annotation/index.html#nav-block",
            "annotation/index.html#labels",
            "annotation/index.html#pbar",
        ]
        for partial in partials:
            response += render_to_string(partial, context)

        return HttpResponse(response)


class ReloadSentence(AnnotatorRequiredMixin, View):
    def get(self, request):
        """view is displayed when user clicks on ->"""
        context = {}
        filter = request.GET.get("filter", "none")
        assignment_id = request.GET.get("assignment_id")
        if filter == "unfinished":
            skip_annotated = True
        else:
            skip_annotated = False

        prev_assignment = ExampleAssignment.objects.get(id=assignment_id).previous()

        if prev_assignment:
            assignment = prev_assignment.next(
                skip_annotated=skip_annotated,
            )
        else:
            # if assignment is first assignment of batch
            assignment = ExampleAssignment.objects.get(id=assignment_id)
            if filter == "unfinished":
                assignment = assignment.next(skip_annotated=True)

        context.update(create_context(request, assignment, skip_annotated=skip_annotated))
        response = ""
        partials = [
            "annotation/index.html#sentence",
            "annotation/index.html#nav-block",
            "annotation/index.html#labels",
            "annotation/index.html#pbar",
        ]
        for partial in partials:
            response += render_to_string(partial, context)

        return HttpResponse(response)


class NextSentence(AnnotatorRequiredMixin, View):
    def get(self, request):
        """view is displayed when user clicks on ->"""
        context = {}
        filter = request.GET.get("filter", "none")
        assignment_id = request.GET.get("assignment_id")
        if filter == "unfinished":
            skip_annotated = True
        else:
            skip_annotated = False
        assignment = ExampleAssignment.objects.get(id=assignment_id).next(
            skip_annotated=skip_annotated,
        )
        context.update(create_context(request, assignment, skip_annotated=skip_annotated))
        response = ""
        partials = [
            "annotation/index.html#sentence",
            "annotation/index.html#nav-block",
            "annotation/index.html#labels",
            "annotation/index.html#pbar",
        ]
        for partial in partials:
            response += render_to_string(partial, context)

        return HttpResponse(response)


class AnnotateView(AnnotatorRequiredMixin, DetailView):
    template_name = "annotation/index.html"
    model = Batch

    def get_context_data(self, **kwargs):
        batch = self.get_object()
        context = super().get_context_data(**kwargs)
        assignment = (
            ExampleAssignment.objects.filter(user=self.request.user, example__batch=batch)
            .order_by("order")
            .first()
        )

        context = create_context(self.request, assignment)

        # TODO: CHANGE
        codebook = batch.project.codebook.get()
        context["codebook"] = codebook
        return context

    def get(
        self,
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

        # TODO: CHANGE
        codebook = batch.project.codebook.get()
        context["codebook"] = codebook

        return render(request, "annotation/index.html", context)


class EditAssignment(View):
    def get(self, request, assignment_id):  # noqa: ARG002
        assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
        batch = assignment.example.batch
        submitted_labels = [int(i) for i in self.request.POST.getlist("labels") if i.strip()]
        assignment.set_user_annotations(label_ids=submitted_labels, phase="ANNOTATION")

        context = {
            "has_prev": bool(assignment.previous()),
            "has_next": bool(assignment.next()),
            "saved": True,
            "assignment": assignment,
            "progress": get_progress(self.request.user, batch),
        }

        partials = [
            "annotation/index.html#nav-block",
            "annotation/index.html#pbar",
        ]
        response = ""
        for partial in partials:
            response += render_to_string(partial, context)

        return HttpResponse(response)

    def post(self, request, assignment_id, *args, **kwargs):  # noqa: ARG002
        assignment = ExampleAssignment.objects.filter(id=assignment_id).get()
        form = MultiLabelForm(request.POST, assignment=assignment)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Saved.")
        else:
            messages.error(self.request, f"Something was invalid: {form}")

        batch = assignment.example.batch
        submitted_labels = [int(i) for i in self.request.POST.getlist("labels") if i.strip()]
        assignment.set_user_annotations(label_ids=submitted_labels, phase="ANNOTATION")

        context = {
            "has_prev": bool(assignment.previous()),
            "has_next": bool(assignment.next()),
            "saved": True,
            "assignment": assignment,
            "progress": get_progress(self.request.user, batch),
        }

        partials = [
            "annotation/index.html#nav-block",
            "annotation/index.html#pbar",
        ]
        response = ""
        for partial in partials:
            response += render_to_string(partial, context)

        return HttpResponse(response)
