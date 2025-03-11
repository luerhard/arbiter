"""Implements the models for the codebooks.

Each Codebook might have multiple versions modelled by CodebookVersion.
Each CodebookVersion has various fields, such as Description Model,
which are modular. To allow for future integration with a front end and
UX each of those fields has a codename which acts similarly to html ids.
"""

from django.db import models


class Codebook(models.Model):
    name = models.CharField(max_length=100)
    # As the schema gets integrated into the core app this will change
    project = models.ForeignKey("projects.Project", null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} - {self.project}"


class CodebookVersion(models.Model):
    """This model represents a specific version of a Codebook."""

    version = models.CharField("Version", max_length=10)
    date = models.DateField("Addition Date")
    codebook = models.ForeignKey(Codebook, on_delete=models.CASCADE)
    codebook_description = models.TextField()

    def __str__(self):
        return f"{self.codebook.name} - {self.codebook.project} - {self.version}"


class DescriptionField(models.Model):
    codebook_version = models.ForeignKey(CodebookVersion, on_delete=models.CASCADE, null=False)
    codename = models.CharField(
        max_length=32, unique=True, blank=True, null=True
    )  # Can be also named index
    order_index = models.PositiveIntegerField(unique=True)
    codebook_description = models.TextField()


class DefinitionField(models.Model):
    codebook_version = models.ForeignKey(CodebookVersion, on_delete=models.CASCADE, null=False)
    codename = models.CharField(
        max_length=32, unique=True, blank=True, null=True
    )  # Can be also named index
    order_index = models.PositiveIntegerField(unique=True)
    term = models.CharField(max_length=31)
    short_description = models.CharField(max_length=1000)
    long_description = models.TextField()


class ExampleField(models.Model):
    codebook_version = models.ForeignKey(CodebookVersion, on_delete=models.CASCADE, null=False)
    codename = models.CharField(
        max_length=32, unique=True, blank=True, null=True
    )  # Can be also named index
    order_index = models.PositiveIntegerField(unique=True)
    definition_field = models.ForeignKey(DefinitionField, on_delete=models.SET_NULL, null=True)
    example = models.CharField(max_length=300)
    comment = models.TextField(blank=True, null=True)
