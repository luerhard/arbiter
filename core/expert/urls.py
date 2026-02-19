from django.urls import path

from . import views

urlpatterns = [
    path(
        "expert-save-labels/<int:codebook_id>/<int:batch_id>/<int:example_id>/",
        views.SaveLabelsExpert.as_view(),
        name="expert-label-save",
    ),
    path(
        "dialogue/<int:codebook_id>/<int:batch_id>/<int:example_id>/",
        views.ExpertDialogue.as_view(),
        name="expert-dialogue",
    ),
]
