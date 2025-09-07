from django.urls import path

from . import views

urlpatterns = [
    path(
        "expert-save-labels/<int:codebook_id>/<int:batch_id>/<int:example_id>/",
        views.expert_save_labels,
        name="expert-label-save",
    ),
]
