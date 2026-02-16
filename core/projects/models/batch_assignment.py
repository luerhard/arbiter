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

    def create_example_assignments(self):

        assignments = []
        for ex in self.examples.all():
            new = apps.get_model("ExampleAssignment")(
                example=ex,
                phase=Batch.Phase,
                batch_assignment=self,
            )
            assignments.append(new)
        apps.get_model("ExampleAssignment").objects.bulk_create(assignments)

    def get_disagreements_for_phase(self, phase):
        # check if all annotators that are assigned have disagreement in a specific phase.
        Example = apps.get_model("data", "Example")
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")

        annotator_ids = list(
            BatchAssignment.objects.filter(
                batch=self.batch,
                role=ProjectUser.Role.ANNOTATOR,
                phase=phase,
            ).values_list("user_id", flat=True),
        )
        if not annotator_ids:
            return Example.objects.none()

        assignments = (
            ExampleAssignment.objects.filter(
                example__batch=self.batch,
                batch_assignment__user_id__in=annotator_ids,
                batch_assignment__phase=phase,
            )
            .select_related("example", "batch_assignment")
            .prefetch_related("annotations")
        )

        by_example = defaultdict(dict)
        for assignment in assignments:
            label_ids = set(assignment.annotations.values_list("label_id", flat=True))
            if not label_ids:
                continue
            by_example[assignment.example_id][assignment.batch_assignment.user_id] = label_ids

        disagreements = []
        required_user_count = len(annotator_ids)
        for example_id, user_labels in by_example.items():
            if len(user_labels) != required_user_count:
                continue
            unique_label_sets = {frozenset(labels) for labels in user_labels.values()}
            if len(unique_label_sets) > 1:
                disagreements.append(example_id)

        return Example.objects.filter(id__in=disagreements)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "user", "phase"),
                name="unique_batch_user_phase",
            ),
        ]
