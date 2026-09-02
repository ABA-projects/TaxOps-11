"""Tests para las tools on-demand de agentes contables en services/chatbot.py."""
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import services.chatbot as chatbot  # noqa: E402
from services.chatbot import _es_reciente  # noqa: E402


def test_es_reciente_hoy_es_fresco():
    assert _es_reciente(date.today()) is True


def test_es_reciente_dentro_del_limite():
    assert _es_reciente(date.today() - timedelta(days=7)) is True


def test_es_reciente_fuera_del_limite():
    assert _es_reciente(date.today() - timedelta(days=8)) is False


def test_es_reciente_limite_configurable():
    assert _es_reciente(date.today() - timedelta(days=10), dias=30) is True


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


def test_tool_vencimientos_devuelve_cache_si_hay_evento_proximo(monkeypatch):
    eventos = [
        {"id": "v1", "fecha": (date.today() + timedelta(days=10)).isoformat(), "titulo": "IVA bimestral"},
    ]
    monkeypatch.setattr(chatbot, "_leer_calendario", lambda: eventos)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda *a, **k: disparos.append(a) or "job-x")

    resultado = chatbot._tool_consultar_vencimientos_tributarios()

    assert "IVA bimestral" in resultado
    assert disparos == []


def test_tool_vencimientos_dispara_si_no_hay_evento_en_30_dias(monkeypatch):
    eventos = [
        {"id": "v1", "fecha": (date.today() + timedelta(days=60)).isoformat(), "titulo": "muy lejos"},
    ]
    monkeypatch.setattr(chatbot, "_leer_calendario", lambda: eventos)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    chatbot._tool_consultar_vencimientos_tributarios()

    assert disparos == ["vencimientos-tributarios"]


def test_tool_vencimientos_dispara_si_calendario_vacio(monkeypatch):
    monkeypatch.setattr(chatbot, "_leer_calendario", lambda: [])
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda agente, **k: disparos.append(agente) or "job-x")

    chatbot._tool_consultar_vencimientos_tributarios()

    assert disparos == ["vencimientos-tributarios"]


def test_tool_buscar_leads_devuelve_cache_si_existen(monkeypatch):
    leads = [
        {"empresa": "Restaurante A", "sector": "restaurantes", "ciudad": "Medellín",
         "contacto": "a@a.com", "fuente_url": "https://a.com", "fecha_generado": date.today()},
    ]
    monkeypatch.setattr(chatbot, "_leads_existentes", lambda sector, ciudad: leads)
    disparos = []
    monkeypatch.setattr(chatbot, "_disparar_agente", lambda *a, **k: disparos.append(a) or "job-x")

    resultado = chatbot._tool_buscar_leads_comerciales("restaurantes", "Medellín")

    assert "Restaurante A" in resultado
    assert disparos == []


def test_tool_buscar_leads_dispara_si_no_existe_esa_combinacion(monkeypatch):
    monkeypatch.setattr(chatbot, "_leads_existentes", lambda sector, ciudad: [])
    disparos = []
    monkeypatch.setattr(
        chatbot, "_disparar_agente",
        lambda agente, overrides=None: disparos.append((agente, overrides)) or "job-x",
    )

    resultado = chatbot._tool_buscar_leads_comerciales("veterinarias", "Bucaramanga")

    assert disparos == [("prospector-clientes-contables", {"sector": "veterinarias", "ciudad": "Bucaramanga"})]
    assert "arrancó" in resultado.lower() or "arranqué" in resultado.lower()


def test_ejecutar_herramienta_despacha_las_4_tools_nuevas(monkeypatch):
    monkeypatch.setattr(chatbot, "_tool_consultar_novedades_dian", lambda: "dian ok")
    monkeypatch.setattr(chatbot, "_tool_consultar_novedades_niif", lambda: "niif ok")
    monkeypatch.setattr(chatbot, "_tool_consultar_vencimientos_tributarios", lambda: "venc ok")
    monkeypatch.setattr(
        chatbot, "_tool_buscar_leads_comerciales",
        lambda sector, ciudad: f"leads {sector} {ciudad} ok",
    )

    assert chatbot._ejecutar_herramienta("consultar_novedades_dian", {}, None) == "dian ok"
    assert chatbot._ejecutar_herramienta("consultar_novedades_niif", {}, None) == "niif ok"
    assert chatbot._ejecutar_herramienta("consultar_vencimientos_tributarios", {}, None) == "venc ok"
    assert chatbot._ejecutar_herramienta(
        "buscar_leads_comerciales", {"sector": "salud", "ciudad": "Cali"}, None
    ) == "leads salud Cali ok"


def test_tools_list_incluye_las_4_nuevas():
    nombres = {t["function"]["name"] for t in chatbot.TOOLS}
    assert {
        "consultar_novedades_dian", "consultar_novedades_niif",
        "consultar_vencimientos_tributarios", "buscar_leads_comerciales",
    } <= nombres
