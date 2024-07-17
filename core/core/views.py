from typing import Any

from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.views.generic import DetailView
from django.views.generic import ListView

from .models import Project
from .models import ProjectUser


User = get_user_model()


def core(request):
    return render(request, "base.html")


class ProjectListView(ListView):
    model = Project
    context_object_name = "projects"
    template_name = "core/project_list.html"

    def get_queryset(self):

        # for simplicity now: show admin all projects
        if "Admin" in (group.name for group in self.request.user.groups.all()):
            return self.model.objects.all()
        else:
            return self.model.objects.filter(users=self.request.user)


class ProjectDetailView(DetailView):
    model = Project
    context_object_name = "project"
    template_name = "core/project_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # can probably be a single db query
        context["annotators"] = User.objects.filter(
            projectuser__project=context["project"], projectuser__role=ProjectUser.Role.ANNOTATOR,
        )
        context["experts"] = User.objects.filter(
            projectuser__project=context["project"], projectuser__role=ProjectUser.Role.EXPERT,
        )


        context["batches"] = [1,2,3]
        return context


# @login_required
# def dashboard(request):
#     assignments = ProjectAssignment.objects.filter(user=request.user)
#     projects_with_sentences = []

#     all_assignments = []

#     for assignment in assignments:
#         project = assignment.project
#         batch_numbers = [batch.batch_number for batch in project.batches.all()]
#         all_assignments.append((project.name, project.pk, batch_numbers))

#         # first_sentence = Sentence.objects.filter(project=project).first()
#         # projects_with_sentences.append({
#         #     "project": project,
#         #     "first_sentence_id": first_sentence.id if first_sentence else None,
#         # })

#     context = {
#         "assignments": all_assignments,
#     }

#     return render(request, "core/dashboard.html", context)


def colors():
    return ["#AF7AC5", "#E74C3C", "#27AE60", "#5DADE2", "#F7DC6F"]
