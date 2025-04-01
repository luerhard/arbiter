from django.urls import path

from . import views

urlpatterns = [
    path("view/<int:pk>", views.CodebookView.as_view(), name="codebook-view"),
    path(
        "diff/<int:pk>/",
        views.CodebookDiffView.as_view(),
        name="codebook-diff",
    ),
    path("edit/<int:pk>", views.CodebookUpdateView.as_view(), name="codebook-edit"),
]
