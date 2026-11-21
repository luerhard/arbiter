from django.apps import apps

from .base import ProjectType


class Classification(ProjectType):
    """Labels for the whole text; any number of them, none is a valid answer."""

    key = "classification"

    def validated_value(self, project, value):
        if not isinstance(value, list) or not all(
            isinstance(i, int) and not isinstance(i, bool) for i in value
        ):
            msg = f"labels must be a list of label ids, got {value!r}"
            raise ValueError(msg)
        unknown = set(value) - set(project.labels.values_list("id", flat=True))
        if unknown:
            msg = f"labels {sorted(unknown)} are not labels of this project"
            raise ValueError(msg)
        return value

    def build_annotations(self, assignment, value):
        Annotation = apps.get_model("data", "Annotation")  # noqa: N806
        labels = assignment.batch.project.labels.filter(pk__in=value)
        return [Annotation(assignment=assignment, label=label) for label in labels]

    def signature(self, annotations):
        return frozenset(annotation.label_id for annotation in annotations)
