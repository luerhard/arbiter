from collections import defaultdict
from typing import Literal

from django.db import models

from .example_assignment import ExampleAssignment
from .models import Annotation
from projects.models import Batch
from projects.models import BatchAssignment


class ExampleQuerySet(models.QuerySet):
    def disagreements(self, phase):
        if isinstance(phase, str) and len(phase) > 1:
            phase = getattr(Batch.Phase, phase)

        example_ids = list(self.values_list("id", flat=True))
        if not example_ids:
            return self.none()

        assignments = (
            ExampleAssignment.objects
            .filter(
                example_id__in=example_ids,
                phase=phase,
            )
            .select_related("example", "batch_assignment")
            .prefetch_related("annotations")
        )

        expected_users = defaultdict(set)
        labels_by_example = defaultdict(dict)
        for assignment in assignments:
            user_id = assignment.batch_assignment.user_id
            expected_users[assignment.example_id].add(user_id)
            label_ids = set(assignment.annotations.values_list("label_id", flat=True))
            if label_ids:
                labels_by_example[assignment.example_id][user_id] = label_ids

        disagreements = []
        for example_id, users in expected_users.items():
            if len(users) <= 1:
                continue
            user_labels = labels_by_example.get(example_id, {})
            if len(user_labels) != len(users):
                continue
            unique_label_sets = {frozenset(labels) for labels in user_labels.values()}
            if len(unique_label_sets) > 1:
                disagreements.append(example_id)

        return self.filter(id__in=disagreements)


class Example(models.Model):
    objects = ExampleQuerySet.as_manager()
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

    @property
    def has_disagreement(self):
        return (
            Example.objects.filter(id=self.id).disagreements(phase=Batch.Phase.ANNOTATION).exists()
        )

    @property
    def has_disagreement_after_discussion(self):
        return (
            Example.objects.filter(id=self.id).disagreements(phase=Batch.Phase.DISCUSSION).exists()
        )

    @property
    def has_expert_decision(self):
        return Annotation.objects.filter(
            assignment__example=self,
            assignment__phase=Batch.Phase.EXPERT,
        ).exists()

    def get_user_annotations(self, phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"], user=None):
        phase = getattr(Batch.Phase, phase)

        qs = Annotation.objects.filter(
            assignment__example=self,
            assignment__phase=phase,
        )
        if user is not None:
            qs = qs.filter(assignment__batch_assignment__user=user)
        return qs

    def set_user_annotations(
        self,
        user,
        label_ids: list[int],
        phase: Literal["ANNOTATION", "DISCUSSION", "EXPERT"],
    ):
        assignment = ExampleAssignment.objects.get(
            example=self,
            batch_assignment__user=user,
            phase=getattr(Batch.Phase, phase),
        )
        assignment.set_user_annotations(label_ids=label_ids)
