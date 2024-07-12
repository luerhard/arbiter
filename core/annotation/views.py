from django.core.paginator import Paginator
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from .models import Sentence
from .models import UserAnnotation
from core.models import Project


# Create your views here.


def simple(request):
    return HttpResponse("Simple Success!")


def edit_sentence(request, sentence_id):
    user_annotations = UserAnnotation.objects.filter(
        sentence__id=sentence_id,
        user=request.user.id,
    )
    sentence = get_object_or_404(Sentence, id=sentence_id)
    project_labels = sentence.project.labels
    submitted_labels = [int(i) for i in request.POST.getlist("labels")]
    new_annotations = []
    update_annotations = []
    for project_label in project_labels.all():
        try:
            annotation = next(anno for anno in user_annotations if anno.pk == project_label.pk)
            is_new = False
        except StopIteration:
            annotation = UserAnnotation(user=request.user, sentence=sentence, label=project_label)
            is_new = True
        
        if project_label.pk in submitted_labels:
            annotation.is_set = True
        else:
            annotation.is_set = False
        
        if is_new:
            new_annotations.append(annotation)
        else:
            update_annotations.append(annotation)

    UserAnnotation.objects.bulk_create(new_annotations)
    UserAnnotation.objects.bulk_update(update_annotations, fields=["is_set", "last_updated"])

    user_annotations = UserAnnotation.objects.filter(
        sentence__id=sentence_id,
        user=request.user.id,
    )
    # return render(request, "annotation/partials/sentence.html", context)
    return HttpResponse(f"{list(user_annotations)}")


def annotate_sentence(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    sentences = Sentence.objects.filter(project_id=project.id)
    labels = project.labels
    paginator = Paginator(sentences, 1)
    sent_number = request.GET.get("sentence", 1)
    sent_obj = paginator.get_page(sent_number)
    context = {
        "sent_obj": sent_obj,
        "labels": labels,
    }
    return render(request, "annotation/sentence_view.html", context)
