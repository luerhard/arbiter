from django.urls import path

from . import views

urlpatterns = [
    path("unread", views.UnreadNotificationsView.as_view(), name="notifications-unread"),
    path(
        "<int:notification_id>/read",
        views.MarkNotificationReadView.as_view(),
        name="notification-read",
    ),
]
