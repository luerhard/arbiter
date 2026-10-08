from collections import defaultdict

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django.db import transaction

from .project_user import ProjectRole

User = get_user_model()


class BatchPhase(models.TextChoices):
    SETUP = "S", "Setup"
    ANNOTATION = "A", "Annotation"
    DISCUSSION = "D", "Discussion"
    EXPERT = "E", "Expert decision"
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
        """The examples the annotators have not agreed on in this phase: different labels, or
        someone has not saved theirs yet. Normally everyone has saved before the batch moves
        on; when an expert moves it on by hand earlier, a missing label must not count as
        "no labels", which would turn it into an agreement nobody made."""
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
        unsaved = set()
        for assignment in assignments:
            label_ids = [annotation.label_id for annotation in assignment.annotations.all()]
            by_example[assignment.example_id][assignment.user_id] = label_ids
            if assignment.done is None:
                unsaved.add(assignment.example_id)

        disagreements = []
        required_user_count = len(annotators)
        for example_id, user_labels in by_example.items():
            if len(user_labels) != required_user_count:
                continue
            unique_label_sets = {frozenset(labels) for labels in user_labels.values()}
            if len(unique_label_sets) > 1 or example_id in unsaved:
                disagreements.append(example_id)

        return Example.objects.filter(id__in=disagreements)

    def discussion_examples(self):
        """The examples to discuss, in batch order: the disagreements as they were when
        the batch entered the discussion, i.e. the examples with DISCUSSION assignments.
        Unlike disagreements(), this does not change when labels change afterwards."""
        Example = apps.get_model("data", "Example")  # noqa: N806
        return Example.objects.filter(
            assignments__batch=self,
            assignments__phase=BatchPhase.DISCUSSION,
        ).distinct()

    def open_discussion_examples(self):
        """Discussion examples where not every annotator has saved a decision yet."""
        return self.discussion_examples().filter(
            assignments__batch=self,
            assignments__phase=BatchPhase.DISCUSSION,
            assignments__done__isnull=True,
        )

    @property
    def can_reorder(self) -> bool:
        """The order can change until the discussion starts; afterwards it is part of the record."""
        return self.current_phase in (BatchPhase.SETUP, BatchPhase.ANNOTATION)

    def set_example_order(self, example_ids: list[int]) -> None:
        """Put the examples in this order. Annotators get them in it right away, and every
        later phase follows it (see _create_example_assignments)."""
        Example = apps.get_model("data", "Example")  # noqa: N806
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")  # noqa: N806

        examples = {example.id: example for example in self.examples.all()}
        if sorted(example_ids) != sorted(examples):
            msg = "The new order must contain every example of the batch exactly once."
            raise ValueError(msg)

        with transaction.atomic():
            for position, example_id in enumerate(example_ids, start=1):
                examples[example_id].position = position
            Example.objects.bulk_update(examples.values(), ["position"])

            assignments = list(
                ExampleAssignment.objects.filter(batch=self, phase=BatchPhase.ANNOTATION),
            )
            for assignment in assignments:
                assignment.order = examples[assignment.example_id].position
            ExampleAssignment.objects.bulk_update(assignments, ["order"])

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
        """Move the project's next SETUP batch into ANNOTATION.

        Only batches AFTER this one are considered (skipped earlier batches
        stay untouched), only in SETUP phase, and only with examples."""
        next_batch = (
            Batch.objects.filter(
                project=self.project,
                current_phase=BatchPhase.SETUP,
                batch_number__gt=self.batch_number,
                examples__isnull=False,
            )
            .order_by("batch_number")
            .first()
        )
        if next_batch is None:
            return None
        next_batch.set_phase(BatchPhase.ANNOTATION)
        return next_batch

    def set_phase(self, phase: BatchPhase, actor=None):
        # Read the old phase from the DB: bound ModelForms (ChangeBatchPhase)
        # mutate the in-memory instance during validation, which would make
        # the phase-change detection below always see "no change".
        old_phase = Batch.objects.filter(pk=self.pk).values_list("current_phase", flat=True).first()
        self.current_phase = phase

        if self.current_phase == BatchPhase.ANNOTATION:
            codebook = self.project.codebook.get()
            codebook.tag_version(self.batch_number)

        self._create_example_assignments(phase=phase)
        self.save()

        if old_phase != phase:
            self._reset_phase(phase)
            if old_phase == BatchPhase.DISCUSSION:
                from discuss import room_state  # noqa: PLC0415

                # open discussion pages show that the room is closed
                batch_id = self.pk
                transaction.on_commit(lambda: room_state.close_room(batch_id, phase))
            self._notify_phase_change(phase, actor=actor)

    def _reset_phase(self, phase: BatchPhase):
        """Entering a phase, also again after it was moved back by hand, starts it from a
        clean state. Nothing anyone entered is deleted: labels, decisions, drafts stay."""
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")  # noqa: N806

        if phase == BatchPhase.ANNOTATION:
            # Finalized annotators can not change their labels, and only finalizing
            # advances the batch: everyone finalizes again, their labels are kept.
            BatchUser.objects.filter(batch=self, role=ProjectRole.ANNOTATOR).update(
                finalized_at=None,
            )
            return

        if phase == BatchPhase.DISCUSSION:
            from discuss import room_state  # noqa: PLC0415

            # a fresh room: one whose discussion had ended would never start again
            batch_id = self.pk
            transaction.on_commit(lambda: room_state.delete_state(batch_id))
            disagreements = self.disagreements(BatchPhase.ANNOTATION)
        elif phase == BatchPhase.EXPERT:
            disagreements = self.disagreements(BatchPhase.DISCUSSION)
        else:
            return

        # undecided assignments of examples that are no longer disagreements
        ExampleAssignment.objects.filter(
            batch=self,
            phase=phase,
            done__isnull=True,
            annotations__isnull=True,
            codebook_draft__isnull=True,
        ).exclude(example__in=disagreements).delete()

    def _notify_phase_change(self, phase: BatchPhase, actor=None):
        """Create an unread notification for every batch user; the polling UI
        shows them as persistent toasts until marked as read.

        `actor` is the user who deliberately triggered the change (manual
        phase form). They get immediate feedback via a django message
        instead, so they are excluded here. Automatic transitions pass no
        actor: even the annotator whose action triggered the advance may not
        realize they were the last one to finish."""
        Notification = apps.get_model("notifications", "Notification")  # noqa: N806
        label = BatchPhase(phase).label
        message = (
            f"Batch {self.batch_number} of project '{self.project.name}' moved to phase {label}."
        )
        users = self.users.all().distinct()
        if actor is not None:
            users = users.exclude(pk=actor.pk)
        Notification.objects.bulk_create(
            Notification(user=user, batch=self, message=message) for user in users
        )

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
