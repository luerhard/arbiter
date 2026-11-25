from .base import ProjectType
from .classification import Classification
from .span import Span

PROJECT_TYPES: dict[str, ProjectType] = {
    project_type.key: project_type for project_type in [Classification(), Span()]
}


def get_project_type(project) -> ProjectType:
    """The type of a project, see Project.project_type."""
    return PROJECT_TYPES[project.project_type]


__all__ = ["PROJECT_TYPES", "ProjectType", "get_project_type"]
