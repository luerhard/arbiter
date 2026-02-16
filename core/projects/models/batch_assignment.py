from collections import defaultdict

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models

from .batch import Batch
from .project_user import ProjectUser

User = get_user_model()


class BatchAssignment(models.Model):
    batch = models.ForeignKey(Batch, related_name="batch_assignments", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="batch_assignments", on_delete=models.CASCADE)
    role = models.CharField(max_length=1, choices=ProjectUser.Role, blank=False)

    phase = models.CharField(
        default=Batch.Phase.SETUP,
        null=False,
        blank=False,
        max_length=1,
        choices=Batch.Phase,
        db_index=True,
    )

    def _create_example_assignments(self):
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")

        assignments = []
        for ex in self.batch.examples.all():
            new = ExampleAssignment(example=ex, batch_assignment=self)
            assignments.append(new)

        ExampleAssignment.objects.bulk_create(
            assignments,
            update_conflicts=True,
            unique_fields=("example", "batch_assignment"),
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "user", "phase"),
                name="unique_batch_user_phase",
            ),
        ]
