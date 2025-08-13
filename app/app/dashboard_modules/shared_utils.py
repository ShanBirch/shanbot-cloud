"""
Shared Utilities Module
Contains common functions used across multiple dashboard modules
"""

import streamlit as st
import json
import logging
from datetime import datetime
import google.generativeai as genai

# Configure logging
logger = logging.getLogger(__name__)

# Gemini configuration
try:
    GEMINI_API_KEY = st.secrets["general"]["GEMINI_API_KEY"]
except (KeyError, FileNotFoundError):
    GEMINI_API_KEY = "AIzaSyAH6467EocGBwuMi-oDLawrNyCKjPHHmN8"

# Gemini model configuration (primary set to flash-lite)
GEMINI_MODEL_PRO = "gemini-2.5-flash-lite"
GEMINI_MODEL_FLASH_LITE_PREVIEW = "gemini-2.5-flash-lite-preview-06-17"
GEMINI_MODEL_FLASH_LITE = "gemini-2.0-flash-lite"
GEMINI_MODEL_FLASH = "gemini-2.0-flash-thinking-exp-01-21"
GEMINI_MODEL_FLASH_STANDARD = "gemini-2.0-flash"

# Configure Gemini
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY" and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini configured successfully with 5-fallback system.")
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}")


def call_gemini_with_retry_sync(model_name: str, prompt: str, retry_count: int = 0) -> str:
    """
    Synchronous version of call_gemini_with_retry with 5-model fallback system.

    Args:
        model_name: The Gemini model to use
        prompt: The prompt to send
        retry_count: Current retry attempt (for internal use)

    Returns:
        str: Generated response text
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.warning(f"Model {model_name} failed: {str(e)}")

        # Fallback chain: Pro -> Flash Lite Preview -> Flash Lite -> Flash -> Flash Standard
        if model_name == GEMINI_MODEL_PRO:
            logger.info("Falling back from Pro to Flash Lite Preview model")
            return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH_LITE_PREVIEW, prompt, retry_count + 1)
        elif model_name == GEMINI_MODEL_FLASH_LITE_PREVIEW:
            logger.info(
                "Falling back from Flash Lite Preview to Flash Lite model")
            return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH_LITE, prompt, retry_count + 1)
        elif model_name == GEMINI_MODEL_FLASH_LITE:
            logger.info("Falling back from Flash Lite to original Flash model")
            return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
        elif model_name == GEMINI_MODEL_FLASH:
            logger.info("Falling back from Flash to Flash Standard model")
            return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH_STANDARD, prompt, retry_count + 1)
        else:
            # All models failed
            logger.error(
                f"All Gemini models failed for prompt: {prompt[:100]}...")
            raise Exception(f"All Gemini models failed: {str(e)}")


def queue_message_for_followup(username, message, topic):
    """Queue a message for follow-up sending"""
    # Initialize message queue if it doesn't exist
    if 'message_queue' not in st.session_state:
        st.session_state.message_queue = []

    # Create message object
    message_obj = {
        'username': username,
        'message': message,
        'topic': topic,
        'timestamp': datetime.now().isoformat()
    }

    # Add to queue
    st.session_state.message_queue.append(message_obj)
    logger.info(f"Message queued for {username}: {topic}")

    # Auto-add to conversation history for check-ins
    if topic == "Check-in":
        try:
            from dashboard_sqlite_utils import add_message_to_history
            add_message_to_history(username, 'ai', message)
            logger.info(
                f"Check-in message added to conversation history for {username}")
        except Exception as e:
            logger.error(
                f"Failed to add check-in message to history for {username}: {e}")


def save_followup_queue():
    """Save the follow-up queue to a file for the follow-up manager"""
    queue_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\followup_queue.json"
    try:
        with open(queue_file, 'w') as f:
            json.dump({
                'messages': st.session_state.message_queue,
                'created_at': datetime.now().isoformat()
            }, f, indent=2)
        logger.info(f"Followup queue saved to {queue_file}")
        return True
    except Exception as e:
        st.error(f"Error saving follow-up queue: {e}")
        logger.error(f"Error saving followup_queue.json: {e}", exc_info=True)
        return False


def get_user_topics(user_data_metrics):
    """Get conversation topics from user's metrics data (loaded from SQLite)."""
    try:
        # First try conversation_topics_json (original format)
        topics_json_str = user_data_metrics.get('conversation_topics_json')
        if topics_json_str:
            try:
                topics = json.loads(topics_json_str)
                if isinstance(topics, list) and topics:
                    # Filter out any empty or None topics
                    filtered_topics = [
                        topic for topic in topics if topic and not str(topic).startswith('**')]
                    if filtered_topics:
                        return filtered_topics
            except json.JSONDecodeError:
                pass  # Continue to other methods

        # Next try conversation_topics at root level (Instagram analyzer format)
        conversation_topics = user_data_metrics.get('conversation_topics')
        if isinstance(conversation_topics, list) and conversation_topics:
            filtered_topics = [topic for topic in conversation_topics if topic and not str(
                topic).startswith('**')]
            if filtered_topics:
                return filtered_topics

        # Finally try in client_analysis structure
        client_analysis = user_data_metrics.get('client_analysis', {})
        if isinstance(client_analysis, dict):
            topics_from_analysis = client_analysis.get(
                'conversation_topics', [])
            if isinstance(topics_from_analysis, list) and topics_from_analysis:
                filtered_topics = [topic for topic in topics_from_analysis if topic and not str(
                    topic).startswith('**')]
                if filtered_topics:
                    return filtered_topics

        logger.warning(
            f"No valid conversation topics found for user {user_data_metrics.get('ig_username')}")
        return []

    except Exception as e:
        logger.error(
            f"Unexpected error in get_user_topics for {user_data_metrics.get('ig_username')}: {e}", exc_info=True)
        return []
