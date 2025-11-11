#!/usr/bin/env python3
"""
Quick helper to inspect the last N messages for a contact.

Usage:
    python scripts/list_messages.py --contact massageandyogabydiane --limit 10
"""

from __future__ import annotations

import argparse
from textwrap import shorten

from conversation_store import ConversationStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List recent messages for a contact.")
    parser.add_argument(
        "--contact",
        "-c",
        required=True,
        help="Contact key or identifier (e.g. ig username).",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Number of messages to show (default: 20).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    store = ConversationStore()
    messages = store.get_recent_messages(args.contact, limit=args.limit)
    if not messages:
        print(f"No messages found for contact '{args.contact}'.")
        return

    print(f"Last {len(messages)} messages for '{args.contact}':\n")
    for entry in messages:
        direction = entry.get("direction", "?")
        timestamp = entry.get("timestamp", entry.get("recorded_at", "?"))
        text = entry.get("text") or ""
        if not text and entry.get("raw_payload"):
            text = "<non-text payload>"
        text_short = shorten(text, width=120, placeholder="…")
        print(f"[{timestamp}] {direction:<8} | {text_short}")


if __name__ == "__main__":
    main()

