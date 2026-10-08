from django.urls import path

from . import views

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="project-list"),
    path("create/", views.ProjectCreateView.as_view(), name="project-create"),
    path(
        "<int:project_id>/batches/create",
        views.ProjectBatchCreateView.as_view(),
        name="project-batch-create",
    ),
    path("<int:project_id>", views.ProjectDetailView.as_view(), name="project-detail"),
    path("<int:project_id>/delete", views.ProjectDeleteView.as_view(), name="project-delete"),
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
    path("batches/<int:batch_id>", views.BatchSamplesView.as_view(), name="project-batch-detail"),
    path(
        "batches/<int:batch_id>/samples/<int:example_id>",
        views.SampleDetailView.as_view(),
        name="project-sample-detail",
    ),
    path("export/batch/<int:batch_id>", views.ExportBatch.as_view(), name="project-export-batch"),
    path(
        "export/project/<int:project_id>",
        views.ExportProject.as_view(),
        name="project-export-project",
    ),
]

htmx_patterns = [
    path("htmx/label-row", views.ProjectLabelRowView.as_view(), name="project-label-row"),
    path("edit/<int:batch_id>", views.ChangeBatchPhase.as_view(), name="change-batch-phase"),
    path("delete/<int:batch_id>", views.DeleteBatch.as_view(), name="delete-batch"),
    path(
        "batches/<int:batch_id>/order", views.BatchOrderView.as_view(), name="project-batch-order"
    ),
    path("htmx/user-search", views.HtmxUserSearch.as_view(), name="project-user-search"),
]

urlpatterns += htmx_patterns
