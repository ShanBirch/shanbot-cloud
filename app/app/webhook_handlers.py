
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
import logging
import json
from datetime import datetime

from utilities import get_user_data, update_manychat_fields
from app.utils.database_utils import get_db_connection, initialize_schema
from typing import Dict, List, Optional, Tuple, Any
import asyncio
import sys
import os

# Add project root to the Python path
project_root = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# Assuming other necessary utilities will be placed in app.utils

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory buffer and task tracking (will be refactored later)
message_buffer: Dict[str, List[Dict]] = {}
scheduled_tasks: Dict[str, asyncio.Task] = {}


def add_to_message_buffer(subscriber_id: str, payload: Dict):
    """Adds a message payload to the buffer for a given subscriber."""
    if subscriber_id not in message_buffer:
        message_buffer[subscriber_id] = []
    message_buffer[subscriber_id].append(payload)
    logger.info(f"Message added to buffer for subscriber_id: {subscriber_id}")


def process_buffered_messages(subscriber_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Processes and combines all buffered messages for a subscriber."""
    if subscriber_id not in message_buffer or not message_buffer[subscriber_id]:
        return None

    payloads = message_buffer.pop(subscriber_id, [])
    if not payloads:
        return None

    # Combine text from all buffered messages
    combined_text = " ".join(p.get('last_input_text', '')
                             for p in payloads).strip()

    # Use the latest payload for metadata
    latest_payload = payloads[-1]

    logger.info(
        f"Processing {len(payloads)} buffered messages for {subscriber_id}. Combined text: '{combined_text}'")
    return combined_text, latest_payload


async def _handle_buffered_messages_for_subscriber(subscriber_id: str, ig_username: str, bg_tasks: BackgroundTasks):
    """The core logic for handling buffered messages and generating a response."""
    # This function will contain the main processing logic.
    # For now, it's a placeholder.
    logger.info(f"Core processing task started for {subscriber_id}")
    await asyncio.sleep(15)  # Simulate processing delay

    combined_text, payload = process_buffered_messages(subscriber_id)
    if not combined_text:
        logger.info(f"No messages to process for {subscriber_id}")
        return

    # This is where we will call get_user_data, get_ai_response, update_analytics_data, etc.
    # For now, just log that we would do it.
    logger.info(
        f"Would generate AI response for '{combined_text}' from {ig_username}")

    # Placeholder for sending response
    await update_manychat_fields(subscriber_id, f"Replying to: {combined_text}")


@router.post("/manychat")
async def process_manychat_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handles incoming webhook requests from ManyChat, buffers them,
    and schedules a background task for processing.
    """
    try:
        data = await request.json()
        subscriber_id = data.get('id')
        ig_username = data.get('ig_username')
        message_text = data.get('last_input_text')

        if not all([subscriber_id, ig_username, message_text]):
            logger.error("Webhook payload missing required fields.")
            raise HTTPException(
                status_code=400, detail="Missing id, ig_username, or last_input_text")

        add_to_message_buffer(subscriber_id, data)

        # Cancel any existing task for this user to reset the timer
        if subscriber_id in scheduled_tasks and not scheduled_tasks[subscriber_id].done():
            scheduled_tasks[subscriber_id].cancel()
            logger.info(f"Cancelled existing task for {subscriber_id}")

        # Schedule the new processing task
        task = asyncio.create_task(_handle_buffered_messages_for_subscriber(
            subscriber_id, ig_username, background_tasks))
        scheduled_tasks[subscriber_id] = task
        logger.info(
            f"Scheduled new processing task for {subscriber_id} ({ig_username})")

        return {"status": "success", "message": "Message received and scheduled for processing."}

    except Exception as e:
        logger.error(f"Error in process_manychat_webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
