import logging

from django import forms

from data.models import Label


log = logging.getLogger(__name__)


class MultiLabelFormAnnotation(forms.Form):
    labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)

        self.assignment = assignment
        self.example = assignment.example
        self.user = assignment.user
        annotation_labels = {
            annotation.label
            for annotation in self.example.get_user_annotations(
                user=assignment.user,
                phase="ANNOTATION",
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
        self.example.set_user_annotations(user=self.user, label_ids=labels, phase="ANNOTATION")


class MultiLabelFormExpert(forms.Form):
    selected_labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, example, codebook, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.example = example
        self.user = user
        labels_queryset = Label.objects.filter(project_id=codebook.project.id)
        labels_choices = [(label.id, label.name) for label in labels_queryset]
        self.fields["selected_labels"].choices = labels_choices

    def save(self):
        data = self.cleaned_data["selected_labels"]
        labels = [int(i) for i in data if i.strip()]
        self.example.set_user_annotations(user=self.user, label_ids=labels, phase="EXPERT")
