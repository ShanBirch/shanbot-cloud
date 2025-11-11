"""
Lightweight utilities for storing and retrieving conversation logs.

Each contact gets a JSONL file under the configured log directory that records
both inbound and outbound messages. An additional `_contacts.json` file keeps
track of contact metadata (subscriber id, display name, etc.) so we can look
up the ManyChat subscriber id when sending replies.
"""

from __future__ import annotations

import json
import os
import re
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class ConversationStore:
    """Persist conversation history and contact metadata on disk."""

    DEFAULT_BASE_DIR = Path("conversation_logs")

    def __init__(self, base_dir: Optional[os.PathLike[str] | str] = None) -> None:
        env_base = os.getenv("CONVERSATION_LOG_DIR")
        base_path = Path(base_dir or env_base or self.DEFAULT_BASE_DIR)
        base_path.mkdir(parents=True, exist_ok=True)
        self.base_dir: Path = base_path
        self.contacts_index_path = self.base_dir / "_contacts.json"
        if not self.contacts_index_path.exists():
            self.contacts_index_path.write_text("{}", encoding="utf-8")

    # --------------------------------------------------------------------- #
    # Contact helpers
    # --------------------------------------------------------------------- #
    def _load_contacts_index(self) -> Dict[str, Dict[str, Any]]:
        try:
            return json.loads(self.contacts_index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupt index – back it up and start fresh
            backup_path = self.contacts_index_path.with_suffix(".corrupt.json")
            self.contacts_index_path.replace(backup_path)
            self.contacts_index_path.write_text("{}", encoding="utf-8")
            return {}

    def _write_contacts_index(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.contacts_index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _safe_contact_key(raw: str) -> str:
        """Turn a contact identifier into a filesystem-safe slug."""
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw.strip().lower())
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "unknown_contact"

    def register_contact(
        self,
        contact_identifier: str,
        subscriber_id: str,
        display_name: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Ensure the contact exists in the index and store basic metadata.

        Returns the filesystem-safe contact key used for the JSONL log file.
        """
        key = self._safe_contact_key(contact_identifier or subscriber_id)
        contacts = self._load_contacts_index()
        contact_entry = contacts.get(key, {})
        contact_entry.update(
            {
                "contact_identifier": contact_identifier,
                "subscriber_id": subscriber_id,
                "display_name": display_name or contact_identifier or subscriber_id,
            }
        )
        if extra:
            contact_entry.update(extra)
        contacts[key] = contact_entry
        self._write_contacts_index(contacts)
        return key

    def get_contact(self, contact_key: str) -> Optional[Dict[str, Any]]:
        contacts = self._load_contacts_index()
        key = self._safe_contact_key(contact_key)
        return contacts.get(key)

    def list_contacts(self) -> List[Tuple[str, Dict[str, Any]]]:
        contacts = self._load_contacts_index()
        return sorted(contacts.items(), key=lambda kv: kv[0])

    # --------------------------------------------------------------------- #
    # Message logging helpers
    # --------------------------------------------------------------------- #
    def _contact_log_path(self, contact_key: str) -> Path:
        filename = f"{self._safe_contact_key(contact_key)}.jsonl"
        return self.base_dir / filename

    def append_message(self, contact_key: str, entry: Dict[str, Any]) -> None:
        """
        Append a JSON message entry to the contact log.

        The entry should already include the required fields (direction, text, etc.).
        """
        log_path = self._contact_log_path(contact_key)
        with log_path.open("a", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
            fh.write("\n")

    def get_recent_messages(
        self, contact_key: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Return the last `limit` messages for the contact, ordered newest -> oldest.
        """
        log_path = self._contact_log_path(contact_key)
        if not log_path.exists():
            return []

        buffer: deque[Dict[str, Any]] = deque(maxlen=limit)
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    buffer.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Return newest first
        return list(reversed(buffer))


__all__ = ["ConversationStore"]

