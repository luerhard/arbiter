from django.urls import path

from . import views

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="project-list"),
    path("<int:project_id>", views.ProjectDetailView.as_view(), name="project-detail"),
    path(
        "<int:project_id>/expert",
        views.ProjectExpertDetailView.as_view(),
        name="project-detail-expert",
    ),
    path(
        "<int:project_id>/annotator",
        views.ProjectAnnotatorDetailView.as_view(),
        name="project-detail-annotator",
    ),
    path("export/batch/<int:batch_id>", views.export_batch, name="export-batch"),
]

htmx_patterns = [path("edit/<int:batch_id>", views.change_batch_phase, name="change-batch-phase")]

urlpatterns += htmx_patterns
