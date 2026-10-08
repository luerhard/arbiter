from django.apps import AppConfig


class DiscussConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "discuss"

    def ready(self):
        from . import signals  # noqa: F401
