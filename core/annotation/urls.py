from django.urls import path

from . import views

urlpatterns = [
    path("batch/<int:batch_id>", views.AnnotateView.as_view(), name="annotate-batch"),
]

htmx_patterns = [
    path("next/", views.NextSentence.as_view(), name="annotate-next"),
    path("reload/", views.ReloadSentence.as_view(), name="annotate-reload"),
    path("prev/", views.PrevSentence.as_view(), name="annotate-prev"),
    path("example/edit/<int:assignment_id>", views.EditAssignment.as_view(), name="annotate-edit"),
]

urlpatterns += htmx_patterns
