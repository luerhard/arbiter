from django.urls import path

from . import views

urlpatterns = [
    path("<int:batch_id>", views.DiscussView.as_view(), name="discuss-batch"),
]

htmx_patterns = [
    # path("update-pbar/<int:batch_id>", views.GetProgress.as_view(), name="update-pbar"),
    path("htmx/pbar", views.HtmxPbar.as_view(), name="discuss-pbar"),
]

urlpatterns += htmx_patterns
