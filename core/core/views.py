from django.shortcuts import render
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegistrationForm
from annotation.models import Sentence
from core.models import ProjectAssignment
from django.contrib.auth.decorators import login_required

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

@login_required
def dashboard(request):
    # Fetch assigned sentences
    assigned_projects = ProjectAssignment.objects.filter(user=request.user).values_list('project', flat=True)
    sentences = Sentence.objects.filter(project__in=assigned_projects)
    
    return render(request, 'core/dashboard.html', {'sentences': sentences})

def user_logout(request):
    logout(request)
    return redirect('login')