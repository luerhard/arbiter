from django.urls import path

from . import views

urlpatterns = [
    path(
        "batch/<int:batch_id>",
        views.ExpertBatchView.as_view(),
        name="expert-batch",
    ),
    path(
        "batch/<int:batch_id>/assignment/<int:assignment_id>",
        views.ExpertAssignmentView.as_view(),
        name="expert-assignment",
    ),
    path(
        "batch/<int:batch_id>/assignment/<int:assignment_id>/codebook",
        views.CodebookPanelView.as_view(),
        name="expert-codebook-panel",
    ),
    path(
        "batch/<int:batch_id>/assignment/<int:assignment_id>/draft",
        views.CodebookDraftSaveView.as_view(),
        name="expert-draft-save",
    ),
    path(
        "batch/<int:batch_id>/assignment/<int:assignment_id>/draft/delete",
        views.CodebookDraftDeleteView.as_view(),
        name="expert-draft-delete",
    ),
]
