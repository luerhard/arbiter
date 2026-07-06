from collections import defaultdict

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models

from .project_user import ProjectRole

User = get_user_model()


class BatchPhase(models.TextChoices):
    SETUP = "S", "Setup"
    ANNOTATION = "A", "Annotation"
    DISCUSSION = "D", "Discussion"
    EXPERT = "E", "ExpertDecision"
    FINAL = "F", "Finalized"


class BatchQuerySet(models.QuerySet):
    def assignments(self, user, phase):
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")
        return ExampleAssignment.objects.filter(batch__in=self, user=user, phase=phase)


class BatchUser(models.Model):
    batch = models.ForeignKey("Batch", on_delete=models.CASCADE, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    role = models.CharField(
        default=ProjectRole.ANNOTATOR,
        null=False,
        blank=False,
        max_length=1,
        choices=ProjectRole,
        db_index=True,
    )
    finalized_at = models.DateTimeField(null=True, blank=True)


class Batch(models.Model):
    objects = BatchQuerySet.as_manager()
    project = models.ForeignKey("Project", related_name="batches", on_delete=models.CASCADE)
    users = models.ManyToManyField(User, through="BatchUser")
    batch_number = models.SmallIntegerField()
    current_phase = models.CharField(
        default=BatchPhase.SETUP,
        null=False,
        blank=False,
        max_length=1,
        choices=BatchPhase,
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
            Batch.objects.filter(project=self.project)
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
        return self.users.filter(batchuser__role=role).distinct()

    def disagreements(self, phase):
        Example = apps.get_model("data", "Example")
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")

        annotators = self.assignees(role=ProjectRole.ANNOTATOR).all()

        if not annotators:
            return Example.objects.none()

        assignments = ExampleAssignment.objects.filter(
            batch=self,
            phase=phase,
        ).prefetch_related("annotations")

        by_example = defaultdict(dict)
        for assignment in assignments:
            label_ids = [annotation.label_id for annotation in assignment.annotations.all()]
            by_example[assignment.example_id][assignment.user_id] = label_ids

        disagreements = []
        required_user_count = len(annotators)
        for example_id, user_labels in by_example.items():
            if len(user_labels) != required_user_count:
                continue
            unique_label_sets = {frozenset(labels) for labels in user_labels.values()}
            if len(unique_label_sets) > 1:
                disagreements.append(example_id)

        return Example.objects.filter(id__in=disagreements)

    def all_annotators_finalized(self) -> bool:
        """True if every annotator has confirmed they are done annotating."""
        annotators = BatchUser.objects.filter(batch=self, role=ProjectRole.ANNOTATOR)
        if not annotators.exists():
            return False
        return not annotators.filter(finalized_at__isnull=True).exists()

    def advance_from_annotation_if_finalized(self) -> "BatchPhase | None":
        """Advance the batch once all annotators have finalized.

        -> DISCUSSION when disagreements exist, otherwise straight to FINAL
        (no discussion or expert decisions needed) and the next batch starts.
        Returns the new phase, or None if nothing changed.
        """
        if self.current_phase != BatchPhase.ANNOTATION:
            return None
        if not self.all_annotators_finalized():
            return None

        next_phase = (
            BatchPhase.DISCUSSION
            if self.disagreements(BatchPhase.ANNOTATION).exists()
            else BatchPhase.FINAL
        )
        self.set_phase(next_phase)
        if next_phase == BatchPhase.FINAL:
            self.start_next_setup_batch()
        return next_phase

    def advance_from_discussion(self) -> "BatchPhase | None":
        """Advance the batch once the discussion has ended.

        -> EXPERT when disagreements remain after discussion, otherwise FINAL
        (no expert decisions needed) and the next batch starts.
        Returns the new phase, or None if nothing changed.
        """
        if self.current_phase != BatchPhase.DISCUSSION:
            return None

        next_phase = (
            BatchPhase.EXPERT
            if self.disagreements(BatchPhase.DISCUSSION).exists()
            else BatchPhase.FINAL
        )
        self.set_phase(next_phase)
        if next_phase == BatchPhase.FINAL:
            self.start_next_setup_batch()
        return next_phase

    def start_next_setup_batch(self) -> "Batch | None":
        """Move the project's next SETUP batch (lowest batch number) into
        ANNOTATION. Batches without examples are not started."""
        next_batch = (
            Batch.objects.filter(
                project=self.project,
                current_phase=BatchPhase.SETUP,
                examples__isnull=False,
            )
            .order_by("batch_number")
            .first()
        )
        if next_batch is None:
            return None
        next_batch.set_phase(BatchPhase.ANNOTATION)
        return next_batch

    def set_phase(self, phase: BatchPhase):
        self.current_phase = phase

        if self.current_phase == BatchPhase.ANNOTATION:
            codebook = self.project.codebook.get()
            codebook.tag_version(self.batch_number)

        self._create_example_assignments(phase=phase)
        self.save()

    def _create_example_assignments(self, phase: BatchPhase):
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")

        if phase == BatchPhase.ANNOTATION:
            examples = self.examples.all()
            users = self.assignees(role=ProjectRole.ANNOTATOR)
        elif phase == BatchPhase.DISCUSSION:
            examples = self.disagreements(phase=BatchPhase.ANNOTATION)
            users = self.assignees(role=ProjectRole.ANNOTATOR)
        elif phase == BatchPhase.EXPERT:
            examples = self.disagreements(phase=BatchPhase.DISCUSSION)
            users = self.assignees(role=ProjectRole.EXPERT)
        else:
            return

        assignments = []
        for i, ex in enumerate(examples, 1):
            for user in users:
                ea = ExampleAssignment(
                    batch=self,
                    example=ex,
                    user=user,
                    phase=phase,
                    order=i,
                )
                assignments.append(ea)
        ExampleAssignment.objects.bulk_create(assignments, ignore_conflicts=True)
