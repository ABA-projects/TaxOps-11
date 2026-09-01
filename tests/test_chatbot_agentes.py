"""Tests para las tools on-demand de agentes contables en services/chatbot.py."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.chatbot import _es_reciente  # noqa: E402


def test_es_reciente_hoy_es_fresco():
    assert _es_reciente(date.today()) is True


def test_es_reciente_dentro_del_limite():
    assert _es_reciente(date.today() - timedelta(days=7)) is True


def test_es_reciente_fuera_del_limite():
    assert _es_reciente(date.today() - timedelta(days=8)) is False


def test_es_reciente_limite_configurable():
    assert _es_reciente(date.today() - timedelta(days=10), dias=30) is True
