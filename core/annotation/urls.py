from django.urls import path

from . import views

urlpatterns = [
    path("batch/<int:batch_id>", views.annotate_batch, name="annotate-batch"),
    path("batch/<int:batch_id>/<int:assignment_id>", views.annotate_batch, name="annotate-batch"),
    path(
        "batch/<int:batch_id>/<int:assignment_id>/<str:cursor>",
        views.annotate_batch,
        name="annotate-batch",
    ),
]

htmx_patterns = [
    path("example/edit/<int:assignment_id>", views.edit, name="annotate-edit"),
]

urlpatterns += htmx_patterns
