from annotation.models import Label
from django import forms
from django.contrib.auth.models import User

from core.models import Project
from core.models import ProjectAssignment


class ProjectForm(forms.Form):
    name = forms.CharField(max_length=100, help_text="Name of the Project")
    description = forms.CharField(widget=forms.Textarea)
    labels = forms.CharField(max_length=512, help_text="all labels in comma-separated values")
    
    def save(self, commit=True):
        data = self.cleaned_data
        project = Project(name=data["name"], description=data["description"])
        project.save()
        labels = []
        for label in data["labels"].split(","):
            obj = Label(project=project, name=label)
            labels.append(obj)
        
        Label.objects.bulk_create(labels)




# class ProjectAssignmentForm(forms.ModelForm):
#     user = forms.ModelMultipleChoiceField(
#         queryset=User.objects.exclude(is_superuser=True),
#         widget=forms.CheckboxSelectMultiple
#     )

#     class Meta:
#         model = ProjectAssignment
#         fields = ['project', 'user']

class ProjectAssignmentForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.exclude(is_superuser=True),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = ProjectAssignment
        fields = ["project"]  # Exclude the 'user' field

    def save(self, commit=True):
        project_assignment = super().save(commit=False)
        users = self.cleaned_data["users"]
        if commit:
            for user in users:
                ProjectAssignment.objects.create(project=self.cleaned_data["project"], user=user)
        return project_assignment        

    # class Meta:
    #     model = ProjectAssignment
    #     fields = ['project', 'user']

    # # project = forms.ModelChoiceField(queryset=Project.objects.all())
    # user = forms.ModelMultipleChoiceField(
    #     queryset=User.objects.exclude(is_superuser=True),
    #     widget=forms.CheckboxSelectMultiple)

    # user = forms.ModelMultipleChoiceField(queryset=User.objects.exclude(is_superuser=True), widget=forms.CheckboxSelectMultiple)
