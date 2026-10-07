import json

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
        """Read the uploaded table into self.examples: one (text, metadata) pair per row, where
        metadata holds the row's other columns, e.g. {"id": 7, "source": "twitter"}."""
        file = self.cleaned_data["file"]
        name = (file.name or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx")):
            msg = "Please upload a .csv or .xlsx file."
            raise ValidationError(msg)
        read = pd.read_csv if name.endswith(".csv") else pd.read_excel
        try:
            table = read(file)
            if "text" not in table.columns:
                msg = "The file needs a column named 'text'."
                raise ValidationError(msg)
            # The texts once more, exactly as written: pandas reads "NA", "None", "null" and
            # the like as empty cells, and "007" as the number 7.
            file.seek(0)
            texts = read(file, usecols=["text"], dtype=str, keep_default_na=False)["text"]
        except ValueError as exc:
            msg = "The file could not be read."
            raise ValidationError(msg) from exc

        # via JSON, so that empty cells become None and dates/numbers plain JSON values
        rows = json.loads(table.to_json(orient="records", date_format="iso"))
        for row, text in zip(rows, texts, strict=True):
            row["text"] = text if isinstance(text, str) else ""  # e.g. an Excel #N/A error cell
        empty = [number for number, row in enumerate(rows, start=2) if not row["text"]]
        if empty:
            listed = ", ".join(str(number) for number in empty[:5])
            msg = (
                f"Row {listed} has no text." if len(empty) == 1 else f"Rows {listed} have no text."
            )
            raise ValidationError(msg)
        self.examples = [(str(row.pop("text")), row) for row in rows]
        return file


class BatchPhaseForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["current_phase"]
