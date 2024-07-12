from django.urls import path

from . import views


urlpatterns = [
    path("", views.simple, name="index"),
    path("sentences/<int:project_id>", views.annotate_sentence, name="sentences"),
    path("sentences/<int:sentence_id>/edit", views.edit_sentence, name="edit-sentence"),
]
