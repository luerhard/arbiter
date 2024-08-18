from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.overview, name="discuss-list"),
    path("batch<int:batch_id>/", views.discuss_batch, name="discuss-batch"),
    path("chat/<int:batch_id>/", views.chat_simple, name="chat-simple"),
]

htmx_patterns = [
    # path("sentences/<int:sentence_id>/edit", views.edit_sentence, name="edit-sentence"),
]

urlpatterns += htmx_patterns
