from django.contrib import admin

from .models import Codebook
from .models import CodebookVersion
from .models import DefinitionField
from .models import DescriptionField
from .models import ExampleField


class CodebookVersionInline(admin.StackedInline):
    model = CodebookVersion
    min_num = 1
    extra = 0


@admin.register(Codebook)
class CodebookAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "get_latest_version", "get_latest_date")
    inlines = (CodebookVersionInline,)

    def get_latest_version(self, obj):
        return obj.codebookversion_set.latest("date").version

    def get_latest_date(self, obj):
        return obj.codebookversion_set.latest("date").date

    get_latest_version.short_description = "Latest Version"
    get_latest_date.short_description = "Date"


class DescriptionFieldInline(admin.StackedInline):
    model = DescriptionField
    extra = 0


class DefinitionFieldInline(admin.StackedInline):
    model = DefinitionField
    extra = 0


class ExampleFieldInline(admin.StackedInline):
    model = ExampleField
    extra = 0


@admin.register(CodebookVersion)
class CodebookVersionAdmin(admin.ModelAdmin):
    list_display = ("get_codebook_name", "get_codebook_project", "version", "date")
    ordering = ("date",)
    inlines = (
        DescriptionFieldInline,
        DefinitionFieldInline,
        ExampleFieldInline,
    )

    def get_codebook_name(self, obj):
        return obj.codebook.name

    def get_codebook_project(self, obj):
        return obj.codebook.project

    get_codebook_name.short_description = "Name"
    get_codebook_project.short_description = "Project"
