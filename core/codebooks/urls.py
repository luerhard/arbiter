from django.urls import path

from codebooks import views

urlpatterns = [
    path(
        "<int:project_id>/<str:version_name>",
        views.CodebookVersionView.as_view(),
        name="codebook-version",
    ),
    path("<int:project_id>", views.CodebookVersionView.as_view(), name="codebook-version"),
    path("edit/<int:codebook_id>", views.edit, name="codebook-edit"),
]

htmx_patterns = [
    path("edit/sort-examples", views.sort_examples, name="codebook-sort-examples"),
    path(
        "edit/add-example/<int:definition_id>",
        views.AddExample.as_view(),
        name="codebook-add-example",
    ),
    path(
        "edit/update-example/<int:example_id>",
        views.UpdateExample.as_view(),
        name="codebook-update-example",
    ),
    path(
        "edit/delete-example/<int:example_id>",
        views.DeleteExample.as_view(),
        name="codebook-delete-example",
    ),
]

urlpatterns += htmx_patterns
