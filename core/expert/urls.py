from django.urls import path

from . import views

urlpatterns = [
    # path("dialogue/<int:task_id>/", views.resolve_Disagreements, name="expert-dialogue"),
    #path("dialogue/<int:task_id>/", views.Usability_test.as_view(), name="expert-dialogue"),
    path("dialogue/<int:codebook_id>/<int:batch_id>/<int:example_id>/", views.ExpertDialogue.as_view(), name="expert-dialogue",   ),
]
