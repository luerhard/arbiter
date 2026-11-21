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

    def signature(self, annotations: "Iterable[Annotation]") -> Hashable:
        """What one person's annotations of one example amount to, in a form that can be
        compared: two people agree if their signatures are equal."""
        raise NotImplementedError

    def agree(self, signatures: Iterable[Hashable]) -> bool:
        """Whether everyone annotated the example the same way."""
        return len(set(signatures)) <= 1
