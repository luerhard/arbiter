from django.core.management import call_command
import pytest

from discuss import room_state
from projects.management.commands import resetdb


@pytest.fixture
def skip_database_reset(monkeypatch):
    """Keep the shared test database: only the Redis part of resetdb runs."""
    calls = []
    monkeypatch.setattr(resetdb, "call_command", lambda name, **_: calls.append(name))
    return calls


@pytest.mark.django_db
def test_clears_chat_state(skip_database_reset, redis_client, capsys):
    for key in ("room:1", "room:2", "asgi:group:chat_1", "unrelated"):
        redis_client.set(key, "x")

    call_command("resetdb", "--noinput")

    assert skip_database_reset == ["flush", "migrate"]
    assert redis_client.keys("*") == ["unrelated"]
    assert "Redis chat state cleared." in capsys.readouterr().out


@pytest.mark.django_db
def test_redis_outage_only_warns(skip_database_reset, monkeypatch, settings, capsys):
    monkeypatch.setattr(room_state, "REDIS_URL", "redis://localhost:1/0")
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    call_command("resetdb", "--noinput")

    assert skip_database_reset == ["flush", "migrate"]
    assert "Redis could not be cleared" in capsys.readouterr().out
