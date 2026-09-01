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


from datetime import timedelta
from unittest.mock import MagicMock

import services.chatbot as chatbot  # noqa: E402


def test_disparar_agente_encola_sqs_y_devuelve_job_id(monkeypatch):
    fake_sqs = MagicMock()
    monkeypatch.setattr(chatbot.boto3, "client", lambda *a, **k: fake_sqs)
    monkeypatch.setenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/q")

    job_id = chatbot._disparar_agente("dian-monitor")

    assert job_id
    fake_sqs.send_message.assert_called_once()
    kwargs = fake_sqs.send_message.call_args.kwargs
    assert kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123/q"
    import json
    body = json.loads(kwargs["MessageBody"])
    assert body == {"tipo": "agente_contable", "agente": "dian-monitor", "job_id": job_id, "overrides": {}}


def test_tool_consultar_novedades_dian_devuelve_cache_si_fresco(monkeypatch):
    reciente = {
        "tipo": "dian", "titulo": "Novedades DIAN — semana del 2026-08-20",
        "resumen": "Resumen de prueba", "fecha_generado": date.today(),
    }
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: reciente)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda *a, **k: disparos.append(a) or "job-x")

    resultado = chatbot._tool_consultar_novedades_dian()

    assert "Resumen de prueba" in resultado
    assert disparos == []  # no disparó nada, el cache estaba fresco


def test_tool_consultar_novedades_dian_dispara_si_viejo(monkeypatch):
    vieja = {
        "tipo": "dian", "titulo": "vieja", "resumen": "vieja",
        "fecha_generado": date.today() - timedelta(days=30),
    }
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: vieja)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    resultado = chatbot._tool_consultar_novedades_dian()

    assert disparos == ["dian-monitor"]
    assert "arrancó" in resultado.lower() or "arranqué" in resultado.lower()


def test_tool_consultar_novedades_dian_dispara_si_no_existe(monkeypatch):
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: None)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    chatbot._tool_consultar_novedades_dian()

    assert disparos == ["dian-monitor"]


def test_tool_consultar_novedades_niif_usa_tipo_niif(monkeypatch):
    consultados = []
    monkeypatch.setattr(chatbot, "_ultima_novedad", lambda tipo: consultados.append(tipo) or None)
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: "job-x")

    chatbot._tool_consultar_novedades_niif()

    assert consultados == ["niif"]
