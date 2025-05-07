# Create your views here.

from codebook.models import Codebook
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.generic.detail import DetailView

from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example


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

        previous_example = all_examples.filter(id__lt=current_example.id).order_by("-id").first()
        next_example = all_examples.filter(id__gt=current_example.id).order_by("id").first()

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
        messages = (
            Message.objects.filter(example=current_example)
            .exclude(user="system")
            .order_by("created_at")
        )

        context["prev_labels"] = annotations_before_discussion
        context["post_labels"] = annotations_after_discussion
        context["chat_messages"] = messages
        context["labels"] = self.object.project.labels.all()

        return context


def resolve_Disagreements(request, task_id=0):
    tasks = [
        {
            "codebook": "##Admiration: \n Finding something impressive or worthy of respect.\n  \n##Pride: A feeling of pleasure or satisfaction inspired by something or someone deemed impressive or worthy of respect.",
            "labels": [
                {"label": "Admiration", "user": "annoator1"},
                {"label": "Pride", "user": "annoator2"},],
            "chat_messages": [
                {"user": "annotator1", "message": "I think this is a good example of admiration."},
                {"user": "annotator2", "message": "I think it is more about pride."},
            ],
            "sentence": "Watching my daughter graduate at the top of her class filled me with an incredible sense of joy and accomplishment.",
        },
        {
            "codebook": "##Sadness: \n Emotional pain, sorrow.\n  \n##Grief: Intense sorrow.",
            "labels": [
                {"label": "Sadness", "user": "annoator1"},
                {"label": "Grief", "user": "annoator2"},
            ],
            "chat_messages": [
                {"user": "annotator1", "message": "This is a clear example of sadness."},
                {"user": "annotator2", "message": "I see it as grief."},
                {"user": "annotator1", "message": "I think the context suggests a deeper emotional pain."},
                {"user": "annotator2", "message": "True, but grief is a more specific term."},
            ],
        },
        {
    "codebook": "##Sadness: \n Emotional pain, sorrow.\n\n##Disappointment: \n Sadness or displeasure.",
    "labels": [
        {"label": "Sadness", "user": "annotator1"},
        {"label": "Disappointment", "user": "annotator2"}
    ],
    "chat_messages": [
        {"user": "annotator1", "message": "I think this is a good example of sadness."},
        {"user": "annotator2", "message": "I think it is more about disappointment."}
    ],
    "sentence": "When the promotion didn’t come through, she felt a deep ache that lingered for days."
},{
    "codebook": "##Curiosity: \n A strong longing to gain knowledge or uncover information about something.\n\n##Desire: A strong longing to obtain or experience something personally meaningful or fulfilling.",
    "labels": [
        {"label": "Curiosity", "user": "annotator1"},
        {"label": "Desire", "user": "annotator2"}
    ],
    "chat_messages": [
        {"user": "annotator1", "message": "I think this is a good example of curiosity."},
        {"user": "annotator2", "message": "I think it is more about desire."},
    ],
    "sentence": "She couldn’t stop thinking about what might be inside the mysterious, locked box."
},
{
    "codebook": "##Annoyance: \n A mild feeling of irritation or displeasure caused by trivial or repetitive disturbances.\n\n##Disgust: A strong feeling of revulsion or disapproval triggered by something deeply unpleasant or offensive.\n\n##Anger: TBD.",
    "labels": [
        {"label": "Annoyance", "user": "annotator1"},
        {"label": "Disgust", "user": "annotator2"}
    ],
    "chat_messages": [
        {"user": "annotator1", "message": "I think this is a mild case of annoyance."},
        {"user": "annotator2", "message": "It seems more like disgust to me."}
    ],
    "sentence": "How dare they cut me off like that! I can't stand people who drive recklessly!"
}

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
