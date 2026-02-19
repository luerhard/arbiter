from django.urls import path

from . import views

urlpatterns = [
    path(
        "save-labels/<int:assignment_id>/",
        views.SaveLabelsExpert.as_view(),
        name="expert-label-save",
    ),
    path(
        "dialogue/<int:batch_id>",
        views.ExpertDialogue.as_view(),
        name="expert-dialogue",
    ),
]
