from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View

from .models import Notification

# More toasts would cover the page and its buttons; the rest is counted below them.
SHOWN = 3
# Tells the poller to reload the toasts right away (see base.html).
CHANGED = {"HX-Trigger": "notifications-changed"}


class UnreadNotificationsView(LoginRequiredMixin, View):
    def get(self, request):
        unread = request.user.notifications.filter(read_at__isnull=True)
        notifications = list(unread.select_related("batch").order_by("-created_at")[:SHOWN])
        return render(
            request,
            "notifications/partials/unread.html",
            {"notifications": notifications, "more": unread.count() - len(notifications)},
        )


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
        notification.mark_read()
        # "Open project" posts with the page to go to next.
        next_url = request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
            return HttpResponseRedirect(next_url)
        # Empty 200 lets the htmx close button remove the toast (hx-swap="delete"); the
        # poller then shows the next one.
        return HttpResponse(status=200, headers=CHANGED)


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
        return HttpResponse(status=200, headers=CHANGED)
