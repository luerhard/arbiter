from django.contrib import admin

from .forms import BatchForm
from annotation.models import Batch
from core.models import Project


# Register your models here.
class ProjectUserInline(admin.TabularInline):
    model = Project.users.through

class BatchInline(admin.TabularInline):
    model = Batch
    form = BatchForm

@admin.register(Project)
class AdminProject(admin.ModelAdmin):
    inlines = (ProjectUserInline, BatchInline)
