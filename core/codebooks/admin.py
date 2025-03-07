from django.contrib import admin
from .models import Codebook, CodebookVersion
from .models import CodebookFieldModel, DescriptionField, DefinitionField, ExampleField


class CodebookVersionInline(admin.StackedInline):
    model = CodebookVersion
    min_num = 1
    extra = 0


@admin.register(Codebook)
class CodebookAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "get_latest_version", "get_latest_date",)
    inlines = (CodebookVersionInline,)

    def get_latest_version(self, obj):
        return obj.codebookversion_set.latest("date").version
    
    def get_latest_date(self, obj):
        return obj.codebookversion_set.latest("date").date

    get_latest_version.short_description = "Latest Version"
    get_latest_date.short_description = "Date"



class CodebookFieldModelInline(admin.TabularInline):
    model = CodebookFieldModel
    min_num = 1
    extra = 3


class DescriptionFieldInline(admin.TabularInline):
    model = DescriptionField
    extra = 1


class DefinitionFieldInline(admin.TabularInline):
    model = DefinitionField
    extra = 1


class ExampleFieldInline(admin.TabularInline):
    model = ExampleField
    extra = 1


class CodebookVersionAdmin(admin.ModelAdmin):
    list_display = ("get_codebook_name", "get_codebook_project", "version", "date",)
    ordering = ("date",)
    inline = (CodebookFieldModelInline, DescriptionFieldInline, DefinitionFieldInline, ExampleFieldInline,)

    def get_codebook_name(self, obj):
        return obj.codebook.name
    
    def get_codebook_project(self, obj):
        return obj.codebook.project

    get_codebook_name.short_description = "Name"
    get_codebook_project.short_description = "Project"


admin.site.register(CodebookVersion, CodebookVersionAdmin)


class CodebookFieldAdmin(admin.ModelAdmin):
    pass

admin.site.register(CodebookFieldModel, CodebookFieldAdmin)
