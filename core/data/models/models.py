from colorfield.fields import ColorField
from django.db import models

from projects.models import Project


class Label(models.Model):
    project = models.ForeignKey(Project, related_name="labels", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = ColorField(max_length=7, default="#155596")
    hotkey = models.CharField(max_length=1, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project", "name"), name="unique_label_name"),
            models.UniqueConstraint(fields=("project", "hotkey"), name="unique_hotkey"),
        ]


class Annotation(models.Model):
    assignment = models.ForeignKey(
        "ExampleAssignment",
        related_name="annotations",
        on_delete=models.CASCADE,
    )
    label = models.ForeignKey(
        Label,
        related_name="label",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    @property
    def sentence(self):
        return self.user_example.example

    class Meta:
        unique_together = ("assignment", "label")
