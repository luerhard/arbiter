# core/models.py
from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    users = models.ManyToManyField(User, related_name="projects", through="ProjectUser")

    def __str__(self):
        return self.name


class ProjectUser(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Role(models.TextChoices):
        ANNOTATOR = "A", "Annotator"
        EXPERT = "E", "Expert"

    role = models.CharField(max_length=1, choices=Role, default=Role.ANNOTATOR)

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.role} -> {self.project.name}"
