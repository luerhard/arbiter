from collections import defaultdict
from collections.abc import Mapping
from typing import TYPE_CHECKING

from django.apps import apps
from django.db import models

from .project_user import ProjectUser

if TYPE_CHECKING:
    User = apps.get_model("users", "User")


class BatchQuerySet(models.QuerySet):
    def example_assignments(self, user, phase):
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")
        return ExampleAssignment.objects.filter(
            batch_assignment__batch__in=self,
            batch_assignment__user=user,
            batch_assignment__phase=phase,
        )


class Batch(models.Model):
    class Phase(models.TextChoices):
        SETUP = "S", "Setup"
        ANNOTATION = "A", "Annotation"
        DISCUSSION = "D", "Discussion"
        EXPERT = "E", "ExpertDecision"
        FINAL = "F", "Finalized"

    objects = BatchQuerySet.as_manager()
    project = models.ForeignKey("Project", related_name="batches", on_delete=models.CASCADE)
    batch_number = models.SmallIntegerField()
    current_phase = models.CharField(
        default=Phase.SETUP,
        null=False,
        blank=False,
        max_length=1,
        choices=Phase,
        db_index=True,
    )

    def __str__(self) -> str:
        return f"Batch {self.batch_number}"

    @property
    def labels(self):
        return self.project.labels

    @property
    def max_batch_number(self):
        max_batch_number = (
            Batch.objects
            .filter(project=self.project)
            .aggregate(models.Max("batch_number"))
            .get("batch_number__max", 0)
        )
        if max_batch_number:
            return max_batch_number
        return 0

    def save(self, **kwargs):
        if self._state.adding is True:
            self.batch_number = self.max_batch_number + 1
        super().save(**kwargs)

    def assignees(self, role):
        User = apps.get_model("users", "User")
        return User.objects.filter(
            batch_assignments__batch=self,
            batch_assignments__role=role,
        ).distinct()

    def disagreements(self, phase):
        Example = apps.get_model("data", "Example")
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")

        annotators = self.assignees(role=ProjectUser.Role.ANNOTATOR).all()

        if not annotators:
            return Example.objects.none()

        assignments = (
            ExampleAssignment.objects
            .filter(
                example__batch=self,
                batch_assignment__user__in=annotators,
                batch_assignment__phase=phase,
            )
            .select_related("example", "batch_assignment")
            .prefetch_related("annotations")
        )

        by_example = defaultdict(dict)
        for assignment in assignments:
            label_ids = [annotation.label_id for annotation in assignment.annotations.all()]
            if not label_ids:
                continue
            by_example[assignment.example_id][assignment.batch_assignment.user_id] = label_ids

        disagreements = []
        required_user_count = len(annotators)
        for example_id, user_labels in by_example.items():
            if len(user_labels) != required_user_count:
                continue
            unique_label_sets = {frozenset(labels) for labels in user_labels.values()}
            if len(unique_label_sets) > 1:
                disagreements.append(example_id)

        return Example.objects.filter(id__in=disagreements)

    def set_phase(
        self,
        phase: Phase,
        user_role_mapping: Mapping["User", ProjectUser.Role] | None = None,
    ):
        self.current_phase = phase

        if self.current_phase == Batch.Phase.ANNOTATION:
            codebook = self.project.codebook.get()
            codebook.tag_version(self.batch_number)

        self._create_batch_assignments(phase=phase, user_role_mapping=user_role_mapping)
        self._create_example_assignments(phase=phase)
        self.save()

    def _create_batch_assignments(
        self,
        phase: Phase,
        user_role_mapping: Mapping["User", ProjectUser.Role] | None = None,
    ):
        BatchAssignment = apps.get_model("projects", "BatchAssignment")

        if phase in (Batch.Phase.ANNOTATION, Batch.Phase.DISCUSSION):
            active_role = ProjectUser.Role.ANNOTATOR
        elif phase == Batch.Phase.EXPERT:
            active_role = ProjectUser.Role.EXPERT
        else:
            return

        if not user_role_mapping:
            users = [
                u.user for u in self.project.project_users.filter(default_role=active_role).all()
            ]
        else:
            users = [u for u, role in user_role_mapping.items() if role == active_role]

        batch_assignments = []
        for user in users:
            batch_assignment = BatchAssignment(
                batch=self,
                user=user,
                role=active_role,
                phase=phase,
            )
            batch_assignments.append(batch_assignment)

        BatchAssignment.objects.bulk_create(
            batch_assignments,
            update_conflicts=True,
            update_fields=["role"],
            unique_fields=("batch", "user", "phase"),
        )

    def _create_example_assignments(self, phase: Phase):
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")

        if phase == Batch.Phase.ANNOTATION:
            examples = self.examples.all()
        elif phase == Batch.Phase.DISCUSSION:
            examples = self.disagreements(phase=Batch.Phase.ANNOTATION)
        elif phase == Batch.Phase.EXPERT:
            examples = self.disagreements(phase=Batch.Phase.DISCUSSION)
        else:
            return

        batch_assignments = self.batch_assignments.filter(phase=phase).all()

        example_assignments = []
        for ba in batch_assignments:
            for i, ex in enumerate(examples, 1):
                ea = ExampleAssignment(
                    example=ex,
                    batch_assignment=ba,
                    order=i,
                )
                example_assignments.append(ea)
        ExampleAssignment.objects.bulk_create(example_assignments, ignore_conflicts=True)
