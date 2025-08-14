from datetime import datetime, timezone, timedelta

def get_melbourne_time_str() -> str:
    # Melbourne is UTC+10 or +11; use +10 as safe default for stub
    return (datetime.utcnow() + timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")

def format_conversation_history(history):
    # history is expected to be list of dicts or strings
    lines = []
    for item in history or []:
        if isinstance(item, dict):
            sender = item.get("sender") or item.get("role") or "user"
            msg = item.get("message") or item.get("content") or ""
            lines.append(f"{sender.capitalize()}: {msg}")
        else:
            lines.append(str(item))
    return "\n".join(lines)

def clean_and_dedupe_history(history, max_items: int = 40):
    # Basic stub: truncate to last max_items
    if not history:
        return []
    # Remove exact duplicates while preserving order
    seen = set()
    cleaned = []
    for item in history:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned[-max_items:]
