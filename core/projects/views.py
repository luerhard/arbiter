import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import reverse
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import RedirectView
from django.views.generic import View
import pandas as pd

from .forms import BatchPhaseForm
from core.mixins import AnnotatorRequiredMixin
from core.mixins import ExpertRequiredMixin
from data.models import Example
from data.models import ExampleAssignment
from discuss.models import Message
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser

User = get_user_model()


log = logging.getLogger(__name__)


class ProjectListView(ListView):
    template_name = "projects/project_list.html"
    model = ProjectUser
    context_object_name = "project_users"

    def get_queryset(self):
        return (
            ProjectUser.objects.filter(user=self.request.user)
            .prefetch_related("project")
            .order_by("-project__pk")
        )


class ProjectDetailView(RedirectView):
    model = Project

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        project_id = kwargs.get("project_id")
        project = get_object_or_404(Project, id=project_id)
        project_user = get_object_or_404(ProjectUser, project=project, user=self.request.user)

        if project_user.role == ProjectUser.Role.ANNOTATOR:
            return reverse("project-detail-annotator", kwargs={"project_id": project_id})
        elif project_user.role == ProjectUser.Role.EXPERT:
            return reverse("project-detail-expert", kwargs={"project_id": project_id})
        else:
            return reverse("home")


class ProjectExpertDetailView(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "project_id"
    model = Project
    template_name = "projects/project-detail-expert.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        all_project_users = User.objects.filter(projectuser__project=project)

        # get assigned users
        context["annotators"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__role=ProjectUser.Role.ANNOTATOR,
        )
        context["experts"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__role=ProjectUser.Role.EXPERT,
        )
        context["codebook"] = project.codebook.get()

        # get associated batches
        batches = project.batches.all()
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

        log.debug(f"Providing the following context to the Expert: {context}")
        return context


class ProjectAnnotatorDetailView(AnnotatorRequiredMixin, DetailView):
    pk_url_kwarg = "project_id"
    model = Project
    template_name = "projects/project-detail-annotator.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        all_project_users = User.objects.filter(projectuser__project=project)

        # get assigned users
        context["annotators"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__role=ProjectUser.Role.ANNOTATOR,
        )
        context["experts"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__role=ProjectUser.Role.EXPERT,
        )
        context["codebook"] = project.codebook.get()

        # view for annotators
        context["batches"] = []
        batches = project.batches.all()
        for batch in batches:
            batch_data = {
                "batch": batch,
                "done": batch.examples.filter(
                    assignments__user=self.request.user,
                    assignments__is_annotated=1,
                ).count(),
                "length": batch.examples.count(),
            }
            context["batches"].append(batch_data)
        log.debug(f"Providing the following context to the Annotator: {context}")
        return context


class ChangeBatchPhase(ExpertRequiredMixin, View):
    def post(self, request, batch_id, *args, **kwargs):  # noqa: ARG002
        batch = get_object_or_404(Batch, id=batch_id)
        form = BatchPhaseForm(request.POST, instance=batch)
        if form.is_valid():
            new = form.save(commit=False)
            batch.set_phase(new.phase)
            phase = batch.get_phase_display()
            messages.success(request, f"Phase updated to {phase}.")
            return HttpResponse(status=204)
        else:
            msg = "invalid form"
            raise Exception(msg)


class ExportBatch(ExpertRequiredMixin, View):
    def get(self, request, batch_id, *args, **kwargs):  # noqa: ARG002
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
