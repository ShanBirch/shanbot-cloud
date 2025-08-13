from datetime import datetime, timezone
import pytz
import logging
from typing import Dict, List, Optional, Tuple
import json
import os

logger = logging.getLogger(__name__)


def get_melbourne_time_str() -> str:
    """Get current Melbourne time with error handling."""
    try:
        melbourne_tz = pytz.timezone('Australia/Melbourne')
        current_time = datetime.now(melbourne_tz)
        return current_time.strftime("%Y-%m-%d %I:%M %p AEST")
    except Exception as e:
        logger.error(f"Error getting Melbourne time: {e}")
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def split_response_into_messages(text: str) -> List[str]:
    """Split response text into up to 3 messages of roughly equal length."""
    if len(text) <= 150:
        return [text]

    sentences = text.split('. ')
    if len(sentences) <= 2:
        return sentences

    result = []
    current_message = ""
    target_length = len(text) / 3

    for sentence in sentences:
        if len(current_message) + len(sentence) <= target_length or not current_message:
            if current_message:
                current_message += ". "
            current_message += sentence
        else:
            result.append(current_message + ".")
            current_message = sentence

        if len(result) == 2:
            result.append(current_message + ". " +
                          ". ".join(sentences[sentences.index(sentence)+1:]))
            break

    if current_message and len(result) < 3:
        result.append(current_message + ".")

    return result


def format_conversation_history(history_list: List[Dict[str, str]]) -> str:
    """Formats the conversation history list into a readable string."""
    formatted_lines = []
    for entry in history_list:
        timestamp = entry.get("timestamp", "")
        msg_type = entry.get("type", "unknown").capitalize()
        text = entry.get("text", "")
        try:
            dt_object = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00"))
            formatted_ts = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            formatted_ts = timestamp

        formatted_lines.append(f"{formatted_ts} [{msg_type}]: {text}")
    return "\n".join(formatted_lines)


def clean_and_dedupe_history(history_list: List[Dict[str, str]], max_items: int = 40) -> List[Dict[str, str]]:
    """Normalize, sort, and de-duplicate conversation history for prompting.
    - Removes empty text
    - Normalizes sender/type to lower
    - Dedupes by (sender/type, text, timestamp to second)
    - Keeps the last max_items
    """
    if not history_list:
        return []

    normalized: List[Dict[str, str]] = []
    for msg in history_list:
        text = (msg.get('text') or msg.get('message') or '').strip()
        if not text:
            continue
        sender = (msg.get('sender') or msg.get(
            'type') or 'unknown').strip().lower()
        ts_raw = (msg.get('timestamp') or '').strip()
        ts_norm = ts_raw.split('+')[0].split('.')[0] if ts_raw else ''
        normalized.append({'text': text, 'timestamp': ts_norm,
                          'type': sender, 'sender': sender})

    try:
        normalized.sort(key=lambda m: m.get('timestamp') or '')
    except Exception:
        pass

    seen = set()
    deduped: List[Dict[str, str]] = []
    for m in normalized:
        key = (m['sender'], m['text'], m['timestamp'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    if len(deduped) > max_items:
        deduped = deduped[-max_items:]
    return deduped


def get_response_time_bucket(time_diff_seconds: float) -> str:
    """Convert time difference to ManyChat response time bucket."""
    if time_diff_seconds <= 120:
        return "response time is 0-2minutes"
    elif time_diff_seconds <= 300:
        return "response time is 2-5 minutes"
    elif time_diff_seconds <= 600:
        return "response time is 5-10 minutes"
    elif time_diff_seconds <= 1200:
        return "response time is 10-20 minutes"
    elif time_diff_seconds <= 1800:
        return "response time is 20-30 minutes"
    elif time_diff_seconds <= 3600:
        return "response time is 30-60 minutes"
    elif time_diff_seconds <= 7200:
        return "response time is 1-2 Hours"
    elif time_diff_seconds <= 18000:
        return "response time is 2-5 hours"
    else:
        return "response time is Above 5 Hours"
