#!/usr/bin/env python3
"""Webhook Auto Scheduler - Automatically schedules responses when Auto Mode is active"""

import sys
import os
from datetime import datetime

# Add path for imports
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)


def auto_schedule_response_from_webhook(
    user_ig_username: str,
    user_subscriber_id: str,
    incoming_message_text: str,
    incoming_message_timestamp: str,
    generated_prompt_text: str,
    proposed_response_text: str,
    prompt_type: str = 'general_chat'
) -> bool:
    """
    Automatically schedule a response with smart timing when called from webhook.
    This bypasses the manual review queue entirely.

    Returns:
        bool: True if successfully scheduled, False if failed
    """
    try:
        # Import locally to avoid circular imports
        from response_review import (
            create_scheduled_responses_table_if_not_exists,
            calculate_response_delay,
            get_db_connection
        )
        from datetime import timedelta

        # Ensure table exists
        if not create_scheduled_responses_table_if_not_exists():
            print(
                f"Failed to create scheduled responses table for {user_ig_username}")
            return False

        # Calculate smart delay based on user response timing
        delay_minutes = calculate_response_delay(
            incoming_message_timestamp,
            user_ig_username
        )

        # Calculate when to send the response
        scheduled_time = datetime.now() + timedelta(minutes=delay_minutes)

        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO scheduled_responses (
            review_id, user_ig_username, user_subscriber_id, response_text,
            incoming_message_text, incoming_message_timestamp, user_response_time,
            calculated_delay_minutes, scheduled_send_time, status, user_notes, manual_context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            0,  # review_id (0 for auto-scheduled)
            user_ig_username,
            user_subscriber_id,
            proposed_response_text,
            incoming_message_text,
            incoming_message_timestamp,
            incoming_message_timestamp,  # user_response_time
            delay_minutes,
            scheduled_time.isoformat(),
            'scheduled',  # status
            f"[AUTO-SCHEDULED] Prompt: {prompt_type}",  # user_notes
            ""  # manual_context
        ))

        conn.commit()
        conn.close()

        print(
            f"✅ AUTO-SCHEDULED response for {user_ig_username} in {delay_minutes} minutes")
        print(f"   📅 Will send at: {scheduled_time.strftime('%I:%M %p')}")

        return True

    except Exception as e:
        print(
            f"❌ Failed to auto-schedule response for {user_ig_username}: {e}")
        return False
