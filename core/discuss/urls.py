from django.urls import path

from . import views

urlpatterns = [
    path("<int:batch_id>", views.DiscussView.as_view(), name="discuss-batch"),
]
