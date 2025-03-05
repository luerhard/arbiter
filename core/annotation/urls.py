from django.urls import path

from . import views

urlpatterns = [
    path("batch/<int:batch_id>", views.annotate_batch, name="annotate-batch"),
]

htmx_patterns = [
    path("next/<int:assignment_id>", views.next_sentence, name="annotate-next"),
    path("prev/<int:assignment_id>", views.prev_sentence, name="annotate-prev"),
    path("example/edit/<int:assignment_id>", views.edit, name="annotate-edit"),
]

urlpatterns += htmx_patterns
