from django.apps import apps
from django.db import models


class Batch(models.Model):
    class Phase(models.TextChoices):
        SETUP = "S", "Setup"
        ANNOTATION = "A", "Annotation"
        DISCUSSION = "D", "Discussion"
        EXPERT = "E", "ExpertDecision"
        FINAL = "F", "Finalized"

    project = models.ForeignKey("Project", related_name="batches", on_delete=models.CASCADE)
    batch_number = models.SmallIntegerField()
    phase = models.CharField(
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

    @property
    def labels(self):
        return self.project.labels

    def already_annotated_count(self, user):
        user_sentence = apps.get_model("annotation.UserSentence")
        return user_sentence.objects.filter(
            sentence__batch=self,
            user=user,
            is_annotated=True,
        ).count()

    def set_phase(self, phase):
        self.phase = phase
        if self.phase == Batch.Phase.ANNOTATION:
            codebook = self.project.codebook.get()
            codebook.tag_version(self.batch_number)
        elif self.phase == Batch.Phase.DISCUSSION:
            self._create_phase_assignments(
                source_phase=Batch.Phase.ANNOTATION,
                target_phase=Batch.Phase.DISCUSSION,
                role_key="ANNOTATOR",
            )
        elif self.phase == Batch.Phase.EXPERT:
            self._create_phase_assignments(
                source_phase=Batch.Phase.DISCUSSION,
                target_phase=Batch.Phase.EXPERT,
                role_key="EXPERT",
            )
        self.save()

    def _create_phase_assignments(self, source_phase, target_phase, role_key: str):
        Example = apps.get_model("data", "Example")
        ExampleAssignment = apps.get_model("data", "ExampleAssignment")
        BatchAssignment = apps.get_model("projects", "BatchAssignment")
        ProjectUser = apps.get_model("projects", "ProjectUser")

        role = getattr(ProjectUser.Role, role_key)

        # Ensure batch assignments exist for the target role (e.g., experts).
        for user in self.project.users.filter(
            projectuser__project=self.project,
            projectuser__default_role=role,
        ):
            BatchAssignment.objects.get_or_create(
                batch=self,
                user=user,
                defaults={"role": role, "phase": self.phase},
            )

        examples = list(
            Example.objects.filter(batch=self).disagreements(phase=source_phase).order_by("id"),
        )
        if not examples:
            return

        for batch_assignment in BatchAssignment.objects.filter(batch=self, role=role):
            for idx, example in enumerate(examples, 1):
                ExampleAssignment.objects.get_or_create(
                    example=example,
                    batch_assignment=batch_assignment,
                    phase=target_phase,
                    defaults={"order": idx},
                )
