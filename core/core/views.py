from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegistrationForm
from annotation.models import Sentence, Label, Annotation
from core.models import Project, ProjectAssignment
import json

def core(request):
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'core/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect('admin_panel:project_list')
            else:
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

@login_required
def dashboard(request):
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

def colors():
    return ["#AF7AC5", "#E74C3C", "#27AE60", "#5DADE2", "#F7DC6F"]


@login_required
def annotate_sentence(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    sentences = Sentence.objects.filter(project=project).order_by('id').values('id', 'content')
    labels = project.labels.split(',')
    get_color = colors()
    labels_list = [{"name": value, "color": get_color[index]} for index, value in enumerate(labels)]

    return render(request, 'core/sentence_display.html', {
        'project': project,
        'sentences': list(sentences),
        'labels': labels_list
    })

@login_required
def save_annotations(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Received data:", data)  # Debugging statement
            sentence_id = data.get('sentence_id')
            pre_label_name = data.get('pre_label_name')
            project_id = data.get('project_id')  # Assuming you have project_id in your data

            # Fetch the sentence and project objects
            sentence = get_object_or_404(Sentence, id=sentence_id)
            project = get_object_or_404(Project, id=project_id)

            # Handle the pre_label_name
            if pre_label_name:
                try:
                    # Create or get the label
                    label, created = Label.objects.get_or_create(name=pre_label_name, project=project)
                    print("Found or created label:", label)
                    annotation, created = Annotation.objects.update_or_create(
                        sentence=sentence,
                        defaults={'pre_label': label, 'post_label': None}  # Use the label object here
                    )
                    print("Annotation saved:", annotation)
                except Exception as e:
                    print("Error finding label or saving annotation:", str(e))
                    return JsonResponse({'error': str(e)}, status=400)
            elif pre_label_name is None:
                print("Pre_label_name is none")
                Annotation.objects.filter(sentence=sentence).delete()
                return JsonResponse({'message': 'Annotation Reset Successful'}, status=200)

            return JsonResponse({'message': 'Annotation saved successfully'}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def get_annotation(request, sentence_id):
    try:
        sentence = Sentence.objects.get(id=sentence_id)
        annotation = Annotation.objects.filter(sentence=sentence).first()
        pre_label_name = annotation.pre_label.name if annotation else None
        return JsonResponse({'pre_label_name': pre_label_name})
    except Sentence.DoesNotExist:
        return JsonResponse({'pre_label_name': None})

def user_logout(request):
    logout(request)
    return redirect('login')
