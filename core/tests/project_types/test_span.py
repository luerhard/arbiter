from django.http import QueryDict
from django.urls import reverse
import pytest

from data.models import ExampleAssignment
from project_types import PROJECT_TYPES
from project_types.span import tokens
from projects.models import BatchPhase

span = PROJECT_TYPES["span"]
TEXT = "The elites 😠 betray us.\n\nWe, the people!"


@pytest.fixture
def example(project_annotation):
    """The example of a span project, with TEXT as its content."""
    project = project_annotation["project"]
    project.project_type = "span"
    project.save()
    example = project_annotation["example"]
    example.content = TEXT
    example.save()
    return example


def offsets(phrase):
    start = TEXT.index(phrase)
    return start, start + len(phrase)


def test_tokens_are_the_words_with_their_punctuation():
    assert [TEXT[start:end] for start, end in tokens(TEXT)] == [
        "The",
        "elites",
        "😠",
        "betray",
        "us.",
        "We,",
        "the",
        "people!",
    ]


@pytest.mark.django_db
def test_validated_value_keeps_spans_on_word_boundaries(example, project_annotation):
    label_a, label_b = (label.id for label in project_annotation["labels"])
    value = [[label_b, *offsets("the people!")], [label_a, *offsets("The elites")]]
    assert span.validated_value(example, value) == sorted(value)
    assert span.validated_value(example, []) == []


@pytest.mark.django_db
def test_validated_value_merges_spans_of_a_label_word_by_word(example, project_annotation):
    label_a, label_b = (label.id for label in project_annotation["labels"])
    value = [
        [label_a, *offsets("The")],
        [label_a, *offsets("elites")],
        [label_a, *offsets("elites 😠")],
        [label_b, *offsets("elites")],  # another label overlaps: stays on its own
    ]
    assert span.validated_value(example, value) == [
        [label_a, *offsets("The elites 😠")],
        [label_b, *offsets("elites")],
    ]


@pytest.mark.django_db
def test_common_value_keeps_the_words_everyone_marked_with_the_same_label(
    example,
    project_annotation,
):
    label_a, label_b = (label.id for label in project_annotation["labels"])
    first = [[label_a, *offsets("The elites 😠 betray")], [label_b, *offsets("the people!")]]
    second = [[label_a, *offsets("elites 😠 betray us.")], [label_b, *offsets("We, the")]]
    assert span.common_value(example, [first, second]) == [
        [label_a, *offsets("elites 😠 betray")],
        [label_b, *offsets("the")],
    ]
    assert span.common_value(example, [first, []]) == []
    assert span.common_value(example, []) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [
        "[]",
        [[1, 2]],
        [[True, 0, 3]],
        [["1", 0, 3]],
        [[999_999_999, 0, 3]],
    ],
)
def test_validated_value_rejects_malformed_spans(example, value):
    with pytest.raises(ValueError, match="span|label"):
        span.validated_value(example, value)


@pytest.mark.django_db
@pytest.mark.parametrize("start_end", [(1, 3), (0, 2), (4, 4), (10, 4)])
def test_validated_value_rejects_spans_off_word_boundaries(example, project_annotation, start_end):
    label = project_annotation["labels"][0].id
    with pytest.raises(ValueError, match="word boundaries"):
        span.validated_value(example, [[label, *start_end]])


@pytest.mark.django_db
def test_saved_spans_compare_and_export(example, project_annotation):
    label_a, label_b = project_annotation["labels"]
    first, second = ExampleAssignment.objects.filter(example=example, phase=BatchPhase.ANNOTATION)
    value = [[label_a.id, *offsets("The elites")], [label_b.id, *offsets("people!")]]
    first.set_user_annotations(value)
    second.set_user_annotations(list(reversed(value)))

    assert span.value(first.annotations.all()) == sorted(value)
    assert span.agree(
        [span.signature(first.annotations.all()), span.signature(second.annotations.all())]
    )
    start, end = offsets("people!")
    assert span.exported_value(first.annotations.all()) == [
        {"label": label_a.name, "start": 0, "end": 10, "text": "The elites"},
        {"label": label_b.name, "start": start, "end": end, "text": "people!"},
    ]


@pytest.mark.django_db
def test_value_from_post_reads_the_json_of_the_editor(example, project_annotation):
    label = project_annotation["labels"][0].id
    post = QueryDict(mutable=True)
    post["value"] = f"[[{label}, 0, 10]]"
    assert span.value_from_post(example, post) == [[label, 0, 10]]
    post["value"] = "not json"
    with pytest.raises(ValueError):  # noqa: PT011
        span.value_from_post(example, post)


@pytest.mark.django_db
def test_annotating_saves_spans_and_refuses_invalid_ones(client, example, project_annotation):
    annotator = project_annotation["annotators"][0]
    label = project_annotation["labels"][0].id
    assignment = ExampleAssignment.objects.get(
        example=example,
        user=annotator,
        phase=BatchPhase.ANNOTATION,
    )
    url = reverse("annotate-assignment", args=(example.batch_id, assignment.id))
    client.force_login(annotator)

    page = client.get(url)
    assert b"span-editor-data" in page.content

    client.post(url, {"value": f"[[{label}, 1, 10]]"})  # not on a word boundary
    assignment.refresh_from_db()
    assert assignment.done is None

    client.post(url, {"value": f"[[{label}, 0, 10]]"})
    assignment.refresh_from_db()
    assert assignment.done is not None
    assert span.value(assignment.annotations.all()) == [[label, 0, 10]]
