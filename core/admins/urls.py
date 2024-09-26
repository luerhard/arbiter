from django.urls import path

from . import views

urlpatterns = [
    path("projects/", views.ProjectListView.as_view(), name="manage-projects"),
    path("projects/<int:pk>", views.ProjectDetailView.as_view(), name="manage-project-detail"),
    path(
        "project/export-annotations/<int:batch_id>",
        views.export_annotations,
        name="export-annotations",
    ),
]

htmx_patterns = [
    path("projects/toggle_finalize", views.toggle_finalize, name="toggle-finalize"),
]

urlpatterns += htmx_patterns
