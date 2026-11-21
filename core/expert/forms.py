from django import forms

from data.models import Label
from projects.models import BatchPhase


class MultiLabelFormExpert(forms.Form):
    labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        self.example = assignment.example
        self.user = assignment.user

        label_details = []
        for label in Label.objects.filter(project=assignment.batch.project):
            label_details.append(
                {
                    "id": label.id,
                    "name": label.name,
                    "color": label.color,
                    "hotkey": label.hotkey,
                },
            )
        self.fields["labels"].choices = [(label["id"], label["name"]) for label in label_details]
        self.fields["labels"].initial = self._initial_label_ids()
        self.label_details = label_details

    def _initial_label_ids(self):
        # Editing a saved decision pre-selects that decision; an open
        # assignment pre-selects the labels every annotator kept after the
        # discussion. Contested labels stay open: pre-selecting them too would
        # let a quick save decide for both sides (Positive and Negative).
        if self.assignment.done is not None:
            return sorted(self.assignment.annotations.values_list("label_id", flat=True))
        from data.models import ExampleAssignment

        discussion = ExampleAssignment.objects.filter(
            example=self.example,
            batch=self.assignment.batch,
            phase=BatchPhase.DISCUSSION,
        ).prefetch_related("annotations")
        label_sets = [{a.label_id for a in d.annotations.all()} for d in discussion]
        return sorted(set.intersection(*label_sets)) if label_sets else []
