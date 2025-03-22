"""Implements the models for the codebooks.

Each Codebook might have multiple versions modelled by CodebookVersion.
Each CodebookVersion has various fields, such as Description Model,
which are modular. To allow for future integration with a front end and
UX each of those fields has a codename which acts similarly to html ids.
"""

from django.db import models


class Codebook(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(
        "projects.Project",
        related_name="codebooks",
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"{self.name} - {self.project}"


class CodebookVersion(models.Model):
    """This model represents a specific version of a Codebook."""

    version_name = models.CharField("Version Name", max_length=10)
    date = models.DateTimeField("Addition Date")
    codebook = models.ForeignKey(Codebook, related_name="versions", on_delete=models.CASCADE)
    codebook_description = models.TextField()

    def __str__(self):
        return f"{self.codebook.name} - {self.codebook.project} - {self.version_name}"


class Description(models.Model):
    codebook_version = models.ForeignKey(
        CodebookVersion,
        related_name="descriptions",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=32, blank=True, null=True)
    order = models.PositiveIntegerField(blank=False)
    codebook_description = models.TextField()

    class Meta:
        ordering = ["order"]
        unique_together = [
            ("codebook_version", "title"),
            ("codebook_version", "order"),
        ]

    def __str__(self):
        return f"{self.title or ''} Description Field"


class Definition(models.Model):
    codebook_version = models.ForeignKey(
        CodebookVersion,
        related_name="definitions",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=32, blank=True, null=True)
    identifier = models.CharField(max_length=31, blank=True, null=True)
    order = models.PositiveIntegerField(blank=False)
    short_description = models.CharField(max_length=1000)
    long_description = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [
            ("codebook_version", "title"),
            ("codebook_version", "identifier"),
            ("codebook_version", "order"),
        ]

    def __str__(self):
        return f"{self.title or ''} Definition Field"


class Example(models.Model):
    definition = models.ForeignKey(
        Definition,
        related_name="examples",
        on_delete=models.CASCADE,
    )
    identifier = models.CharField(max_length=32, blank=False)
    order = models.PositiveIntegerField(blank=True, null=True)
    preamble = models.TextField(blank=True, null=True)
    example = models.CharField(max_length=1000)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["order"]
        unique_together = [
            ("definition", "identifier"),
        ]

    def __str__(self):
        return f"{self.identifier or ''} Example Field"
