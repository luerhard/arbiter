from colorfield.fields import ColorField
from django.db import models

from projects.models import Project

# colors for new labels, one after the other: labels must be told apart, also as spans
LABEL_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777"]


def label_color(index: int) -> str:
    return LABEL_COLORS[index % len(LABEL_COLORS)]


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
    # the labeled passage in span projects, character offsets into the text
    start = models.PositiveIntegerField(null=True, blank=True)
    end = models.PositiveIntegerField(null=True, blank=True)

    @property
    def text(self) -> str | None:
        """The labeled passage in span projects."""
        if self.start is None:
            return None
        return self.assignment.example.content[self.start : self.end]

    @property
    def sentence(self):
        return self.user_example.example

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("assignment", "label"),
                condition=models.Q(start__isnull=True),
                name="unique_label_per_assignment",
            ),
            models.UniqueConstraint(
                fields=("assignment", "label", "start", "end"),
                name="unique_span_per_assignment",
            ),
            models.CheckConstraint(
                condition=models.Q(start__isnull=True, end__isnull=True)
                | models.Q(start__lt=models.F("end")),
                name="span_start_before_end",
            ),
        ]
