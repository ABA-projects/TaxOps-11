"""Tests para agent_core.py — _groq_chat_with_retry (retry+backoff ante 429 RateLimitError).

Bug real visto en producción el 2026-08-25: los 4 agentes corriendo en paralelo pisaban el
límite compartido de TPM de Groq y el 429 tumbaba el job entero sin reintentar."""
import sys
from pathlib import Path

import httpx
import pytest
from groq import RateLimitError

sys.path.insert(0, str(Path(__file__).parent.parent))
from _shared.agent_core import _groq_chat_with_retry  # noqa: E402


def _rate_limit_error() -> RateLimitError:
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/x"))
    return RateLimitError("rate limited", response=response, body=None)


class _FakeCompletions:
    def __init__(self, fail_times: int, result: str = "ok"):
        self.fail_times = fail_times
        self.calls = 0
        self.result = result

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _rate_limit_error()
        return self.result


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, fail_times: int):
        self.chat = _FakeChat(_FakeCompletions(fail_times))


def test_retries_and_succeeds_after_transient_rate_limit(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)  # no esperar de verdad en el test
    client = _FakeClient(fail_times=2)

    result = _groq_chat_with_retry(client, retries=3, backoff=0.01, model="x", messages=[])

    assert result == "ok"
    assert client.chat.completions.calls == 3


def test_reraises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    client = _FakeClient(fail_times=99)  # nunca se recupera

    with pytest.raises(RateLimitError):
        _groq_chat_with_retry(client, retries=2, backoff=0.01, model="x", messages=[])

    assert client.chat.completions.calls == 3  # intento inicial + 2 reintentos
