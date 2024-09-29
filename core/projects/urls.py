from django.urls import path

from . import views

urlpatterns = [
    path("", views.project_list_view, name="project-list"),
    path("<int:project_id>", views.project_detail_view, name="project-detail"),
    path("export/batch/<int:batch_id>", views.export_batch, name="export-batch"),
]

htmx_patterns = [path("edit/<int:batch_id>", views.change_batch_phase, name="change-batch-phase")]

urlpatterns += htmx_patterns
