from django.urls import path

from codebooks.views import CodebookVersionView

urlpatterns = [
    path(
        "<int:project_id>/<str:version_name>",
        CodebookVersionView.as_view(),
        name="codebook-version",
    ),
    path("<int:project_id>", CodebookVersionView.as_view(), name="codebook-version"),
]
