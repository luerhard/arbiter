from typing import Literal

from django.db import models

from projects.models import Batch
from projects.models import Project
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

    assignment = models.ForeignKey(
        "ExampleAssignment",
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
        return self.user_example.example

    class Meta:
        unique_together = ("assignment", "phase", "label")


class ExampleAssignment(models.Model):
    example = models.ForeignKey("Example", related_name="assignments", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="assignments", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(db_index=True)
    is_annotated = models.BooleanField(default=False)
    is_confirmed = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # auto set order for the first time
        if self.order is None:
            max_order = ExampleAssignment.objects.filter(
                user=self.user, example__batch=self.example.batch
            ).aggregate(max_order=models.Max("order"))["max_order"]

            # if there are no other entries
            self.order = (max_order or 0) + 1

        super().save(*args, **kwargs)


class Example(models.Model):
    batch = models.ForeignKey(Batch, related_name="examples", on_delete=models.CASCADE)
    content = models.TextField()

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

        if phase == Annotation.Phase.ANNOTATION:
            return Annotation.objects.filter(
                assignment__example=self,
                assignment__user=user,
                assignment__is_annotated=1,
                phase=phase,
            )
        elif phase == Annotation.Phase.DISCUSSION:
            return Annotation.objects.filter(
                assignment__example=self,
                assignment__user=user,
                assignment__is_discussed=1,
                phase=phase,
            )
        else:
            msg = "NOT IMPLMEEEEMENTEd"
            raise NotImplementedError(msg)

    def set_user_annotations(
        self,
        user,
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
        label_ids: list[int],
    ):
        assignment, _ = ExampleAssignment.objects.get_or_create(sentence=self, user=user)
        assignment.is_annotated = 1

        phase = getattr(Annotation.Phase, phase)

        Annotation.objects.filter(phase=phase, assignment=assignment).delete()

        updates = []
        for label in self.labels.all():
            if label.pk in label_ids:
                new = Annotation(assignment=assignment, label=label, phase=phase)
                updates.append(new)
        Annotation.objects.bulk_create(updates)
        assignment.save()
