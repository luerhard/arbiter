from django.core.paginator import Paginator
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from .models import Batch
from .models import Sentence
from .models import UserAnnotation
from core.models import Project


# Create your views here.


def annotate_batch(request, project_id, batch_number):
    project = get_object_or_404(Project, id=project_id)
    batch = get_object_or_404(Batch, project=project, batch_number=batch_number)
    sentences = batch.sentences.all()
    labels = project.labels.all()
    paginator = Paginator(sentences, 1)
    sent_number = request.GET.get("sentence", 1)
    sent_obj = paginator.get_page(sent_number)
    user_annotations = UserAnnotation.objects.prefetch_related("label").filter(
        sentence__id=sent_obj.object_list[0].id,
        user=request.user.id,
    )
    checked_labels = []
    for label in labels:
        try:
            user_label = next(anno for anno in user_annotations if label.pk == anno.label.pk)
            if user_label.is_set:
                checked_labels.append(True)
            else:
                checked_labels.append(False)
        except StopIteration:
            checked_labels.append(False)

    context = {
        "project_id": project_id,
        "batch_number": batch_number,
        "sent_obj": sent_obj,
        "labels": list(zip(labels, checked_labels, strict=False)),
    }
    if request.htmx:
        return render(request, "annotation/partials/sentence.html", context)
    else:
        return render(request, "annotation/sentence_view.html", context)


def edit_sentence(request, sentence_id):
    user_annotations = UserAnnotation.objects.prefetch_related("label").filter(
        sentence__id=sentence_id,
        user=request.user.id,
    )
    sentence = get_object_or_404(Sentence, id=sentence_id)
    project_labels = sentence.batch.project.labels
    submitted_labels = [int(i) for i in request.POST.getlist("labels")]
    new_annotations = []
    update_annotations = []
    for project_label in project_labels.all():
        try:
            annotation = next(
                anno for anno in user_annotations if anno.label.pk == project_label.pk
            )
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
        sentence=sentence_id,
        user=request.user.id,
    ).all()
    button = """ <button id="save-btn"
        type="submit"
        form="annotation-labels"
        class="btn btn-primary"
        style="width: 8rem; display: inline-block; margin: 0px; border-radius: 0px;"
        > Saved <i class="bi bi-check"></i>
    </button>
    """
    return HttpResponse(button)
