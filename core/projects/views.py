import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from django.views.generic import RedirectView
from django.views.generic import View
import pandas as pd

from .forms import BatchCreateForm
from .forms import BatchPhaseForm
from .forms import ProjectCreateForm
from core.mixins import AnnotatorRequiredMixin
from core.mixins import ExpertRequiredMixin
from data.models import Example
from data.models import ExampleAssignment
from discuss.models import Message
from projects.models import Batch
from projects.models import BatchAssignment
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("project-create") if self.request.user.is_staff else None
        return context


class ProjectCreateView(FormView):
    template_name = "projects/project_create.html"
    form_class = ProjectCreateForm

    def get_success_url(self):
        return reverse("project-detail", kwargs={"project_id": self.project.id})

    def form_valid(self, form):

        self.project = Project.objects.create(
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
        )

        project_users = []
        for user in form.cleaned_data["annotators"]:
            project_users.append(
                ProjectUser(
                    project=self.project,
                    user=user,
                    default_role=ProjectUser.Role.ANNOTATOR,
                ),
            )
        for user in form.cleaned_data["experts"]:
            project_users.append(
                ProjectUser(
                    project=self.project,
                    user=user,
                    default_role=ProjectUser.Role.EXPERT,
                ),
            )
        if project_users:
            ProjectUser.objects.bulk_create(project_users)

        label_names = self.request.POST.getlist("label_name")
        label_colors = self.request.POST.getlist("label_color")
        label_hotkeys = self.request.POST.getlist("label_hotkey")

        labels = []
        seen_names = set()
        seen_hotkeys = set()
        for name, color, hotkey in zip(label_names, label_colors, label_hotkeys, strict=False):
            name = (name or "").strip()
            if not name:
                continue
            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            hotkey = (hotkey or "").strip() or None
            if hotkey and hotkey.lower() in seen_hotkeys:
                continue
            if hotkey:
                seen_hotkeys.add(hotkey.lower())
            color = (color or "").strip() or None
            labels.append({"name": name, "color": color, "hotkey": hotkey})

        if labels:
            from data.models import Label

            Label.objects.bulk_create(
                [
                    Label(
                        project=self.project,
                        name=label["name"],
                        color=label["color"] or Label._meta.get_field("color").default,
                        hotkey=label["hotkey"],
                    )
                    for label in labels
                ],
            )

        return super().form_valid(form)


class ProjectBatchCreateView(ExpertRequiredMixin, View):
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        form = BatchCreateForm()
        return render(
            request,
            "projects/batch_create.html",
            {"project": project, "form": form},
        )

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        form = BatchCreateForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                "projects/batch_create.html",
                {"project": project, "form": form},
            )

        file = form.cleaned_data["file"]
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file)
        else:
            form.add_error("file", "Unsupported file type.")
            return render(
                request,
                "projects/batch_create.html",
                {"project": project, "form": form},
            )
        if "text" not in df.columns:
            form.add_error("file", "Missing required 'text' column.")
            return render(
                request,
                "projects/batch_create.html",
                {"project": project, "form": form},
            )

        batch = Batch(project=project)
        batch.save()

        default_annotators = project.annotators.all()
        batch_assignments = {
            annotator.id: BatchAssignment.objects.create(
                batch=batch,
                user=annotator,
                role=ProjectUser.Role.ANNOTATOR,
                phase=batch.current_phase,
            )
            for annotator in default_annotators
        }
        for _, row in df.iterrows():
            example = Example(batch=batch, content=row["text"])
            example.save()
            for annotator in default_annotators:
                ExampleAssignment.objects.create(
                    example=example,
                    batch_assignment=batch_assignments[annotator.id],
                )

        return redirect("project-detail", project_id=project.id)


class ProjectLabelRowView(View):
    def get(self, request):
        index = int(request.GET.get("index", 0))
        return render(request, "projects/partials/label_row.html", {"index": index})


class ProjectDetailView(RedirectView):
    model = Project

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        project_id = kwargs.get("project_id")
        project = get_object_or_404(Project, id=project_id)
        project_user = get_object_or_404(ProjectUser, project=project, user=self.request.user)

        if project_user.default_role == ProjectUser.Role.ANNOTATOR:
            return reverse("project-detail-annotator", kwargs={"project_id": project_id})
        elif project_user.default_role == ProjectUser.Role.EXPERT:
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
            projectuser__default_role=ProjectUser.Role.ANNOTATOR,
        )
        context["experts"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__default_role=ProjectUser.Role.EXPERT,
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
                "users": [],
            }
            # Query examples with disagreements and no expert decisions
            disagr_ex = [
                e
                for e in Example.objects.filter(batch=batch, batch__project_id=project.id)
                if e.has_disagreement and not e.has_expert_decision
            ]
            disagr_count = len(disagr_ex)
            batch_data["disagreement"] = disagr_count
            batch_data["disagr_after_discussion"] = len(
                [e for e in disagr_ex if e.has_disagreement_after_discussion],
            )
            disagr_ex_first_id = 0
            if disagr_count > 0:
                disagr_ex_first_id = sorted(disagr_ex, key=lambda e: e.id)[0].id
            batch_data["disagreement_first_id"] = disagr_ex_first_id

            disagr_ids = [e.id for e in disagr_ex]
            for annotator in context["annotators"]:
                annotated = (
                    ExampleAssignment.objects.filter(
                        batch_assignment__user=annotator,
                        example__batch=batch,
                        batch_assignment__phase=Batch.Phase.ANNOTATION,
                        done__isnull=False,
                    )
                    .distinct()
                    .count()
                )
                discussed = (
                    ExampleAssignment.objects.filter(
                        batch_assignment__user=annotator,
                        batch_assignment__phase=Batch.Phase.DISCUSSION,
                        done__isnull=False,
                        example_id__in=disagr_ids,
                    )
                    .distinct()
                    .count()
                )
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
            projectuser__default_role=ProjectUser.Role.ANNOTATOR,
        )
        context["experts"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__default_role=ProjectUser.Role.EXPERT,
        )
        context["codebook"] = project.codebook.get()

        # view for annotators
        context["batches"] = []
        batches = project.batches.all()
        for batch in batches:
            batch_data = {
                "batch": batch,
                "done": batch.examples.filter(
                    assignments__batch_assignment__user=self.request.user,
                    assignments__batch_assignment__phase=Batch.Phase.ANNOTATION,
                    assignments__done__isnull=False,
                )
                .distinct()
                .count(),
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
            batch.set_phase(new.current_phase)
            phase = batch.get_current_phase_display()
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
                    phase="ANNOTATION",
                    user=annotator,
                ).select_related("label")
                labels = [annotation.label.name for annotation in user_annotations]
                user_data = {"user": annotator.username, "labels": labels}
                row["labels"].append(user_data)

            # Discussed Annotation Data
            row["discussed_labels"] = []
            for annotator in annotators:
                user_annotations = example.get_user_annotations(
                    phase="DISCUSSION",
                    user=annotator,
                ).select_related("label")
                labels = [annotation.label.name for annotation in user_annotations]
                user_data = {"user": annotator.username, "labels": labels}
                row["discussed_labels"].append(user_data)

            # Discussed Annotation Data
            user_annotations = example.get_user_annotations(
                phase="EXPERT",
            ).select_related("label")
            labels = [annotation.label.name for annotation in user_annotations]
            row["expert_labels"] = labels

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
