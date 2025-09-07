from django.urls import path

from . import views

urlpatterns = [
    path(
        "dialogue/<int:codebook_id>/<int:batch_id>/<int:example_id>/",
        views.ExpertDialogue.as_view(),
        name="expert-dialogue",
    ),
]
