from codebook.models import Codebook
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models

from .project_user import ProjectUser

User = get_user_model()


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    users = models.ManyToManyField(User, related_name="projects", through="ProjectUser")

    def user_role(self, user):
        return ProjectUser.objects.filter(project=self, user=user)

    @property
    def annotator_n_active_batches(self):
        Batch = apps.get_model("projects", "Batch")
        return Batch.objects.filter(
            project=self,
            current_phase__in=[Batch.Phase.ANNOTATION, Batch.Phase.DISCUSSION],
        ).count()

    @property
    def annotator_any_annotation_batches(self):
        Batch = apps.get_model("projects", "Batch")
        return Batch.objects.filter(
            project=self,
            current_phase__in=[Batch.Phase.ANNOTATION],
        ).exists()

    @property
    def annotator_any_discussion_batches(self):
        Batch = apps.get_model("projects", "Batch")
        return Batch.objects.filter(
            project=self,
            current_phase__in=[Batch.Phase.DISCUSSION],
        ).exists()

    @property
    def annotators(self):
        return User.objects.filter(
            projectuser__project=self,
            projectuser__default_role=ProjectUser.Role.ANNOTATOR,
        )

    @property
    def experts(self):
        return User.objects.filter(
            projectuser__project=self,
            projectuser__default_role=ProjectUser.Role.EXPERT,
        )

    @property
    def max_batch_number(self):
        Batch = apps.get_model("projects", "Batch")
        max_batch_number = (
            Batch.objects
            .filter(project=self)
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
            print("adding codebook")
            Codebook.objects.get_or_create(project=self)
