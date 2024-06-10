from django.db import models
from core.models import Project

class Sentence(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    content = models.TextField()

    def __str__(self):
        return self.content