from django.apps import apps

from .base import ProjectType


class Classification(ProjectType):
    """Labels for the whole text; any number of them, none is a valid answer."""

    key = "classification"
    name = "Labels for the whole text"
    description = "Annotators choose the labels that apply to each text."

    def validated_value(self, example, value):
        if not isinstance(value, list) or not all(
            isinstance(i, int) and not isinstance(i, bool) for i in value
        ):
            msg = f"labels must be a list of label ids, got {value!r}"
            raise ValueError(msg)
        unknown = set(value) - set(example.batch.project.labels.values_list("id", flat=True))
        if unknown:
            msg = f"labels {sorted(unknown)} are not labels of this project"
            raise ValueError(msg)
        return value

    def value_from_post(self, example, post):
        # the label checkboxes; int() raises a ValueError for anything else
        return self.validated_value(example, [int(i) for i in post.getlist("labels")])

    def build_annotations(self, assignment, value):
        Annotation = apps.get_model("data", "Annotation")  # noqa: N806
        labels = assignment.batch.project.labels.filter(pk__in=value)
        return [Annotation(assignment=assignment, label=label) for label in labels]

    def value(self, annotations):
        return sorted(annotation.label_id for annotation in annotations)

    def summary(self, project, value):
        names = project.labels.filter(pk__in=value).order_by("name").values_list("name", flat=True)
        return ", ".join(names) or "no labels"

    def exported_value(self, annotations):
        return sorted(annotation.label.name for annotation in annotations)

    def signature(self, annotations):
        return frozenset(annotation.label_id for annotation in annotations)
