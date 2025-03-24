from crispy_forms.helper import FormHelper
from django import forms
from django.urls import reverse_lazy

from .models import Example


class ExampleForm(forms.ModelForm):
    example_id = forms.IntegerField(widget=forms.HiddenInput(), initial=None, required=False)

    def __init__(self, definition, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.definition = definition
        self.helper = FormHelper(self)
        self.helper.form_id = "add-example-form"
        self.helper.attrs = {
            "hx-post": reverse_lazy(
                "codebook-add-example",
                kwargs={"definition_id": self.definition.pk},
            ),
            "hx-target": "#add-example-form",
        }

    class Meta:
        model = Example
        fields = ("identifier", "example", "comment")

        widgets = {
            "identifier": forms.TextInput(),
            "example": forms.TextInput(),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_identifier(self):
        identifier = self.cleaned_data["identifier"]
        if len(identifier) < 2:
            msg = "Identifier too short. Minimum of 2 characters."
            raise forms.ValidationError(msg)
        if not self.data.get("example_id"):
            existing_identifiers = {ex.identifier for ex in self.definition.examples.all()}
            if identifier in existing_identifiers:
                msg = "Identifier not unique."
                raise forms.ValidationError(msg)
        return identifier
