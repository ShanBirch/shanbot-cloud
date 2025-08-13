import logging
import re
import json
import requests
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import random
from .config import FORM_CHECK_REQUEST_RESPONSES, MANYCHAT_API_KEY
from .utils import get_melbourne_time_str
from .analytics import update_analytics_data, add_todo_item
from .ai_handler import get_ai_response

logger = logging.getLogger(__name__)

# Global state tracking
message_buffer: Dict[str, List[Dict[str, Any]]] = {}
form_check_pending: Dict[str, bool] = {}
food_analysis_pending: Dict[str, bool] = {}


def add_to_message_buffer(subscriber_id: str, payload: Dict) -> None:
    """Add a message to the buffer for a given user."""
    if subscriber_id not in message_buffer:
        message_buffer[subscriber_id] = []
    message_buffer[subscriber_id].append({
        'payload': payload,
        'timestamp': datetime.now()
    })
    # Log using both subscriber_id and ig_username for clarity
    ig_username = payload.get('ig_username', 'unknown')
    logger.info(
        f"Added message to buffer for user {ig_username} (ID: {subscriber_id})")


def process_buffered_messages(subscriber_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Process any buffered messages for a given user."""
    try:
        user_buffer = message_buffer.get(subscriber_id, [])
        if not user_buffer:
            logger.info(f"No buffered messages found for {subscriber_id}")
            return None

        first_message = user_buffer[0]
        payload = first_message.get('payload', {})
        ig_username = payload.get('ig_username', 'unknown')

        # Get the actual message text from the correct field
        combined_text = ""
        for msg in user_buffer:
            msg_payload = msg.get('payload', {})
            # Use last_input_text from ManyChat payload
            msg_text = msg_payload.get('last_input_text', '')
            if msg_text:
                if combined_text:
                    combined_text += "\n"
                combined_text += msg_text

        if not combined_text:
            logger.error(
                f"No message content found for {ig_username} (ID: {subscriber_id})")
            return None

        logger.info(
            f"Successfully processed buffer for {ig_username} (ID: {subscriber_id}): {combined_text}")
        return combined_text, payload

    except Exception as e:
        logger.error(f"Error processing buffered messages: {str(e)}")
        return None
    finally:
        message_buffer.pop(subscriber_id, None)
        logger.info(f"Cleared message buffer for {subscriber_id}")


def process_media_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Process a media URL and return its type and content."""
    try:
        response = requests.head(url, timeout=5)
        content_type = response.headers.get('Content-Type', '').lower()

        if 'video' in content_type:
            return 'video', url
        elif 'image' in content_type:
            return 'image', url
        elif 'audio' in content_type:
            return 'audio', url
        else:
            logger.warning(f"Unrecognized content type: {content_type}")
            return None, None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking media URL {url}: {e}")
        return None, None


def extract_media_urls(message: str) -> List[str]:
    """Extract media URLs from a message."""
    url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"
    return re.findall(url_pattern, message)


def handle_form_check_request(ig_username: str, subscriber_id: str, first_name: str, last_name: str, message_text: str) -> bool:
    """Handle a form check request."""
    logger.info(f"Form check request detected for {ig_username}")
    form_check_pending[ig_username] = True

    response = random.choice(FORM_CHECK_REQUEST_RESPONSES)
    field_updates = {
        "o1 Response": response,
        "conversation": message_text  # Updated to match ManyChat field name
    }

    try:
        update_manychat_fields(subscriber_id, field_updates)
        ai_response_for_analytics = "AI responded asking user to send video for form check."
        update_analytics_data(
            ig_username,
            message_text,
            ai_response_for_analytics,
            subscriber_id,
            first_name,
            last_name
        )
        logger.info(
            f"Updated analytics data for {ig_username} after form check request.")
        return True
    except Exception as e:
        logger.error(f"Error handling form check request: {e}")
        return False


def update_manychat_fields(subscriber_id: str, field_updates: Dict[str, str]) -> bool:
    """Update custom fields in ManyChat for a subscriber."""
    filtered_updates = {
        k: v for k, v in field_updates.items() if v is not None and v != ""}
    if not filtered_updates:
        logger.info("No valid field updates to send to ManyChat.")
        return True

    field_data = [
        {"field_name": field_name, "field_value": value}
        for field_name, value in filtered_updates.items()
    ]

    data = {
        "subscriber_id": subscriber_id,
        "fields": field_data
    }

    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://api.manychat.com/fb/subscriber/setCustomFields",
            headers=headers,
            json=data,
            timeout=10
        )
        response.raise_for_status()
        logger.info(
            f"Successfully updated ManyChat fields for subscriber {subscriber_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating ManyChat fields: {e}")
        return False
