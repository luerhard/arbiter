from django.urls import path

from . import views

urlpatterns = [
    path("batch/<int:batch_id>", views.AnnotateView.as_view(), name="annotate-batch"),
    path(
        "batch/<int:batch_id>/assignment/<int:assignment_id>",
        views.AnnotateView.as_view(),
        name="annotate-assignment",
    ),
    path(
        "batch/<int:batch_id>/done",
        views.AnnotationDoneView.as_view(),
        name="annotate-done",
    ),
]

htmx_patterns = [
    # path("htmx/pbar", views.HtmxPbar.as_view(), name="annotate-pbar"),
    # path("htmx/labels", views.HtmxLabels.as_view(), name="annotate-labels"),
    # path("htmx/sentence", views.HtmxSentence.as_view(), name="annotate-sentence"),
    # path("htmx/nav-block", views.HtmxNavBlock.as_view(), name="annotate-nav-block"),
    # path("next/", views.NextSentence.as_view(), name="annotate-next"),
    # path("prev/", views.PrevSentence.as_view(), name="annotate-prev"),
    path("htmx/edit/", views.EditAssignment.as_view(), name="annotate-edit"),
]

urlpatterns += htmx_patterns
