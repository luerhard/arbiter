from django.urls import path

from codebooks.views import CodebookVersionView

urlpatterns = [
    path(
        "<int:project_id>/<str:codebookversion>",
        CodebookVersionView.as_view(),
        name="codebook-version",
    ),
    path("<int:project_id>", CodebookVersionView.as_view(), name="codebook-version"),
]
