from django.urls import path

from . import views

urlpatterns = [
    path(
        "sentences/project<int:project_id>/batch<int:batch_number>",
        views.annotate_batch,
        name="annotate-batch",
    ),
]

htmx_patterns = [
    path("sentences/<int:sentence_id>/edit", views.edit_sentence, name="edit-sentence"),
]

urlpatterns += htmx_patterns
