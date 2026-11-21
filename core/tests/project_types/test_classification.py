from types import SimpleNamespace

import pytest

from project_types import PROJECT_TYPES

classification = PROJECT_TYPES["classification"]


def signature(*label_ids):
    return classification.signature(SimpleNamespace(label_id=i) for i in label_ids)


def test_label_order_does_not_matter():
    assert signature(1, 2) == signature(2, 1)


def test_agree_on_same_labels():
    assert classification.agree([signature(1, 2), signature(2, 1), signature(1, 2)])


def test_disagree_on_different_labels():
    assert not classification.agree([signature(1), signature(1, 2)])


def test_no_label_is_an_answer_of_its_own():
    assert classification.agree([signature(), signature()])
    assert not classification.agree([signature(1), signature()])


def test_exported_value_is_the_sorted_label_names():
    annotations = [SimpleNamespace(label=SimpleNamespace(name=n)) for n in ["Hate", "Abuse"]]
    assert classification.exported_value(annotations) == ["Abuse", "Hate"]


@pytest.mark.django_db
def test_validated_value_accepts_labels_of_the_project(project_annotation):
    project = project_annotation["project"]
    label_ids = [label.id for label in project_annotation["labels"]]
    assert classification.validated_value(project, label_ids) == label_ids
    assert classification.validated_value(project, []) == []


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["1", [True], ["1"], None, [999_999_999]])
def test_validated_value_rejects_anything_else(project_annotation, value):
    with pytest.raises(ValueError, match="label"):
        classification.validated_value(project_annotation["project"], value)
