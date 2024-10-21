from django import forms


class MultiLabelForm(forms.Form):
    labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)

        self.example = assignment.example
        self.user = assignment.user
        annotation_labels = {
            annotation.label
            for annotation in self.example.get_user_annotations(
                assignment.user,
                phase="ANNOTATION",
            ).select_related("label")
        }

        self.shortcuts = []
        choices = []
        initial = []
        for label in self.example.labels.all():
            text = f"{label.name}"
            self.shortcuts.append(label.hotkey)
            choice = (label.id, text)
            choices.append(choice)
            if label in annotation_labels:
                initial.append(label.id)

        self.fields["labels"].choices = choices
        self.fields["labels"].initial = initial

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data
        labels = [int(i) for i in data["labels"] if i.strip()]
        self.example.set_user_annotations(user=self.user, label_ids=labels, phase="ANNOTATION")
