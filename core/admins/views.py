from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test

from annotation.models import Sentence
from .forms import ProjectForm, ProjectAssignmentForm
from core.models import Project, ProjectAssignment
import pandas as pd

def is_admin(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(is_admin)
def assignment_list(request):
    assignments = ProjectAssignment.objects.all()
    return render(request, 'admin_panel/assignment_list.html', {'assignments': assignments})

@user_passes_test(is_admin)
def project_list(request):
    projects = Project.objects.all()
    return render(request, 'admin_panel/project_list.html', {'projects': projects})

@user_passes_test(is_admin)
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_panel:project_list')
    else:
        form = ProjectForm()
    return render(request, 'admin_panel/create_project.html', {'form': form})

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
    if request.method == 'POST':
        form = ProjectAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_panel:assignment_list')  # Ensure this URL name matches your URL configuration
    else:
        form = ProjectAssignmentForm()
    return render(request, 'admin_panel/assign_annotators.html', {'form': form})

def sentence_list(request):
    # Fetch all sentences from the database
    sentences = Sentence.objects.all()
    print(sentences)
    # Render the template with the sentences
    return render(request, 'admin_panel/sentence_list.html', {'sentences': sentences})


@user_passes_test(is_admin)
def upload_sentences(request):
    if request.method == 'POST':
        project_id = request.POST.get('project')
        file = request.FILES['file']
        project = Project.objects.get(id=project_id)
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.name.endswith('.xlsx'):
            df = pd.read_excel(file)
        for index, row in df.iterrows():
            Sentence.objects.create(project=project, content=row['text'])
        return redirect('admin_panel:sentence_list')
    projects = Project.objects.all()
    return render(request, 'admin_panel/upload_sentences.html', {'projects': projects})
