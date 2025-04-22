from django.urls import path
from . import views

urlpatterns = [
    path("overview/", views.overview, name="expert-overview"),
    path("dialogue/", views.resolve_Disagreements, name="expert-dialogue"),
    path("dialogue/<int:codebook_id>/<int:example_id>/", views.ExpertDialogue.as_view(), name="expert-dialogue",   ),
]   