from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.generic import DetailView
from django.views.generic import ListView

User = get_user_model()


@login_not_required
def core(request):
    return render(request, "base.html")
