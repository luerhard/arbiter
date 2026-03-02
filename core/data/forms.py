import logging

from django import forms

log = logging.getLogger(__name__)


class MultiLabelForm(forms.Form):
    labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)

        self.assignment = assignment
        self.user = assignment.user
        annotation_labels = assignment.get_user_annotations()

        label_details = []
        initial = []
        for label in self.assignment.batch.project.labels.all():
            label_data = {
                "id": label.id,
                "name": label.name,
                "color": label.color,
                "hotkey": label.hotkey,
                "selected": label in annotation_labels,
            }
            label_details.append(label_data)

        self.fields["labels"].initial = label_details
        self.fields["labels"].choices = [(label["id"], label["name"]) for label in label_details]
        self.label_details = label_details

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data
        labels = [int(i) for i in data["labels"] if i.strip()]
        self.assignment.set_user_annotations(label_ids=labels)
