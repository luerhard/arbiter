from django.db import models


class SiteSettings(models.Model):
    """Settings for the whole server, changed in the Django admin. There is only ever one
    row; load() returns it."""

    allow_registration = models.BooleanField(
        default=False,
        help_text=(
            "Anyone who can reach the server can create an account on the sign-in page. Like "
            "every user, they can then create projects and be added to others, but not open "
            "the admin."
        ),
    )

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
