"""
Minimal ManyChat webhook receiver that simply captures incoming messages and
writes them to disk for later review. No AI processing, no scheduling –
perfect for quick manual workflows.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from conversation_store import ConversationStore

logger = logging.getLogger("minimal_webhook")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Minimal ManyChat Webhook")
store = ConversationStore()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_contact_identifier(payload: Dict[str, Any]) -> str:
    # Prefer IG username, then name, then subscriber id.
    for key in ("ig_username", "username", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    subscriber_id = payload.get("id") or payload.get("user_id")
    if subscriber_id:
        return str(subscriber_id)
    return "unknown_contact"


def _extract_subscriber_id(payload: Dict[str, Any]) -> str:
    subscriber_id = payload.get("id") or payload.get("user_id")
    if not subscriber_id:
        raise ValueError("Missing subscriber id in payload")
    return str(subscriber_id)


def _extract_message_text(payload: Dict[str, Any]) -> Optional[str]:
    text = payload.get("last_input_text") or payload.get("text")
    if isinstance(text, str):
        return text
    return None


def _extract_timestamp(payload: Dict[str, Any]) -> str:
    for key in (
        "ig_last_interaction",
        "last_interaction",
        "ig_last_seen",
        "last_seen",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return _iso_now()


@app.get("/health", include_in_schema=False)
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "minimal_manychat_webhook"}


@app.get("/")
async def root() -> Dict[str, str]:
    return {
        "message": "Minimal ManyChat webhook is running.",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/webhook/manychat")
async def receive_manychat(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Capture the webhook payload, record the inbound message, and respond 200.
    """
    try:
        subscriber_id = _extract_subscriber_id(payload)
        contact_identifier = _extract_contact_identifier(payload)
        contact_key = store.register_contact(
            contact_identifier=contact_identifier,
            subscriber_id=subscriber_id,
            display_name=payload.get("name"),
            extra={"raw_payload_keys": list(payload.keys())},
        )

        message_text = _extract_message_text(payload)
        timestamp = _extract_timestamp(payload)

        entry = {
            "direction": "inbound",
            "timestamp": timestamp,
            "recorded_at": _iso_now(),
            "text": message_text,
            "subscriber_id": subscriber_id,
            "raw_payload": payload,
        }
        store.append_message(contact_key, entry)

        logger.info(
            "Stored inbound message contact=%s subscriber_id=%s text=%r",
            contact_key,
            subscriber_id,
            message_text,
        )

        return JSONResponse(
            {
                "status": "stored",
                "contact_key": contact_key,
                "subscriber_id": subscriber_id,
                "text_length": len(message_text or ""),
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to capture ManyChat webhook: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/webhook/manychat/test")
async def test_receive(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Convenience endpoint for local testing (mirrors the main handler).
    """
    return await receive_manychat(payload)  # type: ignore[func-returns-value]
