import asyncio

async def get_ai_response(prompt: str) -> str:
    # Simple deterministic fallback for cloud stub
    await asyncio.sleep(0)
    return "Heya! Appreciate the message — keen to help. What are your goals?"
