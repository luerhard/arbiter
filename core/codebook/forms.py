import json
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

log = logging.getLogger(__name__)


class CodebookForm(forms.Form):
    textarea_class = (
        "w-full border bg-white dark:bg-gray-900 p-2 text-gray-900 dark:text-gray-100 "
        "caret-blue-500 focus:outline-none focus:ring-1 focus:border-blue-500 "
        "focus:ring-blue-500 rounded-2xl p-2 scrollbar rounded-2xl"
    )
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 32, "class": textarea_class}))
    rationale = forms.CharField(widget=forms.Textarea(attrs={"rows": 8, "class": textarea_class}))
    modified = forms.BooleanField(initial=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit("submit", "Save", css_class="btn-primary"))

    def clean_modified(self):
        field_name = self.add_prefix("modified")
        if field_name not in self.data:
            # Enforce the initial value when modified wasn't supplied.
            return self.fields["modified"].initial
        return self.cleaned_data["modified"]

    def clean(self, *args, **kwargs):
        cleaned_data = super().clean(*args, **kwargs)
        # If 'modified' is False, we discard all other validation errors
        # This is admissible because it won't save the form anyways.
        if not cleaned_data.get("modified"):
            self._errors.clear()
        return cleaned_data

    def save(self, codebook, metadata=None):
        if not self.cleaned_data["modified"]:
            return

        content = self.cleaned_data["content"]
        rationale = self.cleaned_data["rationale"]

        commit_info = {
            "rationale": rationale,
        }
        if metadata:
            commit_info.update(metadata)
        commit_message = json.dumps(commit_info, ensure_ascii=False)
        if content:
            codebook.save(content=content, commit_message=commit_message)
