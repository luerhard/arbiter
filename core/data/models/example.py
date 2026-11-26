from django.db import models

from .example_assignment import ExampleAssignment
from .models import Annotation
from projects.models import Batch
from projects.models import BatchPhase


class Example(models.Model):
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

    def shown_metadata(self) -> dict:
        """The metadata as annotation, discussion and expert decision show it below the text:
        all of it if the project shows metadata, else nothing."""
        return self.metadata if self.batch.project.show_metadata_in_annotation else {}

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
