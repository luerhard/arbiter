from django.apps import apps
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, username, password, **extra_fields):
        user = self.model(
            username=username,
            **extra_fields,
        )

        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(username, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(verbose_name="Email Adress", blank=True, null=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    objects = UserManager()  # type: ignore

    @property
    def assigned_projects(self):
        projectusermodel = apps.get_model("projects.ProjectUser")
        all_assigned_projects = projectusermodel.objects.prefetch_related("project").filter(
            user_id=self.pk,
        )
        grouped = {role.label: set() for role in projectusermodel.Role}
        for project_user in all_assigned_projects:
            grouped[project_user.get_default_role_display()].add(project_user.project)
        return grouped

    @property
    def discuss_batches(self):
        # TODO: optimize!
        projectusermodel = apps.get_model("projects.ProjectUser")
        all_projects = (
            projectusermodel.objects
            .prefetch_related("project")
            .prefetch_related("project__batches")
            .filter(user_id=self.pk)
            .all()
        )
        return_val = {}
        for project_user in all_projects:
            project = project_user.project
            project_batches = []
            for batch in project.batches.all():
                if batch.annotation_done:
                    project_batches.append(batch)
            if project_batches:
                return_val[project] = project_batches
        return return_val

    def __str__(self) -> str:
        return self.username
