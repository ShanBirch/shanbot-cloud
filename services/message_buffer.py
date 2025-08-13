"""
Message Buffer Service
=====================
Handles message buffering and delayed processing for ManyChat webhooks.
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from functools import partial

logger = logging.getLogger("shanbot_buffer")

# Global message buffering state
manychat_message_buffer: Dict[str, List[Dict]] = defaultdict(list)
manychat_last_message_time: Dict[str, float] = {}
user_buffer_task_scheduled: Dict[str, bool] = defaultdict(bool)
user_buffer_tasks: Dict[str, asyncio.Task] = {}

# Buffer configuration
BUFFER_WINDOW = 60.0  # seconds


class MessageBuffer:
    """Handles message buffering and processing for ManyChat webhooks."""

    @staticmethod
    def add_to_message_buffer(subscriber_id: str, message_data: Dict) -> None:
        """Add message to buffer and schedule processing if needed."""
        try:
            current_time = time.time()

            # Add message to buffer
            manychat_message_buffer[subscriber_id].append(message_data)
            manychat_last_message_time[subscriber_id] = current_time

            logger.info(
                f"[Buffer] Added message for {subscriber_id}. Buffer size: {len(manychat_message_buffer[subscriber_id])}")

            # Schedule processing if not already scheduled
            if not user_buffer_task_scheduled[subscriber_id]:
                MessageBuffer._schedule_delayed_processing(subscriber_id)

        except Exception as e:
            logger.error(
                f"[Buffer] Error adding message for {subscriber_id}: {e}")

    @staticmethod
    def _schedule_delayed_processing(subscriber_id: str) -> None:
        """Schedule delayed processing for a user."""
        try:
            user_buffer_task_scheduled[subscriber_id] = True

            # Cancel existing task if any
            if subscriber_id in user_buffer_tasks:
                user_buffer_tasks[subscriber_id].cancel()

            # Create new delayed task
            loop = asyncio.get_event_loop()
            task = loop.create_task(
                MessageBuffer._delayed_message_processing(subscriber_id))
            user_buffer_tasks[subscriber_id] = task

            logger.info(
                f"[Buffer] Scheduled delayed processing for {subscriber_id}")

        except Exception as e:
            logger.error(
                f"[Buffer] Error scheduling processing for {subscriber_id}: {e}")

    @staticmethod
    async def _delayed_message_processing(subscriber_id: str) -> None:
        """Process buffered messages after delay."""
        try:
            # Wait for buffer window
            await asyncio.sleep(BUFFER_WINDOW)

            # Check if more messages arrived recently
            current_time = time.time()
            last_message_time = manychat_last_message_time.get(
                subscriber_id, 0)

            if current_time - last_message_time < BUFFER_WINDOW:
                # More messages arrived, schedule another processing
                logger.info(
                    f"[Buffer] More messages arrived for {subscriber_id}, rescheduling")
                MessageBuffer._schedule_delayed_processing(subscriber_id)
                return

            # Process buffered messages
            await MessageBuffer.process_buffered_messages(subscriber_id)

        except asyncio.CancelledError:
            logger.info(f"[Buffer] Processing cancelled for {subscriber_id}")
        except Exception as e:
            logger.error(
                f"[Buffer] Error in delayed processing for {subscriber_id}: {e}")
        finally:
            user_buffer_task_scheduled[subscriber_id] = False
            if subscriber_id in user_buffer_tasks:
                del user_buffer_tasks[subscriber_id]

    @staticmethod
    async def process_buffered_messages(subscriber_id: str) -> None:
        """Process all buffered messages for a user."""
        try:
            messages = manychat_message_buffer.get(subscriber_id, [])

            if not messages:
                logger.info(
                    f"[Buffer] No messages to process for {subscriber_id}")
                return

            logger.info(
                f"[Buffer] Processing {len(messages)} buffered messages for {subscriber_id}")

            # Clear the buffer
            manychat_message_buffer[subscriber_id] = []

            # Process messages
            await MessageBuffer._handle_buffered_messages_for_subscriber(subscriber_id, messages)

        except Exception as e:
            logger.error(
                f"[Buffer] Error processing buffered messages for {subscriber_id}: {e}")

    @staticmethod
    async def _handle_buffered_messages_for_subscriber(subscriber_id: str, messages: List[Dict]) -> None:
        """Handle buffered messages for a specific subscriber."""
        try:
            if not messages:
                return

            # Use the latest message for processing
            latest_message = messages[-1]

            # Combine all message texts for context
            combined_text = " ".join([msg.get('text', '')
                                     for msg in messages if msg.get('text')])
            if combined_text:
                latest_message['text'] = combined_text

            # Extract user info from latest message
            ig_username = latest_message.get('ig_username', '')
            subscriber_id = latest_message.get('subscriber_id', '')
            first_name = latest_message.get('first_name', '')
            last_name = latest_message.get('last_name', '')
            user_message_timestamp_iso = latest_message.get(
                'user_message_timestamp_iso', '')

            # Debug logging to see what we have
            logger.info(
                f"[Buffer] Processing combined message for {ig_username}: '{combined_text[:100]}...' (subscriber_id: '{subscriber_id}')")

            # Import and run core processing
            from action_handlers.core_action_handler import CoreActionHandler
            await CoreActionHandler.run_core_processing_after_buffer(
                ig_username, combined_text, subscriber_id, first_name, last_name, user_message_timestamp_iso
            )

        except Exception as e:
            logger.error(f"[Buffer] Error handling buffered messages: {e}")

    @staticmethod
    def get_response_time_bucket(response_time_seconds: float) -> str:
        """Get response time bucket for analytics."""
        if response_time_seconds <= 5:
            return "0-5s"
        elif response_time_seconds <= 10:
            return "6-10s"
        elif response_time_seconds <= 30:
            return "11-30s"
        elif response_time_seconds <= 60:
            return "31-60s"
        else:
            return "60s+"

    @staticmethod
    def get_buffer_stats(subscriber_id: str) -> Dict[str, Any]:
        """Get buffer statistics for a user."""
        return {
            "buffer_size": len(manychat_message_buffer.get(subscriber_id, [])),
            "last_message_time": manychat_last_message_time.get(subscriber_id, 0),
            "processing_scheduled": user_buffer_task_scheduled.get(subscriber_id, False),
            "has_active_task": subscriber_id in user_buffer_tasks
        }

    @staticmethod
    def clear_user_buffer(subscriber_id: str) -> None:
        """Clear buffer for a specific user."""
        try:
            # Cancel any scheduled processing
            if subscriber_id in user_buffer_tasks:
                user_buffer_tasks[subscriber_id].cancel()
                del user_buffer_tasks[subscriber_id]

            # Clear buffer data
            if subscriber_id in manychat_message_buffer:
                del manychat_message_buffer[subscriber_id]
            if subscriber_id in manychat_last_message_time:
                del manychat_last_message_time[subscriber_id]

            user_buffer_task_scheduled[subscriber_id] = False

            logger.info(f"[Buffer] Cleared buffer for {subscriber_id}")

        except Exception as e:
            logger.error(
                f"[Buffer] Error clearing buffer for {subscriber_id}: {e}")

    @staticmethod
    def shutdown():
        """Gracefully stop background tasks (stub for webhook)."""
        return
