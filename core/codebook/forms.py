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
    content = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 32, "class": textarea_class})
    )
    rationale = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "class": textarea_class}),
        required=False,
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit("submit", "Save", css_class="btn-primary"))

    def save(self, codebook):
        if "rationale" not in self.changed_data:
            # For now we'll not save anything if the rationale is empty
            return
        content = self.cleaned_data["content"]
        rationale = self.cleaned_data["rationale"]

        commit_info = {
            "rationale": rationale,
        }
        commit_message = json.dumps(commit_info, ensure_ascii=False)
        if content:
            codebook.save(content=content, commit_message=commit_message)
