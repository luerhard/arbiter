import json
import logging
import shutil

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponseBadRequest
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.template.defaultfilters import pluralize
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


def _posted_users_json(post, field) -> str:
    """The users picked in a user search of a form that is shown again after an error."""
    ids = [value for value in post.getlist(field) if value.isdigit()]
    return _users_json(User.objects.filter(id__in=ids).order_by("username"))


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
            msg = "Only the owner can delete this project."
            raise PermissionDenied(msg)

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

    def get_context_data(self, **kwargs):
        # After an error the form is shown again with everything as entered: the label rows
        # and the picked users are not Django form fields, so they need their own context.
        context = super().get_context_data(**kwargs)
        post = self.request.POST
        rows = zip(
            post.getlist("label_name"),
            post.getlist("label_color"),
            post.getlist("label_hotkey"),
            strict=False,
        )
        context["label_rows"] = [
            {"name": name, "color": color, "hotkey": hotkey}
            for name, color, hotkey in rows
            if (name + color + hotkey).strip()
        ] or [{}]
        context["annotators_selected_users"] = _posted_users_json(post, "annotators")
        context["experts_selected_users"] = _posted_users_json(post, "experts")
        return context

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
        Label.objects.bulk_create(Label(project=self.project, **label) for label in form.labels)
        return super().form_valid(form)


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
        post = self.request.POST
        if self.request.method == "POST":  # shown again after an error: keep the choice
            context["annotators_selected_users"] = _posted_users_json(post, "annotators")
            context["experts_selected_users"] = _posted_users_json(post, "experts")
        else:
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


def _open_work(batch) -> str:
    """What is still open in the batch's current phase, for the confirmation before an
    expert moves it on by hand; empty when the phase is complete."""
    phase = batch.current_phase
    if phase == BatchPhase.ANNOTATION:
        open_per_user = (
            batch.assignments.filter(phase=phase, done__isnull=True)
            .values_list("user__username")
            .annotate(n=Count("id"))
            .order_by("user__username")
        )
        if not open_per_user:
            return ""
        who = ", ".join(
            f"{name} has {n} unlabeled sample{pluralize(n)}" for name, n in open_per_user
        )
        return f"{who}. Samples that not every annotator labeled count as disagreements."
    if phase == BatchPhase.DISCUSSION:
        open_count = batch.open_discussion_examples().count()
        if not open_count:
            return ""
        total = batch.discussion_examples().count()
        return (
            f"{open_count} of {total} disagreements {pluralize(open_count, 'is,are')} not "
            "discussed yet. They stay disagreements."
        )
    if phase == BatchPhase.EXPERT:
        open_count = (
            batch.assignments.filter(phase=phase, done__isnull=True)
            .values("example")
            .distinct()
            .count()
        )
        if open_count:
            are = pluralize(open_count, "is,are")
            return f"{open_count} expert decision{pluralize(open_count)} {are} still open."
    return ""


def _phase_menu(batch, open_work: str) -> list[dict]:
    """The phase menu of a batch card. Moving on to a later phase while the current one is
    unfinished asks for confirmation first (confirm=True: the menu item opens a dialog)."""
    phases = list(BatchPhase)
    current = phases.index(batch.current_phase)
    return [
        {
            "phase": phase,
            "label": phase.label,
            "current": index == current,
            "confirm": bool(open_work) and index > current,
        }
        for index, phase in enumerate(phases)
    ]


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
        # once the discussion started, its examples are fixed; before, count live
        discussion_examples = batch.discussion_examples()
        if not discussion_examples.exists():
            discussion_examples = batch.disagreements(BatchPhase.ANNOTATION)
        discussion_disagreements = batch.disagreements(BatchPhase.DISCUSSION)
        length = batch.examples.count()

        users = []
        for annotator in batch.assignees(role=ProjectRole.ANNOTATOR).order_by("username"):
            done = batch.assignments.filter(user=annotator).done()
            users.append(
                {
                    "user": annotator,
                    "annotated": done.filter(phase=BatchPhase.ANNOTATION).count(),
                    "discussed": done.filter(phase=BatchPhase.DISCUSSION).count(),
                },
            )

        disc_disagreement = discussion_disagreements.count()
        expert_dec = discussion_disagreements.filter(
            assignments__phase=BatchPhase.EXPERT,
            assignments__done__isnull=False,
        ).count()
        open_work = _open_work(batch)
        return {
            "batch": batch,
            "phase_menu": _phase_menu(batch, open_work),
            "open_work": open_work,
            "is_batch_expert": self.batch_roles.get(batch.id) == ProjectRole.EXPERT,
            "steps": _phase_steps(batch),
            "length": length,
            "users": users,
            "annotated_total": sum(u["annotated"] for u in users),
            "annotated_max": length * len(users),
            "disagreement": discussion_examples.count(),
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
        # finished batches stay listed, without actions
        context["finished"] = [
            {"batch": batch, "length": batch.examples.count()}
            for batch in self.object.batches.filter(
                id__in=self.batch_roles,
                current_phase=BatchPhase.FINAL,
            ).order_by("-batch_number")
        ]
        return context


def _sample_state(by_phase: dict, n_annotators: int) -> tuple[str, list | None]:
    """How far one sample got, and its label so far: (status, labels), labels None while
    open, [] for no label. by_phase: phase -> {username: sorted labels, None if not done}.
    The furthest phase counts: expert decision, discussion, annotation."""

    def same(found):
        return len({frozenset(label.id for label in labels) for labels in found}) == 1

    expert = by_phase.get(BatchPhase.EXPERT, {})
    decided = [labels for labels in expert.values() if labels is not None]
    if decided:
        return ("Expert decided", decided[0]) if same(decided) else ("Experts disagree", None)
    if expert:
        return "Waiting for expert", None

    discussion = by_phase.get(BatchPhase.DISCUSSION, {})
    if discussion:
        if None in discussion.values():
            return "In discussion", None
        found = list(discussion.values())
        if same(found):
            return "Agreed in discussion", found[0]
        return "Disagree after discussion", None

    labeled = [
        labels for labels in by_phase.get(BatchPhase.ANNOTATION, {}).values() if labels is not None
    ]
    if len(labeled) < n_annotators or not labeled:
        return f"Labeled {len(labeled)} of {n_annotators}", None
    if same(labeled):
        return "Agreed", labeled[0]
    return "To be discussed", None


def _sample_states(batch, examples) -> dict[int, dict]:
    """_sample_state for every example of a batch, with whether its annotators disagree."""
    by_example = {example.id: {} for example in examples}
    assignments = (
        batch.assignments.filter(
            phase__in=[BatchPhase.ANNOTATION, BatchPhase.DISCUSSION, BatchPhase.EXPERT],
        )
        .select_related("user")
        .prefetch_related("annotations__label")
    )
    for assignment in assignments:
        labels = sorted((a.label for a in assignment.annotations.all()), key=lambda lb: lb.name)
        phases = by_example.setdefault(assignment.example_id, {})
        phases.setdefault(assignment.phase, {})[assignment.user.username] = (
            labels if assignment.done else None
        )
    n_annotators = batch.assignees(role=ProjectRole.ANNOTATOR).count()
    states = {}
    for example_id, phases in by_example.items():
        status, labels = _sample_state(phases, n_annotators)
        annotated = list(phases.get(BatchPhase.ANNOTATION, {}).values())
        disagreement = (
            len(annotated) >= 2  # noqa: PLR2004
            and None not in annotated
            and len({frozenset(label.id for label in found) for found in annotated}) > 1
        )
        states[example_id] = {"status": status, "labels": labels, "disagreement": disagreement}
    return states


def _samples_table(batch) -> dict:
    """The examples of a batch as table rows: how far each got and its label so far, then
    its metadata, one column per key. Who chose what is on the sample's own page, so the
    table is as wide for two annotators as for six."""
    examples = list(batch.examples.all())
    columns = list(dict.fromkeys(key for example in examples for key in example.metadata))
    states = _sample_states(batch, examples)
    return {
        "batch": batch,
        "examples": examples,
        "metadata_columns": columns,
        "rows": [
            {
                "example": example,
                "values": [example.metadata.get(c) for c in columns],
                **states[example.id],
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
        codebook = batch.project.codebook.get()
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
            "state": _sample_states(batch, [example])[example.id],
            "codebook": codebook,
            "changes": codebook.changes_for(example),
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
            if not request.htmx:  # the confirmation dialog posts a plain form
                return redirect("project-detail", project_id=batch.project_id)
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
