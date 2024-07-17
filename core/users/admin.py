from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as OrigUserAdmin

from .forms import UserChangeForm
from .forms import UserCreationForm
from .models import User


# Register your models here.

class UserAdmin(OrigUserAdmin):
    model = User
    add_form = UserCreationForm
    form = UserChangeForm

    list_display = (
        "username",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "username",
        "is_staff",
        "is_active",
    )

    fieldsets = (
        (None, {"fields": ("username",)}),
        ("Permissions", {"fields": ("is_staff", "is_active", "groups", "user_permissions")}),
    )


    search_fields = (
        "username",
    )

    ordering = (
        "is_superuser",
        "is_staff",
        "username",
    )

admin.site.register(User, UserAdmin)
