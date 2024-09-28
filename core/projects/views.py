from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import HttpResponse
from django.shortcuts import render
from django.views.generic import DetailView
from django.views.generic import ListView
import pandas as pd

from data.models import Annotation
from discuss.models import Message
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser

User = get_user_model()


def project_list_view(request):
    projects = Project.objects.filter(project_users__user=request.user)
    context = {"projects": projects}
    return render(request, "projects/project_list.html", context)


def project_detail_view(request, project_id):
    project = Project.objects.get(id=project_id)

    all_project_users = User.objects.filter(projectuser__project=project)
    project_user = ProjectUser.objects.get(project=project, user=request.user)

    context = {}
    context["project"] = project

    # get assigned users
    context["annotators"] = all_project_users.filter(projectuser__role=ProjectUser.Role.ANNOTATOR)
    context["experts"] = all_project_users.filter(projectuser__role=ProjectUser.Role.EXPERT)

    # get associated batches
    batches = context["project"].batches.all()

    if project_user.role == ProjectUser.Role.ANNOTATOR:
        context["batches"] = []
        for batch in batches:
            batch_data = {
                "batch": batch,
                "done": batch.examples.filter(
                    assignments__user=request.user, assignments__is_annotated=1
                ).count(),
                "length": batch.examples.count(),
            }
            context["batches"].append(batch_data)
        return render(request, "projects/project_detail_annotator.html", context)
    elif project_user.role == ProjectUser.Role.EXPERT:
        return HttpResponse("TEST")
    else:
        msg = "Unkown User Role"
        raise Exception(msg)


class ProjectListView(ListView):
    model = Project
    context_object_name = "projects"
    template_name = "projects/manage_projects.html"

    def get_queryset(self):
        # for simplicity now: show admin all projects
        if "Admin" in (group.name for group in self.request.user.groups.all()):
            return self.model.objects.all()
        else:
            return self.model.objects.filter(users=self.request.user)


class ProjectDetailView(DetailView):
    model = Project
    context_object_name = "project"
    template_name = "admin_panel/manage_project_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        if self.request.user not in self.get_queryset().first().experts:
            raise PermissionDenied()

        context = super().get_context_data(**kwargs)

        # can probably be a single db query
        context["annotators"] = User.objects.filter(
            projectuser__project=context["project"],
            projectuser__role=ProjectUser.Role.ANNOTATOR,
        )
        context["experts"] = User.objects.filter(
            projectuser__project=context["project"],
            projectuser__role=ProjectUser.Role.EXPERT,
        )

        batches = context["project"].batches.all()
        context["batches"] = []
        for batch in batches:
            batch_data = {
                "batch": batch,
                "annotation_done": batch.annotation_done,
                "batch_users": [],
                "length": batch.examples.count(),
                "is_discussed": batch.examples.filter(is_discussed=True).count(),
            }

            for user in context["annotators"]:
                already_annotated = batch.examples.already_annotated_count.sum()
                b = {
                    "user": user.username,
                    "annotated": already_annotated,
                }
                batch_data["batch_users"].append(b)
            context["batches"].append(batch_data)
        return context


def toggle_finalize(request):
    # TODO: check for access control
    if request.method == "POST":
        batch_id = request.POST.get("batch")
        if batch_id is None:
            msg = "batch id was none!"
            raise Exception(msg)

    batch = Batch.objects.get(id=batch_id)

    if batch.annotation_done:
        batch.annotation_done = False
        for example in batch.examples.all():
            example.has_disagreement_labels = None
            example.save()
    else:
        examples = (
            batch.examples.prefetch_related("user_annotations")
            .prefetch_related("user_annotations__user")
            .all()
        )

        for example in examples:
            user_annotations = example.user_annotations.all()
            annotation_groups = {user: set() for user in {anno.user for anno in user_annotations}}
            for user_annotation in user_annotations:
                if user_annotation.is_set:
                    annotation_groups[user_annotation.user].add(user_annotation.label_id)
            annotations = list(annotation_groups.values())
            if not all(annotation == annotations[0] for annotation in annotations):
                example.has_disagreement_labels = True
            else:
                example.has_disagreement_labels = False
            example.save()
        batch.annotation_done = True

    batch.save()

    response = f'<div class="fadeout-2" id="output{batch_id}"><i class="bi bi-check"></i></div>'
    return HttpResponse(response)


def _iter_batch_examples(batch_id):
    batch = Batch.objects.prefetch_related("examples").get(id=batch_id)
    examples = batch.examples
    for sent in examples.all():
        row = {
            "batch_number": batch.batch_number,
            "text_id": sent.id,
            "text": sent.content,
            "is_discussed": sent.is_discussed,
            "has_disagreement_labels": sent.has_disagreement_labels,
        }
        yield row, sent


def _get_user_annotations(example):
    annotations = Annotation.objects.prefetch_related("label").filter(example=example).all()
    labels = []
    for annotation in annotations.all():
        group = {
            "user": annotation.user.username,
            "label": annotation.label.name,
            "is_set": annotation.is_set,
        }
        labels.append(group)
    return labels


def _get_confirmed_annotations(example):
    annotations_qs = (
        ConfirmedAnnotation.objects.prefetch_related("label").filter(example=example).all()
    )
    labels = []
    for annotation in annotations_qs.all():
        group = {
            "user": annotation.user.username,
            "label": annotation.label.name,
            "is_set": annotation.is_set,
        }
        labels.append(group)
    return labels


def export_annotations(request, batch_id):  # noqa: ARG001
    rows = []
    for row, example in _iter_batch_examples(batch_id):
        row["labels"] = _get_user_annotations(example)
        rows.append(row)

    df = pd.DataFrame(rows)
    json = df.to_json(orient="records", lines=True)

    batch = Batch.objects.get(id=batch_id)
    response = HttpResponse(json, content_type="application/text")
    response["Content-Disposition"] = (
        f"attachment; filename=annotations_batch_{batch.batch_number}.jsonl"
    )

    return response


def _get_messages(example):
    messages_qs = Message.objects.filter(example=example).order_by("created_at").all()
    messages = []
    for message in messages_qs.all():
        group = {
            "user": message.user,
            "date": message.created_at,
            "content": message.message,
        }
        messages.append(group)
    return messages


def export_confirmed_annotations(request, batch_id):  # noqa: ARG001
    rows = []
    for row, example in _iter_batch_examples(batch_id):
        row["confirmed_labels"] = _get_confirmed_annotations(example)
        row["messages"] = _get_messages(example)
        rows.append(row)

    df = pd.DataFrame(rows)

    json = df.to_json(orient="records", lines=True)

    batch = Batch.objects.get(id=batch_id)
    response = HttpResponse(json, content_type="application/text")
    response["Content-Disposition"] = (
        f"attachment; filename=confirmedannotations_batch_{batch.batch_number}.jsonl"
    )

    return response


def export_batch(request, batch_id):  # noqa: ARG001
    rows = []
    for row, example in _iter_batch_examples(batch_id):
        row["labels"] = _get_user_annotations(example)
        row["confirmed_labels"] = _get_confirmed_annotations(example)
        row["messages"] = _get_messages(example)
        rows.append(row)

    df = pd.DataFrame(rows)

    json = df.to_json(orient="records", lines=True)

    batch = Batch.objects.get(id=batch_id)
    response = HttpResponse(json, content_type="application/text")
    response["Content-Disposition"] = f"attachment; filename=batch_{batch.batch_number}.jsonl"

    return response
