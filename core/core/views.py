from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render

User = get_user_model()


@login_not_required
def core(request):
    return render(request, "base.html")
