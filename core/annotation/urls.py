from django.urls import path

from . import views

urlpatterns = [
    path("batch/<int:batch_id>", views.AnnotateView.as_view(), name="annotate-batch"),
]

htmx_patterns = [
    path("next/<int:assignment_id>", views.NextSentence.as_view(), name="annotate-next"),
    path("prev/<int:assignment_id>", views.PrevSentence.as_view(), name="annotate-prev"),
    path("example/edit/<int:assignment_id>", views.EditAssignment.as_view(), name="annotate-edit"),
]

urlpatterns += htmx_patterns
