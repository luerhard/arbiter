from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.generic import View

from .models import Notification


class UnreadNotificationsView(LoginRequiredMixin, View):
    def get(self, request):
        notifications = request.user.notifications.filter(read_at__isnull=True).select_related(
            "batch"
        )
        return render(
            request,
            "notifications/partials/unread.html",
            {"notifications": notifications},
        )


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
        notification.mark_read()
        # Empty 200 lets the htmx close button remove the toast (hx-swap="delete").
        return HttpResponse(status=200)
