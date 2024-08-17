from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.shortcuts import render

from annotation.models import Batch

# Create your views here.


def overview(request):
    user = request.user
    context = {"projects": user.discuss_batches}
    return render(request, "discuss/overview.html", context)


def discuss_batch(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    context = {"sentences": batch.discuss_disagreement_sentences}
    return render(request, "discuss/discuss_batch.html", context)
