from .base import ProjectType
from .classification import Classification

PROJECT_TYPES: dict[str, ProjectType] = {
    project_type.key: project_type for project_type in [Classification()]
}


def get_project_type(project) -> ProjectType:  # noqa: ARG001
    """The type of a project. Every project is a classification project until projects
    can choose their type."""
    return PROJECT_TYPES[Classification.key]


__all__ = ["PROJECT_TYPES", "ProjectType", "get_project_type"]
