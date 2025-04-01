from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from .models import Codebook


class CodebookForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 32}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit("submit", "Save", css_class="btn-primary"))

    def get_success_url(self, **kwargs):  # noqa: ARG002
        self.object.get_absolute_url()

    class Meta:
        model = Codebook
        fields = []
