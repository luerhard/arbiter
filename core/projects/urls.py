from django.urls import path

from . import views

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="project-list"),
    path("create/", views.ProjectCreateView.as_view(), name="project-create"),
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
    path("export/batch/<int:batch_id>", views.ExportBatch.as_view(), name="export-batch"),
]

htmx_patterns = [
    path("edit/<int:batch_id>", views.ChangeBatchPhase.as_view(), name="change-batch-phase"),
]

urlpatterns += htmx_patterns
