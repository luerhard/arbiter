from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.shortcuts import get_object_or_404
import pandas as pd

from data.models import Example
from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchAssignment
from projects.models import Project
from projects.models import ProjectUser
from users.models import User


class ProjectCreateForm(forms.Form):
    name = forms.CharField(max_length=100, label="Project title")
    description = forms.CharField(widget=forms.Textarea, required=False)
    annotators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    experts = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_input = (
            "block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm "
            "text-gray-900 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 "
            "dark:border-white/10 dark:bg-gray-900 dark:text-white"
        )
        self.fields["name"].widget.attrs.update(
            {
                "class": base_input,
                "placeholder": "Project title",
            },
        )
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


class BatchCreateForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ("file",)

    file = forms.FileField(required=True)

    annotators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    experts = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update(
            {
                "class": "block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm "  # noqa: E501
                "text-gray-900 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 "  # noqa: E501
                "dark:border-white/10 dark:bg-gray-900 dark:text-white",
                "accept": ".csv,.xlsx",
            },
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

    def clean_file(self):
        file = self.cleaned_data["file"]
        name = (file.name or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx")):
            msg = "Please upload a .csv or .xlsx file."
            raise ValidationError(msg)
        return file


class BatchPhaseForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["current_phase"]
