from django.contrib.auth.decorators import user_passes_test
from django.db.models import Max
from django.shortcuts import redirect
from django.shortcuts import render
import pandas as pd

from .forms import ProjectAssignmentForm
from .forms import ProjectForm
from annotation.models import Batch
from annotation.models import Sentence
from core.models import Project
from core.models import ProjectAssignment


def is_admin(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(is_admin)
def assignment_list(request):
    assignments = ProjectAssignment.objects.all()
    return render(request, "admin_panel/assignment_list.html", {"assignments": assignments})

@user_passes_test(is_admin)
def project_list(request):
    projects = Project.objects.all()
    return render(request, "admin_panel/project_list.html", {"projects": projects})

@user_passes_test(is_admin)
def create_project(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_panel:project_list")
    else:
        form = ProjectForm()
    return render(request, "admin_panel/create_project.html", {"form": form})

@user_passes_test(is_admin)
# def assign_users(request):
#     if request.method == 'POST':
#         form = ProjectAssignmentForm(request.POST)
#         if form.is_valid():
#             project = form.cleaned_data['project']
#             users = form.cleaned_data['user']
#             for user in users:
#                 ProjectAssignment.objects.create(project=project, user=user)
#             return redirect('admin_panel:assignment_list')
#     else:
#         form = ProjectAssignmentForm()
#     return render(request, 'admin_panel/assign_annotators.html', {'form': form})

# def assign_users(request):
#     if request.method == 'POST':
#         form = ProjectAssignmentForm(request.POST)
#         if form.is_valid():
#             print(form.cleaned_data['user'])
#             project = form.cleaned_data['project']
#             users = form.cleaned_data['user']
#             for user in users:
#                 ProjectAssignment.objects.create(project=project, user=user)
#             return redirect('admin_panel:assignment_list')
#     else:
#         form = ProjectAssignmentForm()
#     return render(request, 'admin_panel/assign_annotators.html', {'form': form})

def assign_users(request):
    if request.method == "POST":
        form = ProjectAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_panel:assignment_list")  # Ensure this URL name matches your URL configuration
    else:
        form = ProjectAssignmentForm()
    return render(request, "admin_panel/assign_annotators.html", {"form": form})

def sentence_list(request):
    # Fetch all sentences from the database
    sentences = Sentence.objects.all()
    print(sentences)
    # Render the template with the sentences
    return render(request, "admin_panel/sentence_list.html", {"sentences": sentences})


@user_passes_test(is_admin)
def upload_sentences(request):
    if request.method == "POST":
        project_id = request.POST.get("project")
        file = request.FILES["file"]
        project = Project.objects.get(id=project_id)
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file)
        
        #get max previous batch number and increment by one
        max_batch_number = Batch.objects.filter(project=project).aggregate(Max("batch_number"))
        max_batch_number = max_batch_number["batch_number__max"]
        if max_batch_number is None:
            max_batch_number = 0

        max_batch_number += 1

        batch = Batch(project=project, batch_number=max_batch_number)
        batch.save()
        sentences = []
        for _, row in df.iterrows():
            sent = Sentence(project=project, batch=batch, content=row["text"])
            sentences.append(sent)
        Sentence.objects.bulk_create(sentences)
        return redirect("admin_panel:sentence_list")
    projects = Project.objects.all()
    return render(request, "admin_panel/upload_sentences.html", {"projects": projects})
