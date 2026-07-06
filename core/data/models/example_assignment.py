from django.contrib.auth import get_user_model
from django.db import models
from django.db import transaction
from django.utils import timezone

from .models import Annotation
from projects.models import Batch
from projects.models import BatchPhase

User = get_user_model()


class ExampleAssignmentQuerySet(models.QuerySet):
    def done(self):
        return self.filter(done__isnull=False)

    def from_project(self, project):
        return self.filter(batch__project=project)


class ExampleAssignment(models.Model):
    objects = ExampleAssignmentQuerySet.as_manager()
    batch = models.ForeignKey(Batch, related_name="assignments", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    example = models.ForeignKey("Example", related_name="assignments", on_delete=models.CASCADE)
    phase = models.CharField(
        default=BatchPhase.SETUP,
        null=False,
        blank=False,
        max_length=1,
        choices=BatchPhase,
        db_index=True,
    )
    order = models.PositiveIntegerField(db_index=True)
    done = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "user", "phase", "example"),
                name="unique_example_assignment",
            ),
        ]

    def __str__(self):
        return f"id: {self.id}, user: {self.user.usernam}, ex: {self.example.id} done: {self.done}"

    def __repr__(self):
        return f"id: {self.id}, user: {self.user.username}, ex: {self.example.id} done: {self.done}"

    def previous(self, skip_annotated: bool = False):
        query = ExampleAssignment.objects.filter(
            batch=self.batch,
            user=self.user,
            phase=self.phase,
            order__lt=self.order,
        )

        if skip_annotated:
            query = query.filter(done__isnull=True)

        return query.order_by("-order").first()

    def next(self, skip_annotated: bool = False):
        query = ExampleAssignment.objects.filter(
            batch=self.batch,
            user=self.user,
            phase=self.phase,
            order__gt=self.order,
        )

        if skip_annotated:
            query = query.filter(done__isnull=True)

        return query.order_by("order").first()

    def set_user_annotations(self, label_ids: list[int]):
        # Atomic so a failure between delete and create can never wipe the
        # previously stored labels.
        with transaction.atomic():
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

    def get_user_annotations(self):
        return {annotation.label for annotation in self.annotations.all()}

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
