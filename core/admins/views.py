from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import HttpResponse
from django.views.generic import DetailView
from django.views.generic import ListView

from annotation.models import Batch
from annotation.models import Sentence
from core.models import Project
from core.models import ProjectUser

User = get_user_model()


class ProjectListView(ListView):
    model = Project
    context_object_name = "projects"
    template_name = "admin_panel/manage_projects.html"

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
                "length": batch.sentences.count(),
                "is_discussed": batch.sentences.filter(is_discussed=True).count(),
            }

            for user in context["annotators"]:
                already_annotated = (
                    Sentence.objects.filter(
                        batch=batch,
                        user_annotations__user=user,
                    )
                    .values("id")
                    .annotate(label_count=Count("user_annotations"))
                    .filter(label_count__gt=0)
                    .count()
                )
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
        for sentence in batch.sentences.all():
            sentence.has_disagreement_labels = None
            sentence.save()
    else:
        sentences = (
            batch.sentences.prefetch_related("user_annotations")
            .prefetch_related("user_annotations__user")
            .all()
        )

        for sentence in sentences:
            user_annotations = sentence.user_annotations.all()
            annotation_groups = {user: set() for user in {anno.user for anno in user_annotations}}
            for user_annotation in user_annotations:
                if user_annotation.is_set:
                    annotation_groups[user_annotation.user].add(user_annotation.label_id)
            annotations = list(annotation_groups.values())
            if not all(annotation == annotations[0] for annotation in annotations):
                sentence.has_disagreement_labels = True
            else:
                sentence.has_disagreement_labels = False
            sentence.save()
        batch.annotation_done = True

    batch.save()

    response = f'<div class="fadeout-2" id="output{batch_id}"><i class="bi bi-check"></i></div>'
    return HttpResponse(response)
