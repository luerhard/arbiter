from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications",
        on_delete=models.CASCADE,
    )
    batch = models.ForeignKey(
        "projects.Batch",
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user", "read_at"]),
        ]

    def __str__(self):
        return f"Notification for {self.user}: {self.message}"

    @classmethod
    def mark_batch_read(cls, user, batch_id):
        """The user opened the batch's annotation, discussion or expert page: its phase
        notifications have done their job, so their toasts stop coming back."""
        cls.objects.filter(user=user, batch_id=batch_id, read_at__isnull=True).update(
            read_at=timezone.now(),
        )

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])
