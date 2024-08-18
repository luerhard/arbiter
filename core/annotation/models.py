from collections import defaultdict

from django.db import models

from core.models import Project
from users.models import User


class Batch(models.Model):
    project = models.ForeignKey(Project, related_name="batches", on_delete=models.CASCADE)
    batch_number = models.SmallIntegerField()
    annotation_done = models.BooleanField(default=False)

    @property
    def discuss_disagreement_sentences(self):
        sentences = (
            self.sentences.prefetch_related("user_annotations")
            .prefetch_related("user_annotations__user")
            .all()
        )
        disagreement_sentences = []
        for sentence in sentences:
            annotation_groups = defaultdict(set)
            user_annotations = sentence.user_annotations.all()
            for user_annotation in user_annotations:
                if user_annotation.is_set:
                    annotation_groups[user_annotation.user].add(user_annotation.label_id)
            annotations = list(annotation_groups.values())
            if not all(annotation == annotations[0] for annotation in annotations):
                disagreement_sentences.append(sentence)

        return disagreement_sentences

    def __str__(self) -> str:
        return f"Batch {self.batch_number}"


class Sentence(models.Model):
    batch = models.ForeignKey(Batch, related_name="sentences", on_delete=models.CASCADE)
    content = models.TextField()

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.content


class Label(models.Model):
    project = models.ForeignKey(Project, related_name="labels", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#007bff")  # Store color codes
    hotkey = models.CharField(max_length=1, null=True, blank=True)

    def __str__(self):
        return self.name


class UserAnnotation(models.Model):
    sentence = models.ForeignKey(
        Sentence,
        related_name="user_annotations",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(User, related_name="user", on_delete=models.CASCADE)
    label = models.ForeignKey(Label, on_delete=models.CASCADE, null=True, blank=True)
    is_set = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user} - {self.label} - {self.is_set} - {self.last_updated}"
