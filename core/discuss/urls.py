from django.urls import path

from . import views

urlpatterns = [
    path("<int:batch_id>", views.chat_simple, name="discuss-batch"),
]

htmx_patterns = [
    path("update-pbar/<int:batch_id>", views.get_progress, name="update-pbar"),
]

urlpatterns += htmx_patterns
