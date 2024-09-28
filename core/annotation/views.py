from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from .models import Annotation
from .models import UserSentence
from annotation.models import Sentence
from core.models import Batch
from core.models import Project


# Create your views here.
def annotate_batch(request, project_id, batch_number):
    project = get_object_or_404(Project, id=project_id)
    batch = get_object_or_404(Batch, project=project, batch_number=batch_number)

    sentences = Sentence.objects.filter(batch=batch)
    paginator = Paginator(sentences, 1)
    sent_number = request.GET.get("sentence", 1)
    sent_obj = paginator.get_page(sent_number)
    sentence = sent_obj[0]

    previous_annotations = (
        sentence.get_user_annotations(request.user, phase="ANNOTATION")
        .select_related("label")
        .all()
    )

    labels = []
    for label in sentence.labels.all():
        new = {
            "name": label.name,
            "id": label.id,
        }
        if label in previous_annotations:
            new["is_set"] = True
        else:
            new["is_set"] = False
        labels.append(new)

    context = {
        "project_id": project_id,
        "batch_number": batch_number,
        "sent_obj": sent_obj,
        "labels": labels,
    }

    if request.htmx:
        return render(request, "annotation/partials/sentence.html", context)
    else:
        return render(request, "annotation/sentence_view.html", context)


def edit_sentence(request, sentence_id):
    sentence = Sentence.objects.get(id=sentence_id)
    batch = sentence.batch
    if batch.annotation_done:
        raise PermissionDenied()
    submitted_labels = [int(i) for i in request.POST.getlist("labels") if i.strip()]
    sentence.set_user_annotations(user=request.user, phase="ANNOTATION", label_ids=submitted_labels)

    button = """<button id="save-btn"
            type="submit"
            form="label-form"
            class="btn btn-outline-primary"
            hx-swap-oob='true'>
            Saved <i class="bi bi-check"></i>
    </button>"""
    return HttpResponse(button)
