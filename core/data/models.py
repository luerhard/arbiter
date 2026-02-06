from collections import defaultdict
from typing import Literal

from colorfield.fields import ColorField
from django.db import models

from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import Project


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
    batch_assignment = models.ForeignKey(
        BatchAssignment,
        related_name="examples_assignments",
        on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(db_index=True)
    is_annotated = models.BooleanField(default=False)
    is_discussed = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("example", "batch_assignment"),
                name="unique_example_batch_assignment",
            ),
        ]

    @property
    def user(self):
        return self.batch_assignment.user

    def previous(self, skip_annotated: bool = False):
        query = ExampleAssignment.objects.filter(
            example__batch=self.example.batch,
            batch_assignment=self.batch_assignment,
            order__lt=self.order,
        )

        if skip_annotated:
            query = query.filter(is_annotated=False)

        return query.order_by("-order").first()

    def next(self, skip_annotated: bool = False):
        query = ExampleAssignment.objects.filter(
            example__batch=self.example.batch,
            batch_assignment=self.batch_assignment,
            order__gt=self.order,
        )

        if skip_annotated:
            query = query.filter(is_annotated=False)

        return query.order_by("order").first()

    def set_user_annotations(
        self,
        label_ids: list[int],
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
    ):
        phase = getattr(Annotation.Phase, phase)
        if phase == Annotation.Phase.ANNOTATION:
            self.is_annotated = True
        elif phase == Annotation.Phase.DISCUSSION:
            self.is_discussed = True

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
        elif phase == Annotation.Phase.DISCUSSION:
            self.check_for_disagreement_after_discussion()

    def check_for_disagreement(self):
        return self.example.has_disagreement

    def check_for_disagreement_after_discussion(self):
        return self.example.has_disagreement_after_discussion

    def save(self, *args, **kwargs):
        # auto set order for the first time
        if self.order is None:
            max_order = ExampleAssignment.objects.filter(
                batch_assignment=self.batch_assignment,
                example__batch=self.example.batch,
            ).aggregate(max_order=models.Max("order"))["max_order"]

            # if there are no other entries
            self.order = (max_order or 0) + 1

        super().save(*args, **kwargs)


class Example(models.Model):
    batch = models.ForeignKey(Batch, related_name="examples", on_delete=models.CASCADE)
    content = models.TextField()

    assignees = models.ManyToManyField(
        BatchAssignment,
        through=ExampleAssignment,
        related_name="examples",
    )

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.content

    @property
    def labels(self):
        return self.batch.project.labels

    def _has_disagreement_for_phase(self, phase: str) -> bool:
        if phase == Annotation.Phase.ANNOTATION:
            assignment_filter = {"assignment__is_annotated": True}
        elif phase == Annotation.Phase.DISCUSSION:
            assignment_filter = {"assignment__is_discussed": True}
        else:
            assignment_filter = {}

        rows = (
            Annotation.objects.filter(
                assignment__example=self,
                phase=phase,
                **assignment_filter,
            )
            .values(
                "assignment__batch_assignment__user_id",
                "label_id",
            )
            .order_by()
        )

        by_user = defaultdict(set)
        for row in rows:
            by_user[row["assignment__batch_assignment__user_id"]].add(row["label_id"])

        unique_label_sets = {frozenset(labels) for labels in by_user.values()}
        return len(unique_label_sets) > 1

    @property
    def has_expert_decision(self) -> bool:
        return Annotation.objects.filter(
            assignment__example=self,
            phase=Annotation.Phase.EXPERT,
        ).exists()

    @property
    def has_disagreement(self) -> bool:
        return self._has_disagreement_for_phase(Annotation.Phase.ANNOTATION)

    @property
    def has_disagreement_after_discussion(self) -> bool:
        return self._has_disagreement_for_phase(Annotation.Phase.DISCUSSION)

    def get_user_annotations(self, phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"], user=None):
        phase = getattr(Annotation.Phase, phase)

        if phase == Annotation.Phase.ANNOTATION:
            return Annotation.objects.filter(
                assignment__example=self,
                assignment__batch_assignment__user=user,
                assignment__is_annotated=1,
                phase=phase,
            )
        elif phase == Annotation.Phase.DISCUSSION:
            return Annotation.objects.filter(
                assignment__example=self,
                assignment__batch_assignment__user=user,
                assignment__is_discussed=1,
                phase=phase,
            )
        else:
            return Annotation.objects.filter(
                assignment__example=self,
                phase=phase,
            )

    def set_user_annotations(
        self,
        user,
        label_ids: list[int],
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
    ):
        assignment = ExampleAssignment.objects.get(example=self, batch_assignment__user=user)
        assignment.set_user_annotations(label_ids=label_ids, phase=phase)
