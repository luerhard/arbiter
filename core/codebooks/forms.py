from django import forms

from .models import Example


class ExampleForm(forms.ModelForm):
    class Meta:
        model = Example
        fields = ("identifier", "example", "comment", "definition")

        widgets = {
            "identifier": forms.TextInput(attrs={"class": "form-control"}),
            "example": forms.TextInput(attrs={"class": "form-control"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "definition": forms.HiddenInput(),
        }
