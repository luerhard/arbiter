from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
import pandas as pd

from data.models import Example
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import Project
from projects.models import ProjectUser
from users.models import User


class ProjectForm(forms.ModelForm):
    name = forms.CharField(max_length=100, help_text="Name of the Project")
    description = forms.CharField(widget=forms.Textarea)

    class Meta:
        model = Project
        fields = ["name", "description"]


class ProjectCreateForm(forms.Form):
    name = forms.CharField(max_length=100, label="Project title")
    description = forms.CharField(widget=forms.Textarea, required=True)
    annotators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    experts = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_input = (
            "block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm "
            "text-gray-900 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 "
            "dark:border-white/10 dark:bg-gray-900 dark:text-white"
        )
        self.fields["name"].widget.attrs.update({
            "class": base_input,
            "placeholder": "Project title",
        })
        self.fields["description"].widget.attrs.update(
            {"class": base_input, "rows": 4, "placeholder": "What is this project about?"},
        )
        for field in ("annotators", "experts"):
            self.fields[field].widget.attrs.update(
                {"class": "space-y-2 text-sm text-gray-700 dark:text-gray-300"},
            )

    def clean(self):
        cleaned = super().clean()
        annotators = set(cleaned.get("annotators") or [])
        experts = set(cleaned.get("experts") or [])
        overlap = annotators & experts
        if overlap:
            names = ", ".join(sorted(u.username for u in overlap))
            msg = f"Users cannot be both annotator and expert: {names}"
            raise ValidationError(msg)
        return cleaned


class ProjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = ProjectUser
        fields = ["project"]  # Exclude the 'user' field

    annotators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
    )

    experts = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
    )

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data

        new = []
        existing = []
        for annotator in data["annotators"]:
            assign, created = ProjectUser.objects.get_or_create(
                user=annotator,
                project=data["project"],
            )
            assign.role = assign.Role.ANNOTATOR
            if created:
                new.append(assign)
            else:
                existing.append(assign)

        for annotator in data["experts"]:
            assign, created = ProjectUser.objects.get_or_create(
                user=annotator,
                project=data["project"],
            )
            assign.role = assign.Role.EXPERT
            if created:
                new.append(assign)
            else:
                existing.append(assign)

        if new:
            ProjectUser.objects.bulk_create(new)
        if existing:
            ProjectUser.objects.bulk_update(new, fields=["role"])


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ("file",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            if self.instance.examples.exists():
                self.fields["file"].disabled = True

    file = forms.FileField(required=False)

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data
        project = data["project"]
        project.save()
        file = data["file"]
        if not file:
            return

        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file)

        # get max previous batch number and increment by one
        max_batch_number = Batch.objects.filter(project=project).aggregate(Max("batch_number"))
        max_batch_number = max_batch_number["batch_number__max"]
        if max_batch_number is None:
            max_batch_number = 0

        max_batch_number += 1

        batch = Batch(project=project, batch_number=max_batch_number)
        batch.save()
        default_annotators = batch.project.annotators.all()
        batch_assignments = {
            annotator.id: BatchAssignment.objects.create(
                batch=batch,
                user=annotator,
                role=ProjectUser.Role.ANNOTATOR,
                phase=batch.phase,
            )
            for annotator in default_annotators
        }
        for _, row in df.iterrows():
            example = Example(batch=batch, content=row["text"])
            example.save()
            for annotator in default_annotators:
                assignment = ExampleAssignment(
                    example=example,
                    batch_assignment=batch_assignments[annotator.id],
                )
                assignment.save()

        return batch


class BatchPhaseForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["phase"]
