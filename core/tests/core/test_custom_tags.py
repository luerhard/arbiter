from types import SimpleNamespace

from core.templatetags.custom_tags import batch_range


def test_batch_range_covers_the_batch():
    assert batch_range(SimpleNamespace(batch_number=3)) == "batch_old=2&batch_new=3"
