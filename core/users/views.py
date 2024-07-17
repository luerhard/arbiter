from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.shortcuts import render

from .forms import UserRegistrationForm


# Create your views here.

def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("list-projects")
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
                return redirect("list-projects")
            else:
                return redirect("list-projects")
    else:
        form = AuthenticationForm()
    return render(request, "core/login.html", {"form": form})

def user_logout(request):
    logout(request)
    return redirect("login")

def user_profile(request):
    user = request.user

    groups = {group.name for group in user.groups.all()}

    context = {
        "is_admin": "Admin" in groups,
        "is_expert": "Expert" in groups,
        "is_annotator": "Annotator" in groups,
    }

    return render(request, "users/profile.html", context)
