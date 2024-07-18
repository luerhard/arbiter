
from django.contrib import admin

from .forms import BatchForm
from .forms import ProjectForm
from annotation.models import Batch
from annotation.models import Label
from core.models import Project


# Register your models here.
class ProjectUserInline(admin.TabularInline):
    model = Project.users.through
    extra = 2

class LabelInline(admin.TabularInline):
    model = Label
    extra = 2

class BatchInline(admin.TabularInline):
    model = Batch
    form = BatchForm
    extra = 1

@admin.register(Project)
class AdminProject(admin.ModelAdmin):
    form = ProjectForm
    inlines = (LabelInline, ProjectUserInline, BatchInline)
