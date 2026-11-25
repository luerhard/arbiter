import json
import re

from django.apps import apps

from .base import ProjectType

TOKEN = re.compile(r"\S+")


def tokens(text: str) -> list[tuple[int, int]]:
    """(start, end) of every word: whatever stands between whitespace, punctuation
    included. Spans start and end on these boundaries."""
    return [match.span() for match in TOKEN.finditer(text)]


class Span(ProjectType):
    """Labeled passages of the text; they may overlap. The value is a list of
    [label_id, start, end], character offsets into the text, sorted."""

    key = "span"
    name = "Spans in the text"
    description = "Annotators mark passages in each text and label them."

    def validated_value(self, example, value):
        if not isinstance(value, list) or not all(
            isinstance(span, list)
            and len(span) == 3  # noqa: PLR2004
            and all(isinstance(i, int) and not isinstance(i, bool) for i in span)
            for span in value
        ):
            msg = f"spans must be a list of [label_id, start, end], got {value!r}"
            raise ValueError(msg)
        unknown = {label for label, _, _ in value} - set(
            example.batch.project.labels.values_list("id", flat=True),
        )
        if unknown:
            msg = f"labels {sorted(unknown)} are not labels of this project"
            raise ValueError(msg)
        words = tokens(example.content)
        first = {start: i for i, (start, _) in enumerate(words)}
        last = {end: i for i, (_, end) in enumerate(words)}
        if any(start not in first or end not in last or start >= end for _, start, end in value):
            msg = f"spans must start and end at word boundaries, got {value!r}"
            raise ValueError(msg)

        # spans of one label that overlap or follow each other word by word become one,
        # so the same passage always has the same value
        merged = []
        for label, start, end in sorted(value):
            if merged and merged[-1][0] == label and first[start] <= last[merged[-1][2]] + 1:
                merged[-1][2] = max(merged[-1][2], end)
            else:
                merged.append([label, start, end])
        return merged

    def editor_data(self, example, annotations=()):
        """What the span editor in the browser needs: the words with their offsets and the
        whitespace after them, the labels, and the spans to start from."""
        text = example.content
        words = tokens(text)
        gaps = [start for start, _ in words[1:]] + [len(text)]
        return {
            "tokens": [
                {"text": text[start:end], "start": start, "end": end, "gap": text[end:gap]}
                for (start, end), gap in zip(words, gaps, strict=True)
            ],
            "labels": [
                {"id": label.id, "name": label.name, "color": label.color, "hotkey": label.hotkey}
                for label in example.batch.project.labels.order_by("pk")
            ],
            "spans": self.value(annotations),
        }

    def value_from_post(self, example, post):
        # the span editor posts its spans as JSON; a JSONDecodeError is a ValueError
        return self.validated_value(example, json.loads(post.get("value", "")))

    def build_annotations(self, assignment, value):
        Annotation = apps.get_model("data", "Annotation")  # noqa: N806
        return [
            Annotation(assignment=assignment, label_id=label, start=start, end=end)
            for label, start, end in value
        ]

    def value(self, annotations):
        return sorted([a.label_id, a.start, a.end] for a in annotations)

    def common_value(self, example, values):
        """The words all values mark with the same label, as spans: what everyone agrees
        on word by word, e.g. to start an expert decision from."""
        words = tokens(example.content)
        marked = [
            {
                (label, word)
                for label, start, end in value
                for word in words
                if start <= word[0] and word[1] <= end
            }
            for value in values
        ]
        common = set.intersection(*marked) if marked else set()
        # one span per word; validated_value joins neighbouring words into passages
        return self.validated_value(
            example, [[label, start, end] for label, (start, end) in common]
        )

    def summary(self, project, value):
        if not value:
            return "no spans"
        labels = {label for label, _, _ in value}
        names = project.labels.filter(pk__in=labels).order_by("name").values_list("name", flat=True)
        return f"{len(value)} span{'s' if len(value) > 1 else ''} ({', '.join(names)})"

    def exported_value(self, annotations):
        return [
            {
                "label": a.label.name,
                "start": a.start,
                "end": a.end,
                "text": a.text,
            }
            for a in sorted(annotations, key=lambda a: (a.start, a.end, a.label.name))
        ]

    def signature(self, annotations):
        return frozenset((a.label_id, a.start, a.end) for a in annotations)
