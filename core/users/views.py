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

# Finishing page
def thank_you(request):
    return render(request, "Thank_you.html")

@login_not_required
def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect("project-list")
            else:
                return redirect("project-list")
    else:
        form = AuthenticationForm()
    return render(request, "core/login.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("login")


def user_profile(request):
    user = request.user

    groups = {group.name for group in user.groups.all()}

 #redirection
    if "Annotator" in groups:
        task_completed = True  
        if task_completed:
            return redirect("thank_you")

    context = {
        "is_admin": "Admin" in groups,
        "is_expert": "Expert" in groups,
        "is_annotator": "Annotator" in groups,
    }

    return render(request, "users/profile.html", context)


