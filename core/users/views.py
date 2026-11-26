import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import render

from .forms import PasswordChangeForm
from .forms import ProfileForm
from .forms import UserRegistrationForm
from core.models import SiteSettings

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
    context = {"form": form, "allow_registration": SiteSettings.load().allow_registration}
    return render(request, "core/login.html", context)


@login_not_required
def user_register(request):
    if not SiteSettings.load().allow_registration:
        raise Http404
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            log.info("%s registered", user.username)
            return redirect("home")
    else:
        form = UserRegistrationForm()
    return render(request, "core/register.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("login")


def user_profile(request):
    """The user's own account: name and email, and the password. Two forms on one page;
    a hidden "form" field says which one was sent."""
    user = request.user
    profile_form = ProfileForm(instance=user)
    password_form = PasswordChangeForm(user)

    if request.method == "POST":
        if request.POST.get("form") == "password":
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                # otherwise changing the password signs the user out
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Password changed.")
                return redirect("user-profile")
        else:
            profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile saved.")
                return redirect("user-profile")

    context = {"profile_form": profile_form, "password_form": password_form}
    return render(request, "users/profile.html", context)
