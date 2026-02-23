from codebook.models import Codebook
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class ProjectRole(models.TextChoices):
    ANNOTATOR = "A", "Annotator"
    EXPERT = "E", "Expert"


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    owner = models.ForeignKey(User, related_name="owned_projects", on_delete=models.CASCADE)
    users = models.ManyToManyField(User, related_name="projects", through="ProjectUser")

    @property
    def annotators(self):
        ProjectUser = apps.get_model("projects", "ProjectUser")
        return User.objects.filter(
            projectuser__project=self,
            projectuser__default_role=ProjectRole.ANNOTATOR,
        )

    @property
    def experts(self):
        ProjectUser = apps.get_model("projects", "ProjectUser")
        return User.objects.filter(
            projectuser__project=self,
            projectuser__default_role=ProjectRole.EXPERT,
        )

    @property
    def max_batch_number(self):
        Batch = apps.get_model("projects", "Batch")
        max_batch_number = (
            Batch.objects.filter(project=self)
            .aggregate(models.Max("batch_number"))
            .get("batch_number__max", 0)
        )
        if max_batch_number:
            return max_batch_number
        return 0

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # need to check before saving. Is always false otherwise
        is_new = self._state.adding is True
        super().save(*args, **kwargs)
        if is_new:
            Codebook.objects.get_or_create(project=self)
