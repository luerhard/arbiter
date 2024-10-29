from collections import defaultdict
from typing import Literal

from colorfield.fields import ColorField
from django.db import models

from projects.models import Batch
from projects.models import Project
from users.models import User


class Label(models.Model):
    project = models.ForeignKey(Project, related_name="labels", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = ColorField(max_length=7, default="#2c3e50")
    hotkey = models.CharField(max_length=1, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project", "name"), name="unique_label_name"),
            models.UniqueConstraint(fields=("project", "hotkey"), name="unique_hotkey"),
        ]


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
    is_discussed = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    def previous(self):
        return (
            ExampleAssignment.objects.filter(
                example__batch=self.example.batch,
                user=self.user,
                order__lt=self.order,
            )
            .order_by("-order")
            .first()
        )

    def next(self):
        return (
            ExampleAssignment.objects.filter(
                example__batch=self.example.batch,
                user=self.user,
                order__gt=self.order,
            )
            .order_by("order")
            .first()
        )

    def set_user_annotations(
        self,
        label_ids: list[int],
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
    ):
        phase = getattr(Annotation.Phase, phase)
        self.is_annotated = 1

        # delete previous annotations if any
        Annotation.objects.filter(phase=phase, assignment=self).delete()

        # set new annotations
        updates = []
        for label in self.example.labels.all():
            if label.pk in label_ids:
                new = Annotation(assignment=self, label=label, phase=phase)
                updates.append(new)
        Annotation.objects.bulk_create(updates)
        self.save()

        # check for disagreement during annotation phase
        if phase == Annotation.Phase.ANNOTATION:
            self.check_for_disagreement()

    def check_for_disagreement(self):
        # Get annotations for anntation phase
        assignments = ExampleAssignment.objects.filter(
            example=self.example,
            is_annotated=True,
            annotations__phase=Annotation.Phase.ANNOTATION,
        ).prefetch_related("annotations__label", "user")

        # group by user
        user_annotations = defaultdict(set)
        for assignment in assignments:
            for annotation in assignment.annotations.all():
                user_annotations[assignment.user.id].add(annotation.label.id)

        unique_annotations = {frozenset(labels) for labels in user_annotations.values()}

        if len(unique_annotations) > 1:
            self.example.has_disagreement = True
        else:
            self.example.has_disagreement = False

        self.example.save()

    def save(self, *args, **kwargs):
        # auto set order for the first time
        if self.order is None:
            max_order = ExampleAssignment.objects.filter(
                user=self.user,
                example__batch=self.example.batch,
            ).aggregate(max_order=models.Max("order"))["max_order"]

            # if there are no other entries
            self.order = (max_order or 0) + 1

        super().save(*args, **kwargs)


class Example(models.Model):
    batch = models.ForeignKey(Batch, related_name="examples", on_delete=models.CASCADE)
    content = models.TextField()
    has_disagreement = models.BooleanField(default=False)

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
        label_ids: list[int],
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
    ):
        assignment = ExampleAssignment.objects.get(example=self, user=user)
        assignment.set_user_annotations(label_ids=label_ids, phase=phase)
