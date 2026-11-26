from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """One row only: the list goes straight to it, and it can be neither added nor deleted."""

    def changelist_view(self, request, extra_context=None):  # noqa: ARG002
        settings = SiteSettings.load()
        return redirect(reverse("admin:core_sitesettings_change", args=(settings.pk,)))

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False
