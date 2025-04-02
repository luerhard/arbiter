from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse

from data.models import Example
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import Project
from projects.models import ProjectUser

# Create your views here.


def get_progress(request, batch_id):
    query = ExampleAssignment.objects.filter(
        example__batch=batch_id,
        example__has_disagreement=True,
        user=request.user,
    )
    context = {}
    context["batch_id"] = batch_id
    context["done"] = query.filter(is_discussed=True).count()
    context["total"] = query.count()
    try:
        context["progress"] = int(context["done"] / context["total"] * 100)
    except ZeroDivisionError:
        context["progress"] = 100

    return render(request, "discuss/index.html#pbar", context)


def chat_simple(request, batch_id):
    if request.method == "POST":
        return redirect(reverse("chat", kwargs={"batch_id": batch_id}))
    else:
        return render(request, "discuss/index.html", {"batch_id": batch_id})
