import re
from urllib.parse import urlencode

from django import template

register = template.Library()


@register.filter
def zip_lists(a, b):
    """zip two iterables together"""
    return zip(a, b, strict=True)


@register.filter
def initials(username: str) -> str:
    """Two characters for an avatar: "jane.doe" -> "JD", "annotator1" -> "A1", "lukas" -> "LU"."""
    name = str(username or "").strip()
    if not name:
        return "?"
    parts = [p for p in re.split(r"[\s._-]+", name) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if len(name) > 1 and name[-1].isdigit():
        return (name[0] + name[-1]).upper()
    return name[:2].upper()


@register.filter
def batch_range(batch) -> str:
    """Query string for the views that compare batches (codebook diff, export), covering this batch:
    {% url 'codebook-diff' codebook_id=codebook.pk %}?{{ batch|batch_range }} -> ?batch_old=2&batch_new=3"""
    return urlencode({"batch_old": batch.batch_number - 1, "batch_new": batch.batch_number})
