from data.models import Batch
import pytest


class TestBatchModel:
    pytestmark = pytest.mark.django_db

    def test_disagreement_sentences_in_db(self):
        batch = Batch.objects.filter(pk=2).first()
        assert len(batch.discuss_disagreement_sentences) == 4
