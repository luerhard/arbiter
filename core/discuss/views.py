from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse

from core.models import Batch

# Create your views here.


def overview(request):
    user = request.user
    new = {}
    for project, batches in user.discuss_batches.items():
        new_batches = []
        for batch in batches:
            total = batch.sentences.count()
            disagreement = list(batch.sentences.aggregate(Sum("has_disagreement_labels")).values())[
                0
            ]
            if not disagreement:
                disagreement = 0
            new_batches.append({"batch": batch, "total": total, "disagreement": int(disagreement)})
        new[project] = new_batches

    context = {"projects": new}
    return render(request, "discuss/overview.html", context)


def chat_simple(request, batch_id):
    if request.method == "POST":
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))
    else:
        return render(request, "discuss/room.html", {"batch_id": batch_id})


def discuss_batch(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    context = {"sentences": batch.discuss_disagreement_sentences}
    return render(request, "discuss/discuss_batch.html", context)
