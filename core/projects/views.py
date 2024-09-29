from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
import pandas as pd

from .forms import BatchPhaseForm
from data.models import Example
from data.models import ExampleAssignment
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
    project = get_object_or_404(Project, id=project_id)

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
        # view for annotators
        context["batches"] = []
        for batch in batches:
            batch_data = {
                "batch": batch,
                "done": batch.examples.filter(
                    assignments__user=request.user,
                    assignments__is_annotated=1,
                ).count(),
                "length": batch.examples.count(),
            }
            context["batches"].append(batch_data)
        return render(request, "projects/project_detail_annotator.html", context)

    elif project_user.role == ProjectUser.Role.EXPERT:
        # view for experts
        context["batches"] = []
        for batch in batches:
            batch_data = {
                "batch": batch,
                "batch_phase_form": BatchPhaseForm(instance=batch),
                "length": batch.examples.count(),
                "disagreement": Example.objects.filter(batch=batch, has_disagreement=True).count(),
                "users": [],
            }
            for annotator in context["annotators"]:
                annotated = ExampleAssignment.objects.filter(
                    user=annotator,
                    example__batch=batch,
                    is_annotated=True,
                ).count()
                discussed = ExampleAssignment.objects.filter(
                    user=annotator,
                    example__batch=batch,
                    is_discussed=True,
                ).count()
                user_data = {"user": annotator, "annotated": annotated, "discussed": discussed}
                batch_data["users"].append(user_data)
            context["batches"].append(batch_data)

        return render(request, "projects/project_detail_expert.html", context)
    else:
        msg = f"Unkown User Role {project_user.role}"
        raise Exception(msg)


def change_batch_phase(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == "POST":
        form = BatchPhaseForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            phase = batch.get_phase_display()
            messages.success(request, f"Phase updated to {phase}.")
            return HttpResponse(status=204)
    else:
        form = BatchPhaseForm(instance=batch)

    return render(request)


def export_batch(request, batch_id):  # noqa: ARG001
    batch = Batch.objects.get(id=batch_id)
    labels = batch.project.labels
    annotators = batch.project.annotators
    examples = batch.examples

    rows = []
    for example in examples.all():
        row = {
            "batch_number": batch.batch_number,
            "text_id": example.id,
            "text": example.content,
        }
        # Annotation Data
        row["labels"] = []
        for annotator in annotators:
            user_annotations = example.get_user_annotations(
                user=annotator,
                phase="ANNOTATION",
            ).select_related("label")
            labels = [annotation.label.name for annotation in user_annotations]
            user_data = {"user": annotator.username, "labels": labels}
            row["labels"].append(user_data)

        # Discussed Annotation Data
        row["discussed_labels"] = []
        for annotator in annotators:
            user_annotations = example.get_user_annotations(
                user=annotator,
                phase="DISCUSSION",
            ).select_related("label")
            labels = [annotation.label.name for annotation in user_annotations]
            user_data = {"user": annotator.username, "labels": labels}
            row["labels"].append(user_data)

        # Chat Messages
        row["messages"] = []
        messages_qs = Message.objects.filter(example=example).order_by("created_at").all()
        for message in messages_qs.all():
            group = {
                "user": message.user,
                "date": message.created_at,
                "content": message.message,
            }
            row["messages"].append(group)
        rows.append(row)

    df = pd.DataFrame(rows)

    json_data = df.to_json(orient="records", lines=True)

    batch = Batch.objects.get(id=batch_id)
    response = HttpResponse(json_data, content_type="application/text")
    response["Content-Disposition"] = f"attachment; filename=batch_{batch.batch_number}.jsonl"

    return response
