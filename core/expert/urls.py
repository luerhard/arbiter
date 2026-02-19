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
        views.ExpertDialog.as_view(),
        name="expert-dialogue",
    ),
    path(
        "dialogue/<int:batch_id>/content",
        views.ExpertDialogueContent.as_view(),
        name="expert-dialogue-content",
    ),
]
