#!/usr/bin/env python3
"""
Send up to three text messages to a contact via ManyChat and log the outbound
payload locally. The script uses the stored subscriber id saved by the minimal
webhook service.

Usage:
    python scripts/send_message.py --contact massageandyogabydiane "Hey legend" "Meal plan's up" "Sing out if you need tweaks"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import List

import httpx

from conversation_store import ConversationStore

MANYCHAT_SEND_URL = os.getenv(
    "MANYCHAT_SEND_URL", "https://api.manychat.com/sending/sendContent"
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send 1-3 text chunks to a contact via ManyChat."
    )
    parser.add_argument(
        "--contact",
        "-c",
        required=True,
        help="Contact key or identifier (e.g. ig username).",
    )
    parser.add_argument(
        "message_chunks",
        nargs="+",
        help="Text chunks to send (1-3). Provide each chunk as a separate argument.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload without sending it.",
    )
    return parser


def send_messages(contact_key: str, chunks: List[str], dry_run: bool = False) -> None:
    if not (1 <= len(chunks) <= 3):
        raise ValueError("Provide between 1 and 3 message chunks.")

    api_key = os.getenv("MANYCHAT_API_KEY")
    if not api_key:
        raise RuntimeError("Missing MANYCHAT_API_KEY environment variable.")

    store = ConversationStore()
    contact_meta = store.get_contact(contact_key)
    if not contact_meta:
        raise RuntimeError(f"Unknown contact '{contact_key}'. Run list_messages first.")

    subscriber_id = contact_meta.get("subscriber_id")
    if not subscriber_id:
        raise RuntimeError(f"No subscriber_id stored for contact '{contact_key}'.")

    payload = {
        "subscriber_id": subscriber_id,
        "messages": [{"type": "text", "text": chunk} for chunk in chunks],
    }

    if dry_run:
        print("Dry run – not sending. Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(MANYCHAT_SEND_URL, json=payload, headers=headers)

    if response.status_code >= 400:
        raise RuntimeError(
            f"ManyChat API error {response.status_code}: {response.text}"
        )

    resp_body = response.json()
    log_entry = {
        "direction": "outbound",
        "timestamp": iso_now(),
        "recorded_at": iso_now(),
        "text_chunks": chunks,
        "subscriber_id": subscriber_id,
        "api_response": resp_body,
    }
    store.append_message(contact_key, log_entry)

    print(f"Sent {len(chunks)} message chunk(s) to {contact_key} (subscriber {subscriber_id}).")
    print(f"ManyChat response: {json.dumps(resp_body, ensure_ascii=False)}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        send_messages(args.contact, args.message_chunks, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

