# core/models.py
from django.contrib.auth.models import User
from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name

class Label(models.Model):
    label = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name="labels", on_delete=models.CASCADE)
    hotkey = models.CharField(max_length=1, null=True)


class ProjectAssignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} -> {self.project.name}"
