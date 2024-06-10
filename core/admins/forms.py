from django import forms
from core.models import Project, ProjectAssignment
from django.contrib.auth.models import User

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']

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
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = ProjectAssignment
        fields = ['project']  # Exclude the 'user' field

    def save(self, commit=True):
        project_assignment = super().save(commit=False)
        users = self.cleaned_data['users']
        if commit:
            for user in users:
                ProjectAssignment.objects.create(project=self.cleaned_data['project'], user=user)
        return project_assignment        

    # class Meta:
    #     model = ProjectAssignment
    #     fields = ['project', 'user']

    # # project = forms.ModelChoiceField(queryset=Project.objects.all())
    # user = forms.ModelMultipleChoiceField(
    #     queryset=User.objects.exclude(is_superuser=True),
    #     widget=forms.CheckboxSelectMultiple)

    # user = forms.ModelMultipleChoiceField(queryset=User.objects.exclude(is_superuser=True), widget=forms.CheckboxSelectMultiple)
