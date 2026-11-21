from .base import ProjectType


class Classification(ProjectType):
    """Labels for the whole text; any number of them, none is a valid answer."""

    key = "classification"

    def signature(self, annotations):
        return frozenset(annotation.label_id for annotation in annotations)
