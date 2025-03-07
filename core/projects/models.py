# core/models.py
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class ProjectUser(models.Model):
    project = models.ForeignKey("Project", related_name="project_users", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Role(models.TextChoices):
        ANNOTATOR = "A", "Annotator"
        EXPERT = "E", "Expert"

    role = models.CharField(max_length=1, choices=Role, default=Role.ANNOTATOR)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project", "user"), name="unique_project_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.role} -> {self.project.name}"


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    users = models.ManyToManyField(User, related_name="projects", through="ProjectUser")

    def user_role(self, user):
        return ProjectUser.objects.filter(project=self, user=user)

    @property
    def annotator_n_active_batches(self):
        return Batch.objects.filter(
            project=self,
            phase__in=[Batch.Phase.ANNOTATION, Batch.Phase.DISCUSSION],
        ).count()

    @property
    def annotator_any_annotation_batches(self):
        return Batch.objects.filter(
            project=self,
            phase__in=[Batch.Phase.ANNOTATION],
        ).exists()

    @property
    def annotator_any_discussion_batches(self):
        return Batch.objects.filter(
            project=self,
            phase__in=[Batch.Phase.DISCUSSION],
        ).exists()

    @property
    def annotators(self):
        return User.objects.filter(
            projectuser__project=self,
            projectuser__role=ProjectUser.Role.ANNOTATOR,
        )

    @property
    def experts(self):
        return User.objects.filter(
            projectuser__project=self,
            projectuser__role=ProjectUser.Role.EXPERT,
        )

    def __str__(self):
        return self.name


class Batch(models.Model):
    class Phase(models.TextChoices):
        SETUP = "S", "Setup"
        ANNOTATION = "A", "Annotation"
        DISCUSSION = "D", "Discussion"
        EXPERT = "E", "ExpertDecision"
        FINAL = "F", "Finalized"

    project = models.ForeignKey(Project, related_name="batches", on_delete=models.CASCADE)
    batch_number = models.SmallIntegerField()
    phase = models.CharField(
        default=Phase.SETUP,
        null=False,
        blank=False,
        max_length=1,
        choices=Phase,
        db_index=True,
    )
    codebook_version = models.ForeignKey(
        "codebooks.CodebookVersion", on_delete=models.SET_NULL, null=True
    )

    def __str__(self) -> str:
        return f"Batch {self.batch_number}"

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
        self.save()
