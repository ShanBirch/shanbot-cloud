"""
Minimal ManyChat webhook receiver that simply captures incoming messages and
writes them to disk for later review. No AI processing, no scheduling –
perfect for quick manual workflows.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from conversation_store import ConversationStore

logger = logging.getLogger("minimal_webhook")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Minimal ManyChat Webhook")
store = ConversationStore()
admin_token = os.getenv("WEBHOOK_ADMIN_TOKEN")


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


def _verify_admin_token(token: Optional[str]) -> None:
    if admin_token and token != admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _iter_contact_keys(specific: Optional[str]) -> List[str]:
    if specific:
        key = store._safe_contact_key(specific)  # type: ignore[attr-defined]
        contact_meta = store.get_contact(key)
        if contact_meta is None:
            raise HTTPException(
                status_code=404,
                detail=f"Contact '{specific}' not found.",
            )
        return [key]

    return [key for key, _ in store.list_contacts()]


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


def _require_admin(token: Optional[str]) -> None:
    if admin_token and token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@app.get("/messages")
async def list_messages(
    contact: Optional[str] = Query(
        None, description="Specific contact key/identifier"),
    limit: int = Query(100, ge=1, le=1000,
                       description="Max messages per contact"),
    token: Optional[str] = Query(
        None, description="Admin token if configured"),
) -> Dict[str, Any]:
    """
    Stream stored conversation logs. Requires `WEBHOOK_ADMIN_TOKEN` if it is set.
    When a contact key is provided, only that contact is returned. Otherwise, all
    conversations are included (each truncated to `limit` messages).
    """
    _require_admin(token)

    if contact:
        contact_meta = store.get_contact(contact)
        if not contact_meta:
            raise HTTPException(
                status_code=404, detail=f"Unknown contact '{contact}'")
        messages = store.get_recent_messages(contact, limit=limit)
        return {
            "contacts": [
                {
                    "contact_key": contact,
                    "metadata": contact_meta,
                    "messages": messages,
                }
            ]
        }

    contacts_payload: List[Dict[str, Any]] = []
    for contact_key, meta in store.list_contacts():
        messages = store.get_recent_messages(contact_key, limit=limit)
        contacts_payload.append(
            {
                "contact_key": contact_key,
                "metadata": meta,
                "messages": messages,
            }
        )
    return {"contacts": contacts_payload}


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


@app.get("/webhook/manychat/contacts")
async def list_contacts(token: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    Enumerate known contacts and their stored metadata.
    """
    _verify_admin_token(token)

    contacts = [
        {"contact_key": key, "metadata": metadata}
        for key, metadata in store.list_contacts()
    ]
    return {"count": len(contacts), "contacts": contacts}


@app.get("/webhook/manychat/logs")
async def fetch_logs(
    token: Optional[str] = Query(None),
    contact: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    include_raw: bool = Query(False),
) -> Dict[str, Any]:
    """
    Retrieve recent messages for one or more contacts.

    This endpoint is intended for trusted internal tooling. Protect it by
    configuring the `WEBHOOK_ADMIN_TOKEN` environment variable and passing the
    matching `token` query parameter when requesting logs.
    """

    _verify_admin_token(token)

    contact_keys = _iter_contact_keys(contact)
    results: List[Dict[str, Any]] = []

    for key in contact_keys:
        metadata = store.get_contact(key) or {}
        messages = store.get_recent_messages(key, limit=limit)
        if not include_raw:
            messages = [
                {k: v for k, v in message.items() if k != "raw_payload"}
                for message in messages
            ]
        results.append(
            {
                "contact_key": key,
                "metadata": metadata,
                "messages": messages,
            }
        )

    return {"contacts": results, "count": len(results)}


@app.post("/webhook/manychat/test")
async def test_receive(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Convenience endpoint for local testing (mirrors the main handler).
    """
    return await receive_manychat(payload)  # type: ignore[func-returns-value]
