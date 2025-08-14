# Minimal cloud stub for webhook_handlers used by trainerize_action_handler and others
from typing import Any, Dict, Optional
import asyncio


def get_user_data(ig_username: str) -> Dict[str, Any]:
    return {"ig_username": ig_username, "status": "active"}


def update_analytics_data(*args, **kwargs) -> None:
    return None


def call_gemini_with_retry(prompt: str, model: Optional[str] = None, *args, **kwargs) -> str:
    # Deterministic short reply; keep it under 15 words to match your rules
    return "Heya! Keen to help. Tell me your goals?"

# Async convenience wrapper if callers await
async def a_call_gemini_with_retry(prompt: str, model: Optional[str] = None, *args, **kwargs) -> str:
    await asyncio.sleep(0)
    return call_gemini_with_retry(prompt, model, *args, **kwargs)

async def send_manychat_message(subscriber_id: str, text: str) -> None:
    # No-op stub for cloud runtime
    return None
