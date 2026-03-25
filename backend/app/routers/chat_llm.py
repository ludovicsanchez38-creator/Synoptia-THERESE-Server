"""
Thérèse Server - Chat Send (LLM Streaming)

Endpoint streaming SSE pour envoyer un message et recevoir la réponse LLM.
Dégradation gracieuse si les providers LLM ne sont pas disponibles.
"""

import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import get_owned
from app.config import settings
from app.models.database import get_session
from app.models.entities import Conversation, Message

logger = logging.getLogger(__name__)
router = APIRouter()


# Singletons clients LLM (eviter recreation a chaque requete)
_anthropic_client = None
_openai_client = None
_gemini_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            key = settings.anthropic_api_key
            if key:
                _anthropic_client = anthropic.AsyncAnthropic(api_key=key)
        except ImportError:
            pass
    return _anthropic_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        try:
            import openai
            key = settings.openai_api_key
            if key:
                _openai_client = openai.AsyncOpenAI(api_key=key)
        except ImportError:
            pass
    return _openai_client


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai
            key = settings.google_api_key
            if key:
                _gemini_client = genai.Client(api_key=key)
        except ImportError:
            pass
    return _gemini_client


class ChatSendRequest(BaseModel):
    conversation_id: str
    message: str
    model: str | None = None


async def _get_llm_response(
    messages: list[dict], model: str | None = None
) -> AsyncGenerator[str, None]:
    """Appel LLM avec streaming. Essaie les providers dans l'ordre."""

    # Essayer Anthropic
    try:
        client = _get_anthropic()
        if client:
            model_name = model or settings.claude_model or "claude-sonnet-4-6"
            system_msg = (
                "Tu es Thérèse, une assistante IA professionnelle pour les "
                "collectivités et PME françaises. Réponds en français, "
                "de manière claire et structurée."
            )
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] in ("user", "assistant")
            ]

            async with client.messages.stream(
                model=model_name,
                max_tokens=4096,
                system=system_msg,
                messages=api_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
            return
    except Exception as e:
        logger.warning("Anthropic error: %s", e)

    # Essayer OpenAI
    try:
        client = _get_openai()
        if client:
            model_name = model or "gpt-4o"
            system_msg = {
                "role": "system",
                "content": (
                    "Tu es Thérèse, une assistante IA professionnelle "
                    "pour les collectivités et PME françaises. Réponds en français."
                ),
            }
            api_messages = [system_msg] + [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] in ("user", "assistant")
            ]

            stream = await client.chat.completions.create(
                model=model_name,
                messages=api_messages,
                max_tokens=4096,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
    except Exception as e:
        logger.warning("OpenAI error: %s", e)


    # Essayer Google Gemini
    try:
        client = _get_gemini()
        if client:
            model_name = model if model and ("gemini" in model.lower()) else "gemini-2.0-flash-lite"
            system_msg = (
                "Tu es Therese, une assistante IA professionnelle pour les "
                "collectivites et PME francaises. Reponds en francais, "
                "de maniere claire et structuree."
            )
            response = client.models.generate_content_stream(
                model=model_name,
                contents=[
                    {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in messages
                    if m["role"] in ("user", "assistant")
                ],
                config={"system_instruction": system_msg, "max_output_tokens": 4096},
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            return
    except Exception as e:
        logger.warning("Google Gemini error: %s", e)

    # Essayer Ollama (local)
    try:
        import httpx

        ollama_url = settings.ollama_url or "http://localhost:11434"
        model_name = model or settings.ollama_model or "mistral:7b"

        async with httpx.AsyncClient(timeout=120) as http_client:
            api_messages = [
                {"role": "system", "content": "Tu es Thérèse, une assistante IA. Réponds en français."},
            ] + [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] in ("user", "assistant")
            ]

            async with http_client.stream(
                "POST",
                f"{ollama_url}/api/chat",
                json={"model": model_name, "messages": api_messages, "stream": True},
            ) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                    return
    except Exception as e:
        logger.warning("Ollama error: %s", e)

    # Aucun provider disponible
    yield (
        "Aucun fournisseur LLM configuré. "
        "Ajoutez une clé API (ANTHROPIC_API_KEY, OPENAI_API_KEY) "
        "ou configurez Ollama dans le fichier .env"
    )


@router.post("/send")
async def send_message_stream(
    data: ChatSendRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Envoyer un message et recevoir la réponse LLM en streaming SSE."""
    # Vérifier la conversation
    conversation = await get_owned(session, Conversation, data.conversation_id, current_user)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    # Sauvegarder le message utilisateur
    user_msg = Message(
        conversation_id=data.conversation_id,
        role="user",
        content=data.message,
    )
    session.add(user_msg)
    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    await session.commit()

    # Charger l'historique
    stmt = (
        select(Message)
        .where(Message.conversation_id == data.conversation_id)
        .order_by(Message.created_at)
        .limit(50)
    )
    result = await session.execute(stmt)
    history = result.scalars().all()
    messages = [{"role": m.role, "content": m.content} for m in history]

    # Streaming SSE
    async def generate() -> AsyncGenerator[str, None]:
        full_response: list[str] = []
        try:
            async for chunk in _get_llm_response(messages, data.model):
                full_response.append(chunk)
                sse_data = json.dumps({"type": "chunk", "content": chunk})
                yield f"data: {sse_data}\n\n"
        except Exception as e:
            logger.error("LLM streaming error: %s", e)
            err_data = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {err_data}\n\n"

        # Sauvegarder la réponse complète
        complete_text = "".join(full_response)
        if complete_text:
            try:
                from app.models.database import get_session_context

                async with get_session_context() as save_session:
                    assistant_msg = Message(
                        conversation_id=data.conversation_id,
                        role="assistant",
                        content=complete_text,
                        model=data.model or "default",
                    )
                    save_session.add(assistant_msg)
                    await save_session.commit()
            except Exception as e:
                logger.error("Error saving assistant message: %s", e)

        done_data = json.dumps({"type": "done", "content": ""})
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
