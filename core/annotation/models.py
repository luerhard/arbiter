from django.db import models

from core.models import Project
from users.models import User


class Label(models.Model):
    project = models.ForeignKey(Project, related_name="labels", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#007bff")  # Store color codes
    hotkey = models.CharField(max_length=1, null=True, blank=True)

    def __str__(self):
        return self.name


class UserAnnotation(models.Model):
    sentence = models.ForeignKey(
        "Sentence",
        related_name="user_annotations",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(User, related_name="user", on_delete=models.CASCADE)
    label = models.ForeignKey(
        Label,
        related_name="user_annotations",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    is_set = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("sentence", "user", "label")

    def __str__(self) -> str:
        return f"{self.user} - {self.label} - {self.is_set} - {self.last_updated}"


class UserConfirmedAnnotation(models.Model):
    sentence = models.ForeignKey(
        "Sentence",
        related_name="user_confirmed_annotations",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    label = models.ForeignKey(
        Label,
        related_name="user_confirmed_annotations",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    is_set = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("sentence", "user", "label")

    def __str__(self) -> str:
        return f"{self.user} - {self.label} - {self.is_set} - {self.last_updated}"


class Batch(models.Model):
    project = models.ForeignKey(Project, related_name="batches", on_delete=models.CASCADE)
    batch_number = models.SmallIntegerField()
    annotation_done = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Batch {self.batch_number}"

    def annotated_sentences(self, user):
        # Calculate the number of unique annotated sentences for the batch for the specific user
        return UserAnnotation.objects.filter(
            sentence__batch=self, 
            user=user 
        ).values('sentence').distinct().count()

class Sentence(models.Model):
    batch = models.ForeignKey(Batch, related_name="sentences", on_delete=models.CASCADE)
    content = models.TextField()
    has_disagreement_labels = models.BooleanField(default=None, null=True, blank=True)
    is_discussed = models.BooleanField(default=False)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.content

    def annotations(self, user):
        annotations = (
            UserAnnotation.objects.prefetch_related("label").filter(user=user, sentence=self).all()
        )
        return annotations
