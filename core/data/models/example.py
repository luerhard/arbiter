from collections import defaultdict

from django.db import models

from .example_assignment import ExampleAssignment
from .models import Annotation
from projects.models import Batch
from projects.models import BatchPhase


class ExampleQuerySet(models.QuerySet):
    def disagreements(self, phase):
        if isinstance(phase, str) and len(phase) > 1:
            phase = getattr(BatchPhase, phase)

        example_ids = list(self.values_list("id", flat=True))
        if not example_ids:
            return self.none()

        assignments = ExampleAssignment.objects.filter(
            example_id__in=example_ids,
            phase=phase,
        ).prefetch_related("annotations")

        expected_users = defaultdict(set)
        labels_by_example = defaultdict(dict)
        for assignment in assignments:
            user_id = assignment.user.id
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
    # the other columns of the uploaded file, by column name; exported next to the labels
    metadata = models.JSONField(default=dict, blank=True)
    # order within the batch (experts can rearrange it); every phase hands out the
    # examples in this order, see Batch._create_example_assignments
    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.content

    @property
    def labels(self):
        return self.batch.project.labels

    @property
    def has_disagreement(self) -> bool:
        return (
            Example.objects.filter(id=self.id).disagreements(phase=BatchPhase.ANNOTATION).exists()
        )

    @property
    def has_disagreement_after_discussion(self) -> bool:
        return (
            Example.objects.filter(id=self.id).disagreements(phase=BatchPhase.DISCUSSION).exists()
        )

    @property
    def has_expert_decision(self) -> bool:
        return ExampleAssignment.objects.filter(
            example=self,
            phase=BatchPhase.EXPERT,
            done__isnull=False,
        ).exists()

    def labels_by_user(self, phase: BatchPhase) -> dict:
        """Who labeled this example how in one phase: username -> list of annotations,
        or None if the person has not labeled it yet."""
        assignments = (
            self.assignments.filter(phase=phase)
            .select_related("user")
            .prefetch_related("annotations__label")
            .order_by("user__username")
        )
        return {a.user.username: list(a.annotations.all()) if a.done else None for a in assignments}

    def get_user_annotations(self, phase: BatchPhase, user=None):
        qs = Annotation.objects.filter(assignment__example=self, assignment__phase=phase)
        if user is not None:
            qs = qs.filter(assignment__user=user)
        return qs
