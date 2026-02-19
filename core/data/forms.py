import logging

from django import forms

log = logging.getLogger(__name__)


class MultiLabelForm(forms.Form):
    labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, assignment, phase, **kwargs):
        super().__init__(*args, **kwargs)

        self.assignment = assignment
        self.example = assignment.example
        self.user = assignment.user
        annotation_labels = {
            annotation.label
            for annotation in self.example.get_user_annotations(
                user=assignment.user,
                phase=phase,
            ).select_related("label")
        }

        label_details = []
        initial = []
        for label in self.example.labels.all():
            label_data = {
                "id": label.id,
                "name": label.name,
                "color": label.color,
                "hotkey": label.hotkey,
            }
            label_details.append(label_data)
            if label in annotation_labels:
                initial.append(label.id)

        self.fields["labels"].initial = initial
        self.fields["labels"].choices = [(label["id"], label["name"]) for label in label_details]
        self.label_details = label_details

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data
        labels = [int(i) for i in data["labels"] if i.strip()]
        self.assignment.set_user_annotations(label_ids=labels)
