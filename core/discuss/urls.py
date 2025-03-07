from django.urls import path

from . import views

urlpatterns = [
    # path("", views.overview, name="discuss-list"),
    path("<int:batch_id>", views.chat_simple, name="discuss-batch"),
]

htmx_patterns = [
    # path("sentences/<int:sentence_id>/edit", views.edit_sentence, name="edit-sentence"),
    path("update-pbar/<int:batch_id>", views.update_pbar, name="update-pbar"),
]

urlpatterns += htmx_patterns
