from typing import Literal

from django.db import models

from core.models import Batch
from core.models import Project
from users.models import User


class Label(models.Model):
    project = models.ForeignKey(Project, related_name="labels", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#007bff")  # Store color codes
    hotkey = models.CharField(max_length=1, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("project", "name")


class Annotation(models.Model):
    class Phase(models.TextChoices):
        ANNOTATION = "A", "Annotation"
        DISCUSSION = "D", "Discussion"
        EXPERT = "E", "ExpertDecision"

    user_sentence = models.ForeignKey(
        "UserSentence",
        related_name="annotations",
        on_delete=models.CASCADE,
    )
    label = models.ForeignKey(
        Label,
        related_name="label",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    phase = models.CharField(max_length=1, choices=Phase, db_index=True)

    @property
    def sentence(self):
        return self.user_sentence.sentence

    class Meta:
        unique_together = ("user_sentence", "phase", "label")


class UserSentence(models.Model):
    sentence = models.ForeignKey(
        "Sentence",
        related_name="user_sentence",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(User, related_name="user", on_delete=models.CASCADE)
    is_annotated = models.BooleanField(default=False)
    is_confirmed = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("sentence", "user")

    def __str__(self) -> str:
        return f"{self.user} - {self.sentence.id} - {self.is_annotated} - {self.is_confirmed}"

    def annotated_sentences(self, user):
        # Calculate the number of unique annotated sentences for the batch for the specific user
        return (
            UserSentence.objects.filter(sentence__batch=self, user=user)
            .values("sentence")
            .distinct()
            .count()
        )


class Sentence(models.Model):
    batch = models.ForeignKey(Batch, related_name="sentences", on_delete=models.CASCADE)
    content = models.TextField()
    # has_disagreement_labels = models.BooleanField(default=None, null=True, blank=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.content

    @property
    def project(self):
        return self.batch.project

    @property
    def labels(self):
        return self.batch.project.labels

    def get_user_annotations(self, user, phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"]):
        phase = getattr(Annotation.Phase, phase)
        return Annotation.objects.filter(
            user_sentence__sentence=self,
            user_sentence__user=user,
            user_sentence__is_annotated=1,
            phase=phase,
        )

    def set_user_annotations(
        self,
        user,
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
        label_ids: list[int],
    ):
        user_sentence, _ = UserSentence.objects.get_or_create(sentence=self, user=user)
        user_sentence.is_annotated = 1

        phase = getattr(Annotation.Phase, phase)

        Annotation.objects.filter(phase=phase, user_sentence=user_sentence).delete()

        updates = []
        for label in self.labels.all():
            if label.pk in label_ids:
                new = Annotation(user_sentence=user_sentence, label=label, phase=phase)
                updates.append(new)
        Annotation.objects.bulk_create(updates)
        user_sentence.save()
