from crispy_forms.helper import FormHelper
from django import forms
from django.core.validators import MinLengthValidator
from django.urls import reverse_lazy

from .models import Definition
from .models import Example


class ExampleForm(forms.ModelForm):
    def __init__(self, pk, action="add", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = "add-example-form"
        self.action = action
        self.pk = pk
        if self.action == "add":
            path = "codebook-add-example"
            id_name = "definition_id"
        elif self.action == "update":
            path = "codebook-update-example"
            id_name = "example_id"
        else:
            msg = "Specify valid action."
            raise ValueError(msg)

        self.helper.attrs = {
            "hx-post": reverse_lazy(
                path,
                kwargs={id_name: self.pk},
            ),
            "hx-target": "#add-example",
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
        MinLengthValidator(2)(identifier)
        if self.action == "add":
            other_examples = Example.objects.filter(definition__id=self.pk).all()
        else:
            definition = (
                Definition.objects.filter(examples__id=self.pk).prefetch_related("examples").get()
            )
            other_examples = definition.examples.exclude(id=self.pk).all()

        if any(identifier == other.identifier for other in other_examples):
            msg = "Identifier already exists."
            raise forms.ValidationError(msg)
        return identifier
