import json
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.text import slugify
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
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole
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

    @staticmethod
    def _jsonify_users(users):
        out = []
        for user in users:
            out.append({"id": user.id, "username": user.username})
        return json.dumps(out)


class ProjectCreateView(FormView):
    template_name = "projects/project_create.html"
    form_class = ProjectCreateForm

    def get_success_url(self):
        return reverse("project-detail", kwargs={"project_id": self.project.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        if form is not None:
            context["form"] = form
        return context

    def form_valid(self, form):

        self.project = Project.objects.create(
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            owner=self.request.user,
        )

        project_users = []
        for user in form.cleaned_data["annotators"]:
            project_users.append(
                ProjectUser(
                    project=self.project,
                    user=user,
                    default_role=ProjectRole.ANNOTATOR,
                ),
            )
        for user in form.cleaned_data["experts"]:
            project_users.append(
                ProjectUser(
                    project=self.project,
                    user=user,
                    default_role=ProjectRole.EXPERT,
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


class ProjectBatchCreateView(ExpertRequiredMixin, FormView):
    template_name = "projects/batch_create.html"
    form_class = BatchCreateForm

    def get_success_url(self):
        return reverse("project-detail", kwargs={"project_id": self.kwargs.get("project_id")})

    @staticmethod
    def _jsonify_users(users):
        out = []
        for user in users:
            out.append({"id": user.id, "username": user.username})
        return json.dumps(out)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        project_id = self.kwargs.get("project_id")
        project = get_object_or_404(Project, id=project_id)
        if form is not None:
            context["project"] = project
            context["annotators_selected_users"] = self._jsonify_users(project.annotators.all())
            context["experts_selected_users"] = self._jsonify_users(project.experts.all())
        return context

    def form_valid(self, form):

        project_id = self.kwargs.get("project_id")
        project = get_object_or_404(Project, id=project_id)

        file = form.cleaned_data["file"]
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file)
        else:
            form.add_error("file", "Unsupported file type.")
        if "text" not in df.columns:
            form.add_error("file", "Missing required 'text' column.")

        batch = Batch.objects.create(project=project)

        examples = []
        for _, row in df.iterrows():
            examples.append(Example(batch=batch, content=row["text"]))
        Example.objects.bulk_create(examples)

        annotators = form.cleaned_data["annotators"]
        batch.users.add(*annotators, through_defaults={"role": ProjectRole.ANNOTATOR})

        experts = form.cleaned_data["experts"]
        batch.users.add(*experts, through_defaults={"role": ProjectRole.EXPERT})

        batch.set_phase(BatchPhase.ANNOTATION)

        return super().form_valid(form)


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

        if project_user.default_role == ProjectRole.ANNOTATOR:
            return reverse("project-detail-annotator", kwargs={"project_id": project_id})
        elif project_user.default_role == ProjectRole.EXPERT:
            return reverse("project-detail-expert", kwargs={"project_id": project_id})
        else:
            return reverse("home")


class ProjectExpertDetailView(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "project_id"
    model = Project
    template_name = "projects/project_detail_expert.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        all_project_users = User.objects.filter(projectuser__project=project)

        # get assigned users
        context["annotators"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__default_role=ProjectRole.ANNOTATOR,
        )
        context["experts"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__default_role=ProjectRole.EXPERT,
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
            ann_disagr_ex = batch.disagreements(BatchPhase.ANNOTATION)
            ann_disagr_count = ann_disagr_ex.count()
            batch_data["disagreement"] = ann_disagr_count

            disc_disagr_ex = batch.disagreements(BatchPhase.DISCUSSION)
            batch_data["disc_disagreement"] = disc_disagr_ex.count()
            batch_data["expert_dec"] = len([e for e in disc_disagr_ex if e.has_expert_decision])

            ann_disagr_ex_first_id = 0
            if ann_disagr_count > 0:
                ann_disagr_ex_first_id = sorted(ann_disagr_ex, key=lambda e: e.id)[0].id
            batch_data["disagreement_first_id"] = ann_disagr_ex_first_id

            disagr_ids = [e.id for e in ann_disagr_ex]
            for annotator in context["annotators"]:
                annotated = (
                    ExampleAssignment.objects.filter(
                        user=annotator,
                        batch=batch,
                        phase=BatchPhase.ANNOTATION,
                        done__isnull=False,
                    )
                    .distinct()
                    .count()
                )
                discussed = (
                    ExampleAssignment.objects.filter(
                        user=annotator,
                        phase=BatchPhase.DISCUSSION,
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
    template_name = "projects/project_detail_annotator.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        all_project_users = User.objects.filter(projectuser__project=project)

        # get assigned users
        context["annotators"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__default_role=ProjectRole.ANNOTATOR,
        )
        context["experts"] = all_project_users.filter(
            projectuser__project=project,
            projectuser__default_role=ProjectRole.EXPERT,
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
                    assignments__phase=BatchPhase.ANNOTATION,
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


def _generate_batch_data(batch):
    annotators = batch.assignees(role=ProjectRole.ANNOTATOR).order_by("username")
    experts = batch.assignees(role=ProjectRole.EXPERT).order_by("username")

    shared_data = {
        "batch_number": batch.batch_number,
        "batch_annotators": [a.username for a in annotators.all()],
        "batch_experts": [a.username for a in experts.all()],
    }

    assignments = (
        batch.assignments.filter(done__isnull=False)
        .select_related("user")
        .prefetch_related("annotations__label")
        .order_by("example_id", "user__username")
    )

    rows = {}
    for assignment in assignments.all():
        ex = assignment.example
        if ex.id not in rows:
            row = {
                "text_id": ex.id,
                "text": ex.content,
                "labels_annotation": [],
                "labels_discussion": [],
                "messages_discussion": [],
                "labels_expert": [],
                **shared_data,
            }
            rows[ex.id] = row

        label_data = {
            "user": assignment.user.username,
            "labels": sorted([a.label.name for a in assignment.annotations.all()]),
            "at": timezone.localtime(assignment.done).isoformat(timespec="milliseconds"),
        }

        phase = assignment.phase
        if phase == BatchPhase.ANNOTATION:
            rows[ex.id]["labels_annotation"].append(label_data)
        elif phase == BatchPhase.DISCUSSION:
            rows[ex.id]["labels_discussion"].append(label_data)
        elif phase == BatchPhase.EXPERT:
            rows[ex.id]["labels_expert"].append(label_data)

    # Chat Messages
    for example_id in rows.keys():
        messages_qs = Message.objects.filter(example=example_id).order_by("created_at").all()
        messages = []
        for message in messages_qs.all():
            msg = {
                "user": message.user,
                "at": timezone.localtime(message.created_at).isoformat(timespec="milliseconds"),
                "content": message.message,
            }
            messages.append(msg)
        rows[example_id]["messages_discussion"] = messages

    df = pd.DataFrame(rows.values())

    return df


class ExportProject(ExpertRequiredMixin, View):
    def get(self, request, project_id, *args, **kwargs):  # noqa: ARG002
        project = Project.objects.get(id=project_id)
        dfs = []
        for batch in project.batches.order_by("batch_number").all():
            df = _generate_batch_data(batch)
            dfs.append(df)
        df = pd.concat(dfs, axis=0)
        json_data = df.to_json(orient="records", lines=True)

        response = HttpResponse(json_data, content_type="application/text")
        safe_name = slugify(project.name)
        response["Content-Disposition"] = f"attachment; filename=project_{safe_name}.jsonl"

        return response


class ExportBatch(ExpertRequiredMixin, View):
    def get(self, request, batch_id, *args, **kwargs):  # noqa: ARG002
        batch = Batch.objects.get(id=batch_id)
        df = _generate_batch_data(batch)
        json_data = df.to_json(orient="records", lines=True)

        response = HttpResponse(json_data, content_type="application/text")
        response["Content-Disposition"] = f"attachment; filename=batch_{batch.batch_number}.jsonl"

        return response


class HtmxUserSearch(View):
    def get(self, request, **kwargs):  # noqa: ARG002
        query = (request.GET.get("q") or "").strip()

        if query:
            users = User.objects.filter(username__icontains=query).order_by("username")[:5]
        else:
            users = User.objects.all()[:5]
        return render(
            request,
            "projects/partials/user_search_results.html",
            {"users": users},
        )
