# core/models.py
from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    labels = models.CharField(max_length=500, help_text="Comma-separated labels for this project", default='default_label_value')

    def __str__(self):
        return self.name

class ProjectAssignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} -> {self.project.name}"

