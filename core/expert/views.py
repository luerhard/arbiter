# Create your views here.

from django.http import Http404
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from core.mixins import ExpertRequiredMixin
from projects.models import Project
from data.models import Example
from codebook.forms import CodebookForm
from codebook.models import Codebook
from projects.models import ProjectUser
from django.views.generic.detail import DetailView
from data.models import ExampleAssignment
from discuss.models import Message, Room
from data.models import Annotation

def overview(request):
    projects_with_disagreements = Project.objects.filter(
        batches__examples__has_disagreement=True
    ).distinct()

    context = {
        "projects": "projects_with_disagreements",
    }
    return render(request,"expert/display_disagreemets_overview.html", context)

class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "expert/dialogue.html"
   
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        user = self.request.user
        project_user = get_object_or_404(ProjectUser, user=user, project=self.object.project)
        context["role"] = project_user.role

        batch_id = self.kwargs.get("batch_id")  # Ensure batch_id is passed in the URL
        room = get_object_or_404(Room, pk=batch_id)
        messages = Message.objects.filter(room=room).order_by("created_at")
        context["chat_messages"] = messages

        annotations_before_discussion = Annotation.objects.filter(
            assignment__example__batch_id=batch_id,
            phase=Annotation.Phase.ANNOTATION,
        )
        annotations_after_discussion = Annotation.objects.filter(
            assignment__example__batch_id=batch_id,
            phase=Annotation.Phase.DISCUSSION,
        )
        context["prev_labels"] = annotations_before_discussion
        context["post_labels"] = annotations_after_discussion

        return context



def resolve_Disagreements(request):
    disagreements = [
        {
            "id": 1,
            "sentence": "I feel like something bad is going to happen.",
            "labels": ["fear", "anger"],
            "participants": ["Annotator1", "Annotator2"],
        },
    ]
    codebook = [
    
    { "name":"fear",
    "definition":"Fear represents an emotional state caused by the anticipation or awareness of danger.", 
    "examples": [
            "I heard footsteps behind me in the dark alley.",
            "The doctor told me I might need surgery.",
        ],
    },
    
    {
    "name": "anger",
    "definition": "Anger represents an intense emotional response to a perceived provocation or injustice.",
    "examples": [
            "Why did you take my book without asking?",
            "The unfair decision made me want to scream.",
        ],
    }
    ]

    context = {
        "disagreements": disagreements,
        "codebook": codebook,
    }
    return render(request, "expert/dialogue.html", context)



# def resolve_Disagreements(request, project_id, version_name=None):
#     # Fetch the project
#     project = get_object_or_404(Project, id=project_id)

#     # Fetch the codebook version
#     if version_name:
#         codebookv = (
#             get_object_or_404(
#                 CodebookVersion,
#                 codebook__project=project,
#                 version_name=version_name,
#             )
#             .prefetch_related("definitions", "definitions_examples")
#             .prefetch_related("descriptions")
#         )
#     else:
#         try:
#             codebookv = (
#                 CodebookVersion.objects.filter(codebook__project=project)
#                 .order_by("date")
#                 .prefetch_related("definitions__examples")
#                 .prefetch_related("descriptions")[0]
#             )
#         except IndexError:
#             raise Http404("No codebooks exist.")

#     # Mock disagreements data
#     disagreements = [
#         {
#             "id": 1,
#             "sentence": "I feel like something bad is going to happen.",
#             "labels": ["fear", "anger"],
#             "participants": ["Annotator1", "Annotator2"],
#         },
#     ]

#     context = {
#         "disagreements": disagreements,
#         "codebook": codebookv.codebook,
#         "codebookv": codebookv,
#     }
#     return render(request, "expert/resolve_Disagreements.html", context)





