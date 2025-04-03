from django.urls import path

from . import views

urlpatterns = [
    path("view/<int:codebook_id>", views.CodebookView.as_view(), name="codebook-view"),
    path(
        "diff/<int:codebook_id>/",
        views.CodebookDiffView.as_view(),
        name="codebook-diff",
    ),
    path("edit/<int:codebook_id>", views.CodebookUpdateView.as_view(), name="codebook-edit"),
]
