from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.shortcuts import render

from .forms import UserRegistrationForm
from core.models import ProjectAssignment


def core(request):
    return render(request, "home.html")

def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = UserRegistrationForm()
    return render(request, "core/register.html", {"form": form})

def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect("admin_panel:project_list")
            else:
                return redirect("dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "core/login.html", {"form": form})

@login_required
def dashboard(request):
    assignments = ProjectAssignment.objects.filter(user=request.user)
    projects_with_sentences = []

    all_assignments = []

    for assignment in assignments:
        project = assignment.project
        batch_numbers = [batch.batch_number for batch in project.batches.all()]
        all_assignments.append((project.name, project.pk, batch_numbers))

        # first_sentence = Sentence.objects.filter(project=project).first()
        # projects_with_sentences.append({
        #     "project": project,
        #     "first_sentence_id": first_sentence.id if first_sentence else None,
        # })
    
    context = {
        "assignments": all_assignments,
    }

    return render(request, "core/dashboard.html", context)

def colors():
    return ["#AF7AC5", "#E74C3C", "#27AE60", "#5DADE2", "#F7DC6F"]


# @login_required
# def annotate_sentence(request, project_id):
#     project = get_object_or_404(Project, id=project_id)
#     sentences = Sentence.objects.filter(project=project).order_by('id').values('id', 'content')
#     labels = project.labels.split(',')
#     get_color = colors()
#     labels_list = [{"name": value, "color": get_color[index]} for index, value in enumerate(labels)]

#     return render(request, 'core/sentence_display.html', {
#         'project': project,
#         'sentences': list(sentences),
#         'labels': labels_list,
#     })

# @login_required
# def save_annotations(request):
#     if request.method == 'POST':
#         data = json.loads(request.body)
#         sentence_id = data.get('sentence_id')
#         pre_label_name = data.get('pre_label_name')

#         if sentence_id is not None:
#             sentence = get_object_or_404(Sentence, id=sentence_id)
#             if pre_label_name:
#                 label = get_object_or_404(Label, name=pre_label_name)
#                 annotation, created = Annotation.objects.update_or_create(
#                     sentence=sentence,
#                     pre_label=label
#                 )
#                 # annotation.pre_label_name = pre_label_name
#                 annotation.save()
#             else:
#                 Annotation.objects.filter(sentence=sentence).delete()

#             return JsonResponse({'status': 'success'})
#         return JsonResponse({'status': 'error', 'message': 'Invalid sentence ID'}, status=400)
#     return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

# @login_required
# def get_annotation(request, sentence_id):
#     try:
#         sentence = Sentence.objects.get(id=sentence_id)
#         annotation = Annotation.objects.filter(sentence=sentence).first()
#         pre_label_name = annotation.pre_label_name if annotation else None
#         return JsonResponse({'pre_label_name': pre_label_name})
#     except Sentence.DoesNotExist:
#         return JsonResponse({'pre_label_name': None})

def user_logout(request):
    logout(request)
    return redirect("login")
