from django.contrib import admin
import nested_admin

from .models import Codebook
from .models import CodebookVersion
from .models import Definition
from .models import Description
from .models import Example


class CodebookVersionInline(admin.StackedInline):
    model = CodebookVersion
    min_num = 1
    extra = 0


@admin.register(Codebook)
class CodebookAdmin(admin.ModelAdmin):
    list_display = ("get_latest_version", "name", "project", "get_latest_date")
    inlines = (CodebookVersionInline,)

    def get_latest_version(self, obj):
        return obj.versions.order_by("date")[0].version_name

    def get_latest_date(self, obj):
        return obj.versions.order_by("date")[0].date

    get_latest_version.short_description = "Latest Version Name"
    get_latest_date.short_description = "Date"


class DescriptionInline(nested_admin.NestedStackedInline):
    model = Description
    extra = 0


class ExampleInline(nested_admin.NestedStackedInline):
    model = Example
    sortable_field_name = "order_index"
    extra = 0


class DefinitionInline(nested_admin.NestedStackedInline):
    model = Definition
    extra = 0
    inlines = [ExampleInline]


@admin.register(CodebookVersion)
class CodebookVersionAdmin(nested_admin.NestedModelAdmin):
    list_display = ("version_name", "get_codebook_name", "get_codebook_project", "date")
    ordering = ("date",)
    inlines = (
        DescriptionInline,
        DefinitionInline,
    )

    def get_codebook_name(self, obj):
        return obj.codebook.name

    def get_codebook_project(self, obj):
        return obj.codebook.project

    get_codebook_name.short_description = "Name"
    get_codebook_project.short_description = "Project"
