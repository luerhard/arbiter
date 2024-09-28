from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from data.models import Example
from projects.models import Batch
from projects.models import Project


# Create your views here.
def annotate_batch(request, batch_id, batch_order=None):
    batch = Batch.objects.get(id=batch_id)
    project = batch.project

    examples = Example.objects.filter(batch=batch)
    labels = project.labels.all()
    annotated_examples_count = batch.examples.filter(
        assignments__user=request.user, assignments__is_annotated=1
    ).count()
    total_examples = examples.count()
    progress = (annotated_examples_count / total_examples * 100) if total_examples > 0 else 0
    progress_formatted = format(progress, ".1f")
    paginator = Paginator(examples, 1)
    ex_number = request.GET.get("sentence", 1)
    ex_obj = paginator.get_page(ex_number)
    example = ex_obj[0]

    previous_annotations = (
        example.get_user_annotations(user=request.user, phase="ANNOTATION")
        .select_related("label")
        .all()
    )

    labels = []
    for label in example.labels.all():
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
        "project_id": project.id,
        "batch_number": batch.batch_number,
        "sent_obj": ex_obj,
        "labels": labels,
        "progress": progress_formatted,
    }

    if request.htmx:
        return render(request, "annotation/partials/sentence.html", context)
    else:
        return render(request, "annotation/sentence_view.html", context)


def edit_sentence(request, sentence_id):
    sentence = Example.objects.get(id=sentence_id)
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
