import json
import logging
import shutil

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.functional import cached_property
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
from core.mixins import AnyRoleRequiredMixin
from core.mixins import ExpertRequiredMixin
from data.models import Example
from data.models import Label
from discuss.models import Message
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import BatchUser
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser

User = get_user_model()


log = logging.getLogger(__name__)


def _users_json(users) -> str:
    """Users as JSON for the preselected entries of the user search."""
    return json.dumps([{"id": user.id, "username": user.username} for user in users])


class ProjectListView(ListView):
    template_name = "projects/project_list.html"
    model = ProjectUser
    context_object_name = "project_users"

    def get_queryset(self):
        return (
            ProjectUser.objects.filter(user=self.request.user)
            .select_related("project")
            .order_by("-project__pk")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("project-create") if self.request.user.is_staff else None
        return context


class ProjectDeleteView(View):
    """Delete a project with everything in it. Only its owner may do this."""

    def post(self, request, project_id, *args, **kwargs):  # noqa: ARG002
        project = get_object_or_404(Project, id=project_id)
        if project.owner_id != request.user.id:
            return HttpResponseForbidden("Only the owner can delete this project.")

        # the codebook's git repository is a folder on disk, deleted after the database rows
        codebook_dirs = [
            codebook.file.parent for codebook in project.codebook.all() if codebook.git_dir
        ]
        project.delete()  # one transaction, including the chat rooms (discuss.signals)
        for path in codebook_dirs:
            shutil.rmtree(path, ignore_errors=True)

        messages.success(request, f"Project {project.name} deleted.")
        return redirect("project-list")


class ProjectCreateView(FormView):
    template_name = "projects/project_create.html"
    form_class = ProjectCreateForm

    def get_success_url(self):
        return reverse("project-detail", kwargs={"project_id": self.project.id})

    def form_valid(self, form):
        self.project = Project.objects.create(
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            owner=self.request.user,
        )
        ProjectUser.objects.bulk_create(
            [
                ProjectUser(project=self.project, user=user, default_role=role)
                for field, role in (
                    ("annotators", ProjectRole.ANNOTATOR),
                    ("experts", ProjectRole.EXPERT),
                )
                for user in form.cleaned_data[field]
            ],
        )
        Label.objects.bulk_create(
            Label(project=self.project, **label) for label in _labels_from_post(self.request.POST)
        )
        return super().form_valid(form)


def _labels_from_post(post) -> list[dict]:
    """The label rows of the project form, minus empty names and duplicate names or keys."""
    default_color = Label._meta.get_field("color").default
    labels = []
    seen_names, seen_hotkeys = set(), set()
    rows = zip(
        post.getlist("label_name"),
        post.getlist("label_color"),
        post.getlist("label_hotkey"),
        strict=False,
    )
    for name, color, hotkey in rows:
        name = (name or "").strip()
        hotkey = (hotkey or "").strip() or None
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        if hotkey and hotkey.lower() in seen_hotkeys:
            continue
        if hotkey:
            seen_hotkeys.add(hotkey.lower())
        labels.append(
            {"name": name, "color": (color or "").strip() or default_color, "hotkey": hotkey}
        )
    return labels


class ProjectBatchCreateView(ExpertRequiredMixin, FormView):
    template_name = "projects/batch_create.html"
    form_class = BatchCreateForm

    @cached_property
    def project(self):
        return get_object_or_404(Project, id=self.kwargs["project_id"])

    def get_success_url(self):
        return reverse("project-detail", kwargs={"project_id": self.project.id})

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "project": self.project}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        context["annotators_selected_users"] = _users_json(self.project.annotators)
        context["experts_selected_users"] = _users_json(self.project.experts)
        return context

    def form_valid(self, form):
        batch = Batch.objects.create(project=self.project)
        Example.objects.bulk_create(
            Example(batch=batch, content=text, metadata=metadata, position=position)
            for position, (text, metadata) in enumerate(form.examples, start=1)
        )
        batch.users.add(
            *form.cleaned_data["annotators"], through_defaults={"role": ProjectRole.ANNOTATOR}
        )
        batch.users.add(
            *form.cleaned_data["experts"], through_defaults={"role": ProjectRole.EXPERT}
        )
        batch.set_phase(BatchPhase.ANNOTATION)
        return super().form_valid(form)


class ProjectLabelRowView(View):
    def get(self, request):
        index = int(request.GET.get("index", 0))
        return render(request, "projects/partials/label_row.html", {"index": index})


class ProjectDetailView(RedirectView):
    """Experts land on the page that manages the project, annotators on their batches."""

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        member = get_object_or_404(
            ProjectUser, project_id=kwargs["project_id"], user=self.request.user
        )
        page = (
            "project-detail-expert"
            if member.default_role == ProjectRole.EXPERT
            else "project-detail-annotator"
        )
        return reverse(page, kwargs={"project_id": kwargs["project_id"]})


_PHASE_FLOW = [BatchPhase.ANNOTATION, BatchPhase.DISCUSSION, BatchPhase.EXPERT, BatchPhase.FINAL]


def _phase_steps(batch) -> list[dict]:
    """The phases of a batch as steps (done/current/todo) for the phase stepper."""
    current = batch.current_phase
    position = _PHASE_FLOW.index(current) if current in _PHASE_FLOW else -1
    steps = []
    for index, phase in enumerate(_PHASE_FLOW):
        if index < position or (index == position and phase == BatchPhase.FINAL):
            state = "done"
        elif index == position:
            state = "current"
        else:
            state = "todo"
        steps.append({"phase": phase, "label": phase.label, "state": state})
    return steps


class _ProjectPageMixin:
    """Shared by both project pages: the team and codebook for the side column, and the
    user's role per batch (self.batch_roles: batch id -> role)."""

    pk_url_kwarg = "project_id"
    model = Project

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        context["annotators"] = project.annotators
        context["experts"] = project.experts
        context["codebook"] = project.codebook.get()
        self.batch_roles = dict(
            BatchUser.objects.filter(user=self.request.user, batch__project=project).values_list(
                "batch_id",
                "role",
            ),
        )
        return context


class ProjectExpertDetailView(ExpertRequiredMixin, _ProjectPageMixin, DetailView):
    template_name = "projects/project_detail_expert.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_annotation_work"] = ProjectRole.ANNOTATOR in self.batch_roles.values()
        context["batches"] = [
            self._batch_card(batch) for batch in self.object.batches.order_by("-batch_number")
        ]
        return context

    def _batch_card(self, batch) -> dict:
        """Everything a batch card shows: phase stepper, progress per annotator, open decisions."""
        annotation_disagreements = batch.disagreements(BatchPhase.ANNOTATION)
        discussion_disagreements = batch.disagreements(BatchPhase.DISCUSSION)
        length = batch.examples.count()

        users = []
        for annotator in batch.assignees(role=ProjectRole.ANNOTATOR).order_by("username"):
            done = batch.assignments.filter(user=annotator).done()
            users.append(
                {
                    "user": annotator,
                    "annotated": done.filter(phase=BatchPhase.ANNOTATION).count(),
                    "discussed": done.filter(
                        phase=BatchPhase.DISCUSSION,
                        example__in=annotation_disagreements,
                    ).count(),
                },
            )

        disc_disagreement = discussion_disagreements.count()
        expert_dec = discussion_disagreements.filter(
            assignments__phase=BatchPhase.EXPERT,
            assignments__done__isnull=False,
        ).count()
        return {
            "batch": batch,
            "batch_phase_form": BatchPhaseForm(instance=batch),
            "is_batch_expert": self.batch_roles.get(batch.id) == ProjectRole.EXPERT,
            "steps": _phase_steps(batch),
            "length": length,
            "users": users,
            "annotated_total": sum(u["annotated"] for u in users),
            "annotated_max": length * len(users),
            "disagreement": annotation_disagreements.count(),
            "discussed": users[0]["discussed"] if users else 0,
            "disc_disagreement": disc_disagreement,
            "expert_dec": expert_dec,
            "expert_open": disc_disagreement - expert_dec,
        }


class ProjectAnnotatorDetailView(AnyRoleRequiredMixin, _ProjectPageMixin, DetailView):
    """The batches the user works on, in whatever role they have per batch."""

    template_name = "projects/project_detail_annotator.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batches = self.object.batches.filter(
            id__in=self.batch_roles,
            current_phase__in=[BatchPhase.ANNOTATION, BatchPhase.DISCUSSION, BatchPhase.EXPERT],
        ).order_by("-batch_number")
        finalized = set(
            BatchUser.objects.filter(
                batch__in=batches,
                user=self.request.user,
                finalized_at__isnull=False,
            ).values_list("batch_id", flat=True),
        )
        context["batches"] = [
            {
                "batch": batch,
                "role": self.batch_roles[batch.id],
                "done": batch.assignments.filter(
                    user=self.request.user, phase=BatchPhase.ANNOTATION
                )
                .done()
                .count(),
                "length": batch.examples.count(),
                "finalized": batch.id in finalized,
            }
            for batch in batches
        ]
        return context


def _samples_table(batch) -> dict:
    """The examples of a batch as table rows: metadata spread over one column per key, and
    one column per person with their labels (None = not labeled yet, [] = no label).
    Annotators always get a column, experts once they have decided something."""
    examples = list(batch.examples.all())
    columns = list(dict.fromkeys(key for example in examples for key in example.metadata))

    people = {
        (BatchPhase.ANNOTATION, user.id): {"name": user.username, "role": "Annotator"}
        for user in batch.assignees(role=ProjectRole.ANNOTATOR).order_by("username")
    }
    labels = {}  # (example id, phase, user id) -> labels
    done = (
        batch.assignments.filter(
            done__isnull=False,
            phase__in=[BatchPhase.ANNOTATION, BatchPhase.EXPERT],
        )
        .select_related("user")
        .prefetch_related("annotations__label")
        .order_by("user__username")
    )
    for assignment in done:
        key = (assignment.phase, assignment.user_id)
        people.setdefault(key, {"name": assignment.user.username, "role": "Expert"})
        found = sorted((a.label for a in assignment.annotations.all()), key=lambda lb: lb.name)
        labels[(assignment.example_id, *key)] = found

    annotators = [key for key in people if key[0] == BatchPhase.ANNOTATION]

    def disagree(example) -> bool:
        """Every annotator has labeled the example, and not all chose the same labels."""
        chosen = [labels.get((example.id, *key)) for key in annotators]
        if len(chosen) < 2 or None in chosen:
            return False
        return len({frozenset(label.id for label in found) for found in chosen}) > 1

    return {
        "batch": batch,
        "examples": examples,
        "metadata_columns": columns,
        "people": list(people.values()),
        "rows": [
            {
                "example": example,
                "values": [example.metadata.get(c) for c in columns],
                "labels": [labels.get((example.id, *key)) for key in people],
                "disagreement": disagree(example),
            }
            for example in examples
        ],
    }


class BatchSamplesView(ExpertRequiredMixin, DetailView):
    """All examples of a batch as a table; while it can still change, experts drag rows
    into the order in which annotators get them."""

    model = Batch
    pk_url_kwarg = "batch_id"
    template_name = "projects/batch_samples.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **_samples_table(self.object)}


class SampleDetailView(ExpertRequiredMixin, View):
    """One example with everything that happened to it: metadata, labels per phase, the chat
    and the expert decision. Previous/next follow the batch order."""

    def get(self, request, batch_id, example_id):
        batch = get_object_or_404(Batch.objects.select_related("project"), id=batch_id)
        examples = list(batch.examples.all())
        example = get_object_or_404(Example, id=example_id, batch=batch)
        index = examples.index(example)
        context = {
            "batch": batch,
            "example": example,
            "number": index + 1,
            "previous": examples[index - 1] if index > 0 else None,
            "next": examples[index + 1] if index + 1 < len(examples) else None,
            "before": example.labels_by_user(BatchPhase.ANNOTATION),
            "after": example.labels_by_user(BatchPhase.DISCUSSION),
            "decision": example.labels_by_user(BatchPhase.EXPERT),
            "chat": Message.objects.filter(example=example)
            .exclude(user="system")
            .order_by("created_at"),
        }
        return render(request, "projects/sample_detail.html", context)


class BatchOrderView(ExpertRequiredMixin, View):
    def post(self, request, batch_id):
        batch = get_object_or_404(Batch, id=batch_id)
        if not batch.can_reorder:
            return HttpResponse("The order is fixed once the discussion has started.", status=409)
        try:
            batch.set_example_order([int(i) for i in request.POST.getlist("example")])
        except ValueError as exc:
            return HttpResponseBadRequest(str(exc))
        messages.success(request, "Order saved.")
        return render(request, "projects/partials/samples_rows.html", _samples_table(batch))


class ChangeBatchPhase(ExpertRequiredMixin, View):
    def post(self, request, batch_id, *args, **kwargs):  # noqa: ARG002
        batch = get_object_or_404(Batch, id=batch_id)
        form = BatchPhaseForm(request.POST, instance=batch)
        if form.is_valid():
            new = form.save(commit=False)
            batch.set_phase(new.current_phase, actor=request.user)
            phase = batch.get_current_phase_display()
            messages.success(request, f"Phase updated to {phase}.")
            response = HttpResponse(status=204)
            response["HX-Refresh"] = "true"
            return response
        else:
            msg = "invalid form"
            raise Exception(msg)


class DeleteBatch(ExpertRequiredMixin, View):
    def post(self, request, batch_id, *args, **kwargs):  # noqa: ARG002
        batch = get_object_or_404(Batch, id=batch_id)
        batch_number = batch.batch_number
        codebook = batch.project.codebook.first()
        if codebook is not None:
            codebook.untag_version(batch_number)
        batch.delete()
        messages.success(request, f"Batch {batch_number} deleted.")
        return redirect("project-detail", project_id=batch.project_id)


_LABEL_KEYS = {
    BatchPhase.ANNOTATION: "labels_annotation",
    BatchPhase.DISCUSSION: "labels_discussion",
    BatchPhase.EXPERT: "labels_expert",
}


def _timestamp(value) -> str:
    return timezone.localtime(value).isoformat(timespec="milliseconds")


def _generate_batch_data(batch):
    """One export row per example of the batch: text, metadata, labels per phase and chat.
    Examples that nobody has labeled yet are included with empty label lists."""
    shared_data = {
        "batch_number": batch.batch_number,
        "batch_annotators": [
            u.username for u in batch.assignees(role=ProjectRole.ANNOTATOR).order_by("username")
        ],
        "batch_experts": [
            u.username for u in batch.assignees(role=ProjectRole.EXPERT).order_by("username")
        ],
    }

    rows = {
        example.id: {
            "text_id": example.id,
            "text": example.content,
            "metadata": example.metadata,
            "labels_annotation": [],
            "labels_discussion": [],
            "messages_discussion": [],
            "labels_expert": [],
            **shared_data,
        }
        for example in batch.examples.order_by("pk")
    }

    assignments = (
        batch.assignments.filter(done__isnull=False, phase__in=_LABEL_KEYS)
        .select_related("user")
        .prefetch_related("annotations__label")
        .order_by("example_id", "user__username")
    )
    for assignment in assignments:
        rows[assignment.example_id][_LABEL_KEYS[assignment.phase]].append(
            {
                "user": assignment.user.username,
                "labels": sorted(a.label.name for a in assignment.annotations.all()),
                "at": _timestamp(assignment.done),
            },
        )

    messages = Message.objects.filter(example__in=rows).order_by("created_at")
    for message in messages:
        rows[message.example_id]["messages_discussion"].append(
            {
                "user": message.user,
                "at": _timestamp(message.created_at),
                "content": message.message,
            },
        )

    return pd.DataFrame(rows.values())


class ExportProject(ExpertRequiredMixin, View):
    def get(self, request, project_id, *args, **kwargs):  # noqa: ARG002
        project = Project.objects.get(id=project_id)
        frames = [_generate_batch_data(b) for b in project.batches.order_by("batch_number")]
        json_data = pd.concat(frames).to_json(orient="records", lines=True) if frames else ""

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
        project_id = request.GET.get("project_id")

        users = User.objects.all()
        if project_id:
            users = users.filter(projectuser__project_id=project_id)
        if query:
            users = users.filter(username__icontains=query)
        users = users.order_by("username")[:5]
        return render(
            request,
            "projects/partials/user_search_results.html",
            {"users": users},
        )
