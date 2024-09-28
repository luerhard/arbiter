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
    labels = project.labels.all()
    annotated_sentences_count = batch.annotated_sentences(request.user)
    total_sentences = sentences.count()
    progress = (annotated_sentences_count / total_sentences * 100) if total_sentences > 0 else 0
    progress_formatted = format(progress, ".1f")
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
        "progress": progress_formatted,
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

    # Calculate progress using the updated count
    total_sentences = batch.sentences.count()
    annotated_sentences = batch.annotated_sentences(request.user)
    progress = (annotated_sentences / total_sentences) * 100 if total_sentences > 0 else 0
    progress_formatted = format(progress, ".1f")
    # Return the updated progress context and button HTML
    button = """ <button id="save-btn"
        type="submit"
        form="annotation-labels"
        class="btn btn-primary"
        style="width: 8rem"
        > Saved <i class="bi bi-check"></i>
    </button>
    """
    return HttpResponse(f"""
        {button}
        <script>
            document.querySelector('.progress-bar').style.width = '{progress_formatted}%';
            document.querySelector('.progress-bar').innerHTML= '{progress_formatted}%';
        </script>
    """)
