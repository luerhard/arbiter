from django.db import models
from django.utils import timezone

from .models import Annotation
from projects.models import Batch
from projects.models import BatchAssignment


class ExampleAssignmentQuerySet(models.QuerySet):
    def done(self):
        return self.filter(done__isnull=False)


class ExampleAssignment(models.Model):
    objects = ExampleAssignmentQuerySet.as_manager()
    example = models.ForeignKey("Example", related_name="assignments", on_delete=models.CASCADE)
    batch_assignment = models.ForeignKey(
        BatchAssignment,
        related_name="examples_assignments",
        on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(db_index=True)
    done = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("example", "batch_assignment", "phase"),
                name="unique_example_batch_assignment",
            ),
        ]

    @property
    def phase(self):
        return self.batch_assignment.phase

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
            query = query.filter(done__isnull=True)

        return query.order_by("-order").first()

    def next(self, skip_annotated: bool = False):
        query = ExampleAssignment.objects.filter(
            example__batch=self.example.batch,
            batch_assignment=self.batch_assignment,
            order__gt=self.order,
        )

        if skip_annotated:
            query = query.filter(done__isnull=True)

        return query.order_by("order").first()

    def set_user_annotations(self, label_ids: list[int]):

        # delete previous annotations if any
        self.annotations.all().delete()

        # set new annotations
        updates = []
        for label in self.example.labels.all():
            if label.pk in label_ids:
                new = Annotation(assignment=self, label=label)
                updates.append(new)
        Annotation.objects.bulk_create(updates)
        self.done = timezone.now()
        self.save()

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
