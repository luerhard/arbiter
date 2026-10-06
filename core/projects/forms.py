from django import forms
from django.core.exceptions import ValidationError
import pandas as pd

from projects.models import Batch
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
        base_input = "input"
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
                {"class": "space-y-2 text-sm text-ink-2"},
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

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        # Any project member can take either role in a batch; users outside
        # the project would get assignments for pages they cannot open.
        members = User.objects.filter(projectuser__project=project)
        self.fields["annotators"].queryset = members
        self.fields["experts"].queryset = members
        self.fields["file"].widget.attrs.update(
            {
                "class": "file-input",
                "accept": ".csv,.xlsx",
            },
        )
        for field in ("annotators", "experts"):
            self.fields[field].widget.attrs.update(
                {"class": "space-y-2 text-sm text-ink-2"},
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
        """Read the uploaded table; its "text" column becomes the batch's samples (self.texts)."""
        file = self.cleaned_data["file"]
        name = (file.name or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx")):
            msg = "Please upload a .csv or .xlsx file."
            raise ValidationError(msg)
        try:
            table = pd.read_csv(file) if name.endswith(".csv") else pd.read_excel(file)
        except ValueError as exc:
            msg = "The file could not be read."
            raise ValidationError(msg) from exc
        if "text" not in table.columns:
            msg = "The file needs a column named 'text'."
            raise ValidationError(msg)
        self.texts = table["text"].tolist()
        return file


class BatchPhaseForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["current_phase"]
