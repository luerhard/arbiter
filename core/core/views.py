from django.http import JsonResponse
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegistrationForm
from annotation.models import Sentence, Label, Annotation
from core.models import Project, ProjectAssignment
import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

def core(request):
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('core:dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'core/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if(user.is_staff):
                return redirect('admin_panel:project_list')
            else:
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

# @login_required
# def dashboard(request):
#     # Fetch assigned sentences
#     assigned_projects = ProjectAssignment.objects.filter(user=request.user).values_list('project', flat=True)
#     sentences = Sentence.objects.filter(project__in=assigned_projects)
    
#     return render(request, 'core/dashboard.html', {'sentences': sentences})
@login_required
def dashboard(request):
    # Get projects assigned to the logged-in user
    assignments = ProjectAssignment.objects.filter(user=request.user)
    projects_with_sentences = []

    for assignment in assignments:
        project = assignment.project
        first_sentence = Sentence.objects.filter(project=project).first()
        projects_with_sentences.append({
            'project': project,
            'first_sentence_id': first_sentence.id if first_sentence else None
        })

    return render(request, 'core/dashboard.html', {
        'projects_with_sentences': projects_with_sentences
    })


@login_required
def annotate_sentence(request, project_id, sentence_id):
    project = get_object_or_404(Project, id=project_id)
    sentence = get_object_or_404(Sentence, id=sentence_id)
    labels = project.labels.split(',')
    next_sentence = Sentence.objects.filter(project=project, id__gt=sentence_id).order_by('id').first()

    return render(request, 'core/sentence_display.html', {
        'project': project,
        'sentence': sentence,
        'labels': labels,
        'next_sentence_id': next_sentence.id if next_sentence else None,
    })

def colors():
    return ["#AF7AC5", "#E74C3C", "#27AE60", "#5DADE2", "#F7DC6F"]
# @csrf_exempt
@login_required
def annotate_sentence(request, project_id, sentence_id):
    project = get_object_or_404(Project, id=project_id)
    sentence = get_object_or_404(Sentence, id=sentence_id)
    labels = project.labels.split(',')
    labels_list = []
    get_color = colors()
    for index, value in enumerate(labels):
        labels_dict = {"name": value, "color": get_color[index]}
        print(labels_dict)
        labels_list.append(labels_dict)

    return render(request, 'core/sentence_display.html', {
        'project': project,
        'sentence': sentence,
        'labels': labels_list,
    })

# @csrf_exempt
@login_required
def save_annotation(request):
    if request.method == 'POST':
        sentence_id = request.POST.get('sentence_id')
        label_id = request.POST.get('label_id')
        start_offset = request.POST.get('start_offset')
        end_offset = request.POST.get('end_offset')
        text = request.POST.get('text')

        sentence = get_object_or_404(Sentence, id=sentence_id)
        label = get_object_or_404(Label, id=label_id)

        annotation = Annotation.objects.create(
            sentence=sentence,
            label=label,
            start_offset=start_offset,
            end_offset=end_offset,
            text=text,
        )
        print(annotation)
        return JsonResponse({'success': True})

    return JsonResponse({'success': False}, status=400)

@csrf_exempt
@login_required
def save_annotations(request):
    if request.method == 'POST':
        sentence_id = request.POST.get('sentence_id')
        annotations_data = request.POST.get('annotations')
        
        sentence = get_object_or_404(Sentence, id=sentence_id)

        if annotations_data:
            annotations = json.loads(annotations_data)
            for annotation in annotations:
                label_id = annotation['label_id']
                start_offset = annotation['start_offset']
                end_offset = annotation['end_offset']
                text = annotation['text']

                label = get_object_or_404(Label, pk=label_id)

                Annotation.objects.create(
                    sentence=sentence,
                    label=label,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text=text
                )
                print(annotation)
            return JsonResponse({'success': True})

    return JsonResponse({'success': False}, status=400)
# @login_required
# def annotate_sentence(request, sentence_id):
#     sentence = get_object_or_404(Sentence, id=sentence_id)
#     if request.method == 'POST':
#         annotations = json.loads(request.POST.get('annotations', '[]'))
#         sentence.annotations = annotations
#         sentence.save()
#         return JsonResponse({'status': 'success'})

#     return render(request, 'core/annotate_sentence.html', {
#         'sentence': sentence,
#         'labels': sentence.project.labels.split(','),
#     })

# @login_required
# def annotate_sentence(request, sentence_id):
#     sentence = get_object_or_404(Sentence, id=sentence_id)
#     labels = sentence.project.labels.split(',')
#     return render(request, 'core/annotate_sentence.html', {'sentence': sentence, 'labels': labels})


# @login_required
# def save_annotation(request):
#     if request.method == 'POST':
#         sentence_id = request.POST.get('sentence_id')
#         annotated_content = request.POST.get('annotated_content')
#         sentence = get_object_or_404(Sentence, id=sentence_id)
#         sentence.annotated_content = annotated_content
#         sentence.save()
#         return JsonResponse({'success': True})
#     return JsonResponse({'success': False}, status=400)

def user_logout(request):
    logout(request)
    return redirect('login')