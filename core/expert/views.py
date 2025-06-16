# Create your views here.

from codebook.models import Codebook
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic.detail import DetailView
from django.views.generic import View
from core.mixins import ExpertRequiredMixin
from data.models import Annotation
from data.models import Example
from discuss.models import Message
from data.models import Example, ExampleAssignment
from django.http import HttpResponseBadRequest
from django.db import models
import json
from django.http import JsonResponse
from django.urls import reverse

def save_resolution_labels(request, codebook_id, batch_id, example_id):
    if request.method == "POST":
        user = request.user
        example = get_object_or_404(Example, pk=example_id, batch=batch_id)
        assignment = ExampleAssignment.objects.filter(example=example, user=user).first()
        if not assignment:
            max_order = ExampleAssignment.objects.filter(
                user=user,
                example__batch=example.batch
            ).aggregate(models.Max("order"))["order__max"] or 0
            assignment = ExampleAssignment.objects.create(
                example=example,
                user=user,
                order=max_order + 1
            )
        label_ids = [int(i) for i in request.POST.getlist("selected_labels") if i.strip()]
        assignment.set_user_annotations(label_ids=label_ids, phase="EXPERT")

        all_examples = Example.objects.filter(has_disagreement=True).order_by("id")
        next_example = all_examples.filter(id__gt=example.id).order_by("id").first()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'next_url': reverse('expert-dialogue', args=[codebook_id, batch_id, next_example.id])
            })
        else:
            return redirect('expert-dialogue', codebook_id, batch_id, next_example.id)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False}, status=400)
    else:
        return redirect('expert-dialogue', codebook_id, batch_id, example_id)

class CodebookPartialView(View):
    def get(self, request, pk):
        codebook = get_object_or_404(Codebook, pk=pk)
        return render(request, "expert/partials/codebook_rendered.html", {"codebook": codebook})

class CodebookUpdateView(View):
    def post(self, request, pk):
        codebook = get_object_or_404(Codebook, pk=pk)
        content = request.POST.get("content", "")
        rationale = request.POST.get("definition_correction", "")
        sentence = request.POST.get("sentence", "")
        example_id = request.POST.get("example_id", "")
        batch_id = request.POST.get("batch_id", "")
        current_example = get_object_or_404(Example, pk=example_id, batch =batch_id)
        
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
        chat_history_list = [f"{msg.user}: {msg.message}" for msg in messages]
        chat_history_str = "\n".join(chat_history_list)  

        labels_before_str = ""
        for ann in annotations_before_discussion:
            labels_before_str += f"{ann.label} (assigned by: {ann.assignment.user})\n"

        labels_after_list = [f"{ann.label} (assigned by: {ann.assignment.user})" for ann in annotations_after_discussion]
        labels_after_str = "\n".join(labels_after_list)
        commit_info = {
    "rationale": rationale,
    "sentence": sentence,
    "labels_before": labels_before_str,
    "labels_after": labels_after_str,
    "chat_history": chat_history_str,
}
        commit_message = json.dumps(commit_info, ensure_ascii=False)
        if content:
           codebook.save(content=content, commit_message=commit_message)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return render(request, "expert/partials/codebook_rendered.html", {"codebook": codebook})

class ExpertDialogue(ExpertRequiredMixin, DetailView):
    pk_url_kwarg = "codebook_id"
    model = Codebook
    context_object_name = "codebook"
    template_name = "expert/dialogue_UI-Test.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        user = self.request.user
        # project_user = get_object_or_404(ProjectUser, user=user, project=self.object.project)
        # context["role"] = project_user.role
        codebook = self.object
        project = codebook.project
        context["codebook"] = codebook
        batch_id =self.kwargs.get("batch_id")
        context["batch_id"]= batch_id
       
        current_example_id = self.kwargs.get("example_id")
        if current_example_id:
            current_example = get_object_or_404(Example, pk=current_example_id, batch =batch_id)
        else:
            current_example = Example.objects.filter(has_disagreement=True).first()

        all_examples = Example.objects.filter(has_disagreement=True).order_by("id")
        
        previous_example = all_examples.filter(id__lt=current_example.id).order_by("-id").first()
        next_example = all_examples.filter(id__gt=current_example.id).order_by("id").first()
        context["example_id"] = current_example_id
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
        examples_with_disagreement = Example.objects.filter(batch_id=batch_id, has_disagreement=True, ).count
        examples_with_expert_decision = Example.objects.filter(batch_id=batch_id, has_disagreement=True).count
        context["disagreements_remaining"] = 3
        context["prev_labels"] = annotations_before_discussion
        context["post_labels"] = annotations_after_discussion
        context["chat_messages"] = messages
        context["labels"] = self.object.project.labels.all()

        return context


# def resolve_Disagreements(request, task_id=0):
class Usability_test(DetailView):
    tasks = [
            {
                "codebook": "##Admiration: \n Finding something impressive or worthy of respect.\n  \n##Pride: A feeling of pleasure or satisfaction inspired by something or someone deemed impressive or worthy of respect.",
                "labels": [
                    {"label": "Admiration", "user": "annotator1"},
                    {"label": "Pride", "user": "annotator2"},
                ],
                "all_labels": [
                    {"label": "Admiration"},
                    {"label": "Pride"},
                ],
                "chat_messages": [
                    {"user": "annotator1", "message": "According to the codebook, admiration is about finding something impressive. I think this fits because the statement highlights an impressive achievement."},
                    {"user": "annotator2", "message": "But pride is also about satisfaction in something impressive, as per the codebook. The focus here seems to be on the personal satisfaction of the parent."},
                    {"user": "annotator1", "message": "True, but the emphasis on 'incredible sense of joy and accomplishment' leans more towards admiration for the daughter's achievement."},
                    {"user": "annotator2", "message": "I see your point, but the personal connection makes it feel more like pride. Admiration might be more detached."},
                ],
                "sentence": "Watching my daughter graduate at the top of her class filled me with an incredible sense of joy and accomplishment.",
            },
            {
               "codebook": "##Anger: \n A strong feeling of displeasure or hostility.\n\n##Curiosity: \n A strong longing to gain knowledge or uncover information about something.\n\n ##Desire: \n A strong longing to obtain or experience something personally meaningful or fulfilling.\n\n ##Disappointment: \n Sadness or displeasure.\n\n\
##Disapproval: \n Having or expressing an unfavorable opinion.\n\n\
##Disgust: \n Revulsion or strong disapproval aroused by something unpleasant or offensive.\n\n\
##Embarrassment: \n Self-consciousness, shame, or awkwardness.\n\n\
##Excitement: \n Feeling of great enthusiasm and eagerness.\n\n\
##Fear: \n Being afraid or worried.\n\n\
##Gratitude: \n A feeling of thankfulness and appreciation.\n\n\
##Grief: \n Intense sorrow.\n\n\
##Joy: \n A feeling of pleasure and happiness.\n\n\
##Love: \n A strong positive emotion of regard and affection.\n\n\
##Nervousness: \n Apprehension, worry, anxiety.\n\n\
##Optimism: \n Hopefulness and confidence about the future or the success of something.\n\n\
##Realization: \n Becoming aware of something.\n\n\
##Relief: \n Reassurance and relaxation following release from anxiety or distress.\n\n\
##Remorse: \n Regret or guilty feeling.\n\n\
##Sadness: \n Emotional pain, sorrow.",
        
                "labels": [
                    {"label": "Sadness", "user": "annotator1"},
                    {"label": "Grief", "user": "annotator2"},
                ],
                "all_labels": [
                    {"label": "Anger"},
                    {"label": "Curiosity"},
{"label": "Desire"},
{"label": "Disappointment"},
{"label": "Disapproval"},
{"label": "Disgust"},
{"label": "Embarrassment"},
{"label": "Excitement"},
{"label": "Fear"},
{"label": "Gratitude"},
{"label": "Grief"},
{"label": "Joy"},
{"label": "Love"},
{"label": "Nervousness"},
{"label": "Optimism"},
{"label": "Realization"},
{"label": "Relief"},
{"label": "Remorse"},
{"label": "Sadness"},
                ],
                "chat_messages": [
                    {"user": "annotator1", "message": "The codebook defines sadness as emotional pain, which seems to fit here. The statement doesn't explicitly suggest the intensity of grief."},
                    {"user": "annotator2", "message": "But grief is defined as intense sorrow. The lingering ache described here feels deeper than just sadness."},
                    {"user": "annotator1", "message": "I think the intensity is subjective. The phrase 'deep ache' could still fall under sadness without reaching the level of grief."},
                    {"user": "annotator2", "message": "Fair, but the context of disappointment and lingering pain suggests a more profound emotional impact, which aligns with grief."},
                ],
                "sentence": "After losing her beloved pet, she felt a heavy emptiness that lingered for weeks.",
            },
            {
        "codebook": "##Anger: \n A strong feeling of displeasure or hostility.\n\n##Curiosity: \n A strong longing to gain knowledge or uncover information about something.\n\n ##Desire: \n A strong longing to obtain or experience something personally meaningful or fulfilling.\n\n ##Disappointment: \n Sadness or displeasure.\n\n\
##Disapproval: \n Having or expressing an unfavorable opinion.\n\n\
##Disgust: \n Revulsion or strong disapproval aroused by something unpleasant or offensive.\n\n\
##Embarrassment: \n Self-consciousness, shame, or awkwardness.\n\n\
##Excitement: \n Feeling of great enthusiasm and eagerness.\n\n\
##Fear: \n Being afraid or worried.\n\n\
##Gratitude: \n A feeling of thankfulness and appreciation.\n\n\
##Joy: \n A feeling of pleasure and happiness.\n\n\
##Love: \n A strong positive emotion of regard and affection.\n\n\
##Nervousness: \n Apprehension, worry, anxiety.\n\n\
##Optimism: \n Hopefulness and confidence about the future or the success of something.\n\n\
##Realization: \n Becoming aware of something.\n\n\
##Relief: \n Reassurance and relaxation following release from anxiety or distress.\n\n\
##Remorse: \n Regret or guilty feeling.\n\n\
##Sadness: \n Emotional pain, sorrow.",
            
        "labels": [
            {"label": "Sadness", "user": "annotator1"},
            {"label": "Disappointment", "user": "annotator2"}
        ],
        "all_labels": [
                {"label": "Anger"},
                    {"label": "Curiosity"},
                    {"label": "Desire"},
                    {"label": "Disappointment"},
                    {"label": "Disapproval"},
                    {"label": "Disgust"},
                    {"label": "Embarrassment"},
                    {"label": "Excitement"},
                    {"label": "Fear"},
                    {"label": "Gratitude"},
                    {"label": "Grief"},
                    {"label": "Joy"},
                    {"label": "Love"},
                    {"label": "Nervousness"},
                    {"label": "Optimism"},
                    {"label": "Realization"},
                    {"label": "Relief"},
                    {"label": "Remorse"},
                    {"label": "Sadness"},
                ],
        "chat_messages": [
            {"user": "annotator1", "message": "The codebook defines sadness as emotional pain. The lingering ache described here feels like a general emotional pain rather than a specific reaction to unmet expectations."},
            {"user": "annotator2", "message": "But disappointment is explicitly tied to unmet expectations, as per the codebook. The statement mentions the promotion not coming through, which directly points to disappointment."},
            {"user": "annotator1", "message": "I see your point, but sadness can also encompass the emotional pain caused by unmet expectations. The 'deep ache' seems to describe a broader emotional state rather than just disappointment."},
            {"user": "annotator2", "message": "I disagree. The context of the promotion being the trigger makes it more specific to disappointment. Sadness feels too general for this scenario."},
            {"user": "annotator1", "message": "But the intensity of the emotional pain described here—'deep ache that lingered for days'—goes beyond the fleeting nature of disappointment. It aligns more with sadness as a prolonged emotional state."},
            {"user": "annotator2", "message": "I think the lingering aspect could still fit disappointment, especially when the unmet expectation is significant. The emotional pain described here seems tied to the specific event of the promotion being denied."},
            {"user": "annotator1", "message": "Fair point, but I still feel the emotional depth described here leans more towards sadness. Disappointment might be a part of it, but sadness captures the overall feeling better."}
        ],
        "sentence": "When the promotion didn’t come through, she felt a deep ache that lingered for days."
        },
            {
                "codebook": "##Anger: \n A strong feeling of displeasure or hostility.\n\n##Curiosity: \n A strong longing to gain knowledge or uncover information about something.\n\n\
##Desire: \n A strong longing to obtain or experience something personally meaningful or fulfilling.\n\n ##Disappointment: \n Sadness or displeasure.\n\n\
##Disapproval: \n Having or expressing an unfavorable opinion.\n\n\
##Disgust: \n Revulsion or strong disapproval aroused by something unpleasant or offensive.\n\n\
##Embarrassment: \n Self-consciousness, shame, or awkwardness.\n\n\
##Excitement: \n Feeling of great enthusiasm and eagerness.\n\n\
##Fear: \n Being afraid or worried.\n\n\
##Gratitude: \n A feeling of thankfulness and appreciation.\n\n\
##Joy: \n A feeling of pleasure and happiness.\n\n\
##Love: \n A strong positive emotion of regard and affection.\n\n\
##Nervousness: \n Apprehension, worry, anxiety.\n\n\
##Optimism: \n Hopefulness and confidence about the future or the success of something.\n\n\
##Realization: \n Becoming aware of something.\n\n\
##Relief: \n Reassurance and relaxation following release from anxiety or distress.\n\n\
##Remorse: \n Regret or guilty feeling. \n\n\
##Sadness: \n Emotional pain, sorrow.",
        
                "labels": [
                    {"label": "Curiosity", "user": "annotator1"},
                    {"label": "Desire", "user": "annotator2"},
                ],
                "all_labels": [
                    {"label": "Anger"},
                    {"label": "Curiosity"},
{"label": "Desire"},
{"label": "Disappointment"},
{"label": "Disapproval"},
{"label": "Disgust"},
{"label": "Embarrassment"},
{"label": "Excitement"},
{"label": "Fear"},
{"label": "Gratitude"},
{"label": "Grief"},
{"label": "Joy"},
{"label": "Love"},
{"label": "Nervousness"},
{"label": "Optimism"},
{"label": "Realization"},
{"label": "Relief"},
{"label": "Remorse"},
{"label": "Sadness"},
                ],
                
                "chat_messages": [
                    {"user": "annotator1", "message": "The codebook describes curiosity as a longing to uncover information. The statement about the locked box fits this perfectly."},
                    {"user": "annotator2", "message": "But desire is about wanting to experience something personally meaningful. The focus on 'couldn’t stop thinking' suggests a deeper personal longing."},
                    {"user": "annotator1", "message": "I disagree. The locked box represents a mystery, which aligns more with curiosity. Desire would imply wanting to possess or experience the box itself."},
                    {"user": "annotator2", "message": "I see your point, but the intensity of the longing here feels more personal, which could lean towards desire."},
                ],
                "sentence": "She couldn’t stop thinking about what might be inside the mysterious, locked box.",
            },
            {
    "codebook": "##Anger: \n A strong feeling of displeasure or hostility.\n\n##Curiosity: \n A strong longing to gain knowledge or uncover information about something.\n\n\
##Desire: \n A strong longing to obtain or experience something personally meaningful or fulfilling.\n\n ##Disappointment: \n Sadness or displeasure.\n\n\
##Disapproval: \n Having or expressing an unfavorable opinion.\n\n\
##Disgust: \n Revulsion or strong disapproval aroused by something unpleasant or offensive.\n\n\
##Embarrassment: \n Self-consciousness, shame, or awkwardness.\n\n\
##Excitement: \n Feeling of great enthusiasm and eagerness.\n\n\
##Fear: \n Being afraid or worried.\n\n\
##Gratitude: \n A feeling of thankfulness and appreciation.\n\n\
##Joy: \n A feeling of pleasure and happiness.\n\n\
##Love: \n A strong positive emotion of regard and affection.\n\n\
##Nervousness: \n Apprehension, worry, anxiety.\n\n\
##Optimism: \n Hopefulness and confidence about the future or the success of something.\n\n\
##Realization: \n Becoming aware of something.\n\n\
##Relief: \n Reassurance and relaxation following release from anxiety or distress.\n\n\
##Remorse: \n Regret or guilty feeling. \n\n\
##Sadness: \n Emotional pain, sorrow.",
    "labels": [
        {"label": "Anger", "user": "annotator1"},
    ],
    "all_labels": [
        {"label": "Anger"},
        {"label": "Curiosity"},
{"label": "Desire"},
{"label": "Disappointment"},
{"label": "Disapproval"},
{"label": "Disgust"},
{"label": "Embarrassment"},
{"label": "Excitement"},
{"label": "Fear"},
{"label": "Gratitude"},
{"label": "Grief"},
{"label": "Joy"},
{"label": "Love"},
{"label": "Nervousness"},
{"label": "Optimism"},
{"label": "Realization"},
{"label": "Relief"},
{"label": "Remorse"},
{"label": "Sadness"},
    ],
    "chat_messages": [
        {"user": "annotator1", "message": "I labeled this as anger because the color red symbolizes anger and aggression in many contexts."},
        {"user": "annotator2", "message": "I disagree, I don't think the color alone is enough to indicate anger."},
    ],
    "sentence": "The red car sped past everyone at the intersection.",
},
        ]
    
    def get (self,request, task_id =0,*args, **kwargs ):
        
        if task_id < 0 or task_id >= len(self.tasks):
            raise Http404("Task not found")
        previous_task_id = task_id - 1 if task_id > 0 else None
        next_task_id = task_id + 1 if task_id < len(self.tasks) - 1 else None

        context = {
            "task": self.tasks[task_id],
            "tasks": self.tasks,
            "task_id": task_id,
            "previous_task_id": previous_task_id,
            "next_task_id": next_task_id,
            "progress_actual": (task_id+1)*100/len(self.tasks),
            "task_display_number": task_id+1,
        }
        messages.success(request, "Saved.")
        return render(request, "expert/dialogue_UI-Test.html", context)

    # def post (self,request,  task_id):
    #     #post_data = request.POST.dict()
    #     messages.success(request, "Saved.")
    #     if task_id < 0 or task_id >= len(self.tasks):
    #         raise Http404("Task not found")
    #     previous_task_id = task_id - 1 if task_id > 0 else None
    #     next_task_id = task_id + 1 if task_id < len(self.tasks) - 1 else None

    #     context = {
    #         "task": self.tasks[task_id],
    #         "tasks":self.tasks,
    #         "task_id": task_id,
    #         "previous_task_id": previous_task_id,
    #         "next_task_id": next_task_id,
    #         "progress_actual": task_id*100/len(self.tasks)
    #     }
    #     html = render_to_string("expert/dialogue_UI-Test.html", context, request=request)
    #     return HttpResponse(html)
