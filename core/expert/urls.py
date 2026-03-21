from django.urls import path

from . import views

urlpatterns = [
    path(
        "save/<int:assignment_id>/<int:codebook_id>",
        views.ExpertDialogue.as_view(),
        name="expert-save",
    ),
    path(
        "dialogue/<int:batch_id>",
        views.ExpertDialogue.as_view(),
        name="expert-dialogue",
    ),
]
