from types import SimpleNamespace

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
