from django.urls import path

from . import views

urlpatterns = [
    path("batch/<int:batch_id>", views.annotate_batch, name="annotate-batch"),
    path("batch/<int:batch_id>/<int:batch_order>", views.annotate_batch, name="annotate-batch"),
]

htmx_patterns = [
    path("sentences/<int:sentence_id>/edit", views.edit_sentence, name="edit-sentence"),
]

urlpatterns += htmx_patterns
