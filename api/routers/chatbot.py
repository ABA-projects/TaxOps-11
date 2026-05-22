"""Chatbot router — asistente contable IA."""
from __future__ import annotations

import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/ask", response_model=ChatResponse)
async def ask(
    body: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    # Inyectar API keys desde config al entorno para que los servicios las lean
    from core.config import get_settings

    s = get_settings()
    for key, val in [
        ("GROQ_API_KEY", s.GROQ_API_KEY),
        ("OPENAI_API_KEY", s.OPENAI_API_KEY),
        ("ANTHROPIC_API_KEY", s.ANTHROPIC_API_KEY),
        ("GOOGLE_API_KEY", s.GOOGLE_API_KEY),
    ]:
        if val:
            os.environ.setdefault(key, val)

    df = pd.DataFrame(body.df_context) if body.df_context else None
    historial = [{"role": m.role, "content": m.content} for m in body.history]

    try:
        from services.chatbot import responder

        content = responder(
            prompt=body.message,
            df=df,
            historial=historial,
            model=body.model,
            provider=body.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error del asistente: {exc}")

    return ChatResponse(content=content, provider=body.provider, model=body.model)


@router.get("/providers")
async def list_providers(_: dict = Depends(get_current_user)) -> dict:
    """Devuelve los proveedores y modelos disponibles."""
    from services.chatbot import PROVIDERS

    return {"providers": PROVIDERS}


@router.post("/contextual")
async def contextual_chat(
    body: ChatRequest,
    _: dict = Depends(get_current_user),
) -> ChatResponse:
    """
    Chatbot con system prompt personalizado.
    Úsalo para los mini-asistentes contextuales de cada módulo.
    """
    from core.config import get_settings
    from services.chatbot import SYSTEM_PROMPT

    s = get_settings()
    groq_key = s.GROQ_API_KEY
    if not groq_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY no configurada en el servidor.")

    system = body.system_prompt or SYSTEM_PROMPT
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})

    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model=body.model,
            messages=messages,
            max_tokens=1500,
        )
        content = resp.choices[0].message.content or "Sin respuesta."
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error del asistente: {exc}")

    return ChatResponse(content=content, provider="groq", model=body.model)
