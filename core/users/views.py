import logging

from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.shortcuts import render

# Create your views here.
# def register(request):
#     if request.method == "POST":
#         form = UserRegistrationForm(request.POST)
#         if form.is_valid():
#             user = form.save()
#             login(request, user)
#             return redirect("list-projects")
#     else:
#         form = UserRegistrationForm()
#     return render(request, "core/register.html", {"form": form})

log = logging.getLogger(__name__)


@login_not_required
def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "core/login.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("login")


def user_profile(request):
    user = request.user
    log.debug(user)
    # groups = {group.name for group in user.groups.all()}

    context = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "user_id": user.id,
        "password": user.password,
        # "is_admin": "Admin" in groups,
        # "is_expert": "Expert" in groups,
        # "is_annotator": "Annotator" in groups,
    }
    log.debug(context)
    return render(request, "users/profile.html", context)
