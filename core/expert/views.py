# Create your views here.

from django.shortcuts import render
from django.shortcuts import get_object_or_404
from core.mixins import ExpertRequiredMixin
from projects.models import Project, Batch
from codebook.models import Codebook
from projects.models import ProjectUser
from django.views.generic.detail import DetailView
from discuss.models import Message
from data.models import Annotation 
from data.models import Example

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
        codebook = self.object
        context["complete_codebook"] = codebook.content
        context["Definition_AE"] = codebook.get_definition_section("Anti-Elitism")
        context["Example_AE"] = codebook.get_example_section("Anti-Elitism")
        context["Definition_PC"] = codebook.get_definition_section("People-Centrism")
        context["Example_PC"] = codebook.get_example_section("People-Centrism")
        context["ease_scale"] = range(1, 8)
        current_example_id = self.kwargs.get("example_id")
        if current_example_id:
            current_example = get_object_or_404(Example, pk=current_example_id)
        else:
            current_example = Example.objects.filter(has_disagreement=True).first()

      
        all_examples = Example.objects.filter(has_disagreement=True).order_by("id")

        previous_example = (
            all_examples.filter(id__lt=current_example.id).order_by("-id").first()
        )
        next_example = (
            all_examples.filter(id__gt=current_example.id).order_by("id").first()
        )

        context["sentence"] = current_example
        context["previous_example"] = previous_example
        context["next_example"] = next_example
        context["all_examples"] = all_examples

        annotations_before_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            phase=Annotation.Phase.ANNOTATION,
        )
        annotations_after_discussion = Annotation.objects.filter(
            assignment__example=current_example,
            phase=Annotation.Phase.DISCUSSION,
        )
        messages = Message.objects.filter(
            example=current_example
        ).exclude(user="system").order_by("created_at")

        context["prev_labels"] = annotations_before_discussion
        context["post_labels"] = annotations_after_discussion
        context["chat_messages"] = messages
        context["labels"] = self.object.project.labels.all()

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