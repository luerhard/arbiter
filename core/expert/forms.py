import logging

from django import forms

from data.models import ExampleAssignment
from data.models import Label
from projects.models import BatchPhase

log = logging.getLogger(__name__)


class MultiLabelFormExpert(forms.Form):
    labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, example, codebook, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.example = example
        self.user = user
        self.assignment = ExampleAssignment.objects.filter(
            example=self.example,
            user=self.user,
            phase=BatchPhase.EXPERT,
        ).get()
        labels_queryset = Label.objects.filter(project_id=codebook.project.id)
        labels_choices = [(label.id, label.name) for label in labels_queryset]
        log.debug(f"{labels_choices =}")
        self.fields["labels"].choices = labels_choices

    def save(self):
        data = self.cleaned_data
        labels = [int(i) for i in data["labels"] if i.strip()]
        if labels:
            log.info(
                "Expert decision saved: example=%s user=%s labels=%s",
                self.example.id,
                self.user.username,
                labels,
            )
        else:
            log.info(
                "Expert decision saved with no labels (non-offensive): example=%s user=%s",
                self.example.id,
                self.user.username,
            )
        self.assignment.set_user_annotations(label_ids=labels)
