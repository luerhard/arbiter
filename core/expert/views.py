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
from django.http import Http404

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





def resolve_Disagreements(request, task_id=0):
    tasks = [
        {
            "codebook": "##Admiration: \n Finding something impressive or worthy of respect.\n  \n##Pride: A feeling of pleasure or satisfaction inspired by something or someone deemed impressive or worthy of respect.",
            "labels": ["Admiration", "Pride"],
            "chat_messages": [
                {"user": "annotator1", "message": "I think blabla"},
                {"user": "annotator2", "message": "I think XOXOXO"},
                {"user": "annotator1", "message": "sounds good"},
            ],
            "sentence":"Sentece des problems"
        },
        {
            "codebook": "##Joy: \n A feeling of great pleasure and happiness.\n  \n##Excitement: A feeling of enthusiasm and eagerness.",
            "labels": [{"label":"Joy", "user":"annoator1"}, {"label":"Excitement","user":"annoator2"},],
            "chat_messages": [
                {"user": "annotator1", "message": "This is amazing!"},
                {"user": "annotator2", "message": "I agree, it's exciting!"},
            ],
        },
    ]
    if task_id < 0 or task_id >= len(tasks):
        raise Http404("Task not found")
    previous_task_id = task_id - 1 if task_id > 0 else None
    next_task_id = task_id + 1 if task_id < len(tasks) - 1 else None

    context = {
        "task": tasks[task_id],
        "previous_task_id": previous_task_id,
        "next_task_id": next_task_id,
    }
    return render(request, "expert/dialogue_UI-Test.html", context)