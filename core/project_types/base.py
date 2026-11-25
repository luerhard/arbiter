from collections.abc import Hashable
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.models import Annotation


class ProjectType:
    """What an annotation is in one type of project, e.g. labels for the whole text or
    labeled spans. Everything that depends on the type of project goes through this
    class, so the phases (annotation, discussion, expert decision) work the same for all
    of them."""

    key: str = ""
    # shown when creating a project
    name: str = ""
    description: str = ""

    def validated_value(self, example, value):
        """value as a client sent it, checked to be a valid answer for this example;
        raises ValueError otherwise."""
        raise NotImplementedError

    def editor_data(self, example, annotations=()) -> dict | None:  # noqa: ARG002
        """What the editor in the browser (cotton/span_editor.html) needs for an example,
        starting from these annotations; None for a type that is annotated with the label
        checkboxes instead."""
        return None

    def value_from_post(self, example, post):
        """The validated value a form in the browser posted (see validated_value)."""
        raise NotImplementedError

    def build_annotations(self, assignment, value) -> "list[Annotation]":
        """The annotations (not saved yet) for what one person chose for one example; for
        classification, value is a list of label ids."""
        raise NotImplementedError

    def value(self, annotations: "Iterable[Annotation]"):
        """One person's annotations of one example as the value build_annotations takes,
        e.g. to show them in the browser again."""
        raise NotImplementedError

    def summary(self, project, value) -> str:
        """A value in a few words, e.g. for the chat when someone saves their decision."""
        raise NotImplementedError

    def exported_value(self, annotations: "Iterable[Annotation]"):
        """One person's annotations of one example as JSON data, for the export and the
        decision log in the codebook history."""
        raise NotImplementedError

    def signature(self, annotations: "Iterable[Annotation]") -> Hashable:
        """What one person's annotations of one example amount to, in a form that can be
        compared: two people agree if their signatures are equal."""
        raise NotImplementedError

    def agree(self, signatures: Iterable[Hashable]) -> bool:
        """Whether everyone annotated the example the same way."""
        return len(set(signatures)) <= 1
