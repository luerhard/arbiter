import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from .models import Codebook
from data.models import Label

log = logging.getLogger(__name__)


class CodebookForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 32}))
    rationale = forms.CharField(widget=forms.Textarea(attrs={"rows": 8}))
    sentence = forms.CharField(widget=forms.Textarea, required=False)
    example_id = forms.IntegerField(widget=forms.NumberInput, required=False)
    batch_id = forms.IntegerField(widget=forms.NumberInput, required=False)
    selected_labels = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit("submit", "Save", css_class="btn-primary"))
        # This doesn't pass as valid form because the expert dialogue web page sends to forms
        # The labels form gets sent to save-labels as "selected_labels=1&selected_labels=2".
        # While the other form sends it as "name=selected_labels        1,2" to codebook/edit/1
        # TODO: Therefore, we must create another form: LabelForm in data/forms and a model that would save those labels.
        # TODO: Make sure that the labelForm.submit() from expert/templates/dialogue.html is being processed by the data/models.py.
        # TODO: Also, turn off access to codebook/edit/ page. Make it only accept POST and check for admin?.
        labels_queryset = Label.objects.filter(project_id=kwargs["instance"].project_id)
        labels_choices = [(label.id, label.name) for label in labels_queryset]
        self.fields["selected_labels"].choices = labels_choices

    def get_success_url(self, **kwargs):  # noqa: ARG002
        self.object.get_absolute_url()

    class Meta:
        model = Codebook
        fields = []
