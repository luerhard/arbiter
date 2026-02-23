from django.contrib.auth import get_user_model
from django.db import models

from .project import ProjectRole

User = get_user_model()


class ProjectUser(models.Model):
    project = models.ForeignKey("Project", related_name="project_users", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    default_role = models.CharField(
        max_length=1,
        choices=ProjectRole,
        default=ProjectRole.ANNOTATOR,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project", "user"), name="unique_project_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.default_role} -> {self.project.name}"
