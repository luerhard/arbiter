from django import forms
from django.db.models import Max
import pandas as pd

from annotation.models import Batch
from annotation.models import Label
from annotation.models import Sentence
from core.models import Project
from core.models import ProjectUser
from users.models import User


class ProjectForm(forms.Form):
    name = forms.CharField(max_length=100, help_text="Name of the Project")
    description = forms.CharField(widget=forms.Textarea)
    labels = forms.CharField(max_length=512, help_text="all labels in comma-separated values")

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data
        project = Project(name=data["name"], description=data["description"])
        project.save()
        labels = []
        for label in data["labels"].split(","):
            obj = Label(project=project, name=label)
            labels.append(obj)

        Label.objects.bulk_create(labels)


class ProjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = ProjectUser
        fields = ["project"]  # Exclude the 'user' field

    annotators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
    )

    experts = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
    )

    def save(self, commit=True):  # noqa: ARG002
        data = self.cleaned_data

        new = []
        existing = []
        for annotator in data["annotators"]:
            assign, created = ProjectUser.objects.get_or_create(
                user=annotator, project=data["project"],
            )
            assign.role = assign.Role.ANNOTATOR
            if created:
                new.append(assign)
            else:
                existing.append(assign)

        for annotator in data["experts"]:
            assign, created = ProjectUser.objects.get_or_create(
                user=annotator, project=data["project"],
            )
            assign.role = assign.Role.EXPERT
            if created:
                new.append(assign)
            else:
                existing.append(assign)

        if new:
            ProjectUser.objects.bulk_create(new)
        if existing:
            ProjectUser.objects.bulk_update(new, fields=["role"])


class BatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            if self.instance.sentences.exists():
  # replace `your_file_field` with the actual field name
                self.fields["file"].disabled = True



    class Meta:
        model = Batch
        fields = ("file",)

    file = forms.FileField(required=False)

    def save(self, commit=True): ## noqa: ARG002
        data = self.cleaned_data
        project = data["project"]
        project.save()
        file = data["file"]
        if not file:
            return

        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file)

        #get max previous batch number and increment by one
        max_batch_number = Batch.objects.filter(project=project).aggregate(Max("batch_number"))
        max_batch_number = max_batch_number["batch_number__max"]
        if max_batch_number is None:
            max_batch_number = 0

        max_batch_number += 1

        batch = Batch(project=project, batch_number=max_batch_number)
        batch.save()
        sentences = []
        for _, row in df.iterrows():
            sent = Sentence(project=project, batch=batch, content=row["text"])
            sent.save()

        Sentence.objects.bulk_create(sentences)
        return batch
