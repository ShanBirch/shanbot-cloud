#!/usr/bin/env python3
"""
Automated response sender that processes scheduled responses from the dashboard.
This script should run continuously in the background.
"""

import sqlite3
import time
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_sender.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection"""
    db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return None
    return sqlite3.connect(db_path)


def send_via_manychat(user_ig_username: str, subscriber_id: str, message_text: str) -> bool:
    """
    Send message via ManyChat API

    Args:
        user_ig_username: Instagram username
        subscriber_id: ManyChat subscriber ID
        message_text: Message to send

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Import ManyChat utilities
        import sys
        sys.path.append(r'C:\Users\Shannon\OneDrive\Desktop\shanbot\app')
        from webhook_handlers import update_manychat_fields

        logger.info(
            f"Sending message to @{user_ig_username} (subscriber: {subscriber_id})")
        logger.info(f"Message: {message_text[:100]}...")

        # Use ManyChat field update (same as webhook)
        success = update_manychat_fields(
            subscriber_id, {"o1 Response": message_text})
        if success:
            # Trigger the response
            update_manychat_fields(subscriber_id, {"response time": "action"})

        if success:
            logger.info(
                f"[SUCCESS] Successfully sent message to @{user_ig_username}")
        else:
            logger.error(
                f"[ERROR] Failed to send message to @{user_ig_username}")

        return success

    except Exception as e:
        logger.error(f"Error sending message via ManyChat: {e}", exc_info=True)
        return False


def process_scheduled_responses() -> int:
    """
    Process all scheduled responses that are due to be sent

    Returns:
        int: Number of responses processed
    """
    try:
        conn = get_db_connection()
        if not conn:
            return 0

        cursor = conn.cursor()
        current_time = datetime.now().isoformat()

        logger.info(f"Checking for responses due at {current_time}")

        # Get responses that are due to be sent
        cursor.execute("""
            SELECT schedule_id, review_id, user_ig_username, user_subscriber_id, 
                   response_text, scheduled_send_time, status
            FROM scheduled_responses 
            WHERE status = 'scheduled' AND scheduled_send_time <= ?
            ORDER BY scheduled_send_time ASC
        """, (current_time,))

        due_responses = cursor.fetchall()
        logger.info(f"Found {len(due_responses)} responses due for sending")

        processed_count = 0

        for row in due_responses:
            schedule_id, review_id, user_ig_username, subscriber_id, response_text, scheduled_time, status = row

            logger.info(
                f"Processing response ID {schedule_id} for @{user_ig_username}")
            logger.info(f"  Scheduled: {scheduled_time}, Status: {status}")
            logger.info(f"  Message: {response_text[:100]}...")

            # Send the message
            success = send_via_manychat(
                user_ig_username, subscriber_id, response_text)

            if success:
                # Update status to sent
                cursor.execute("""
                    UPDATE scheduled_responses 
                    SET status = 'sent', sent_at = ?
                    WHERE schedule_id = ?
                """, (current_time, schedule_id))

                # Update review status to indicate it was sent automatically
                try:
                    cursor.execute("""
                        UPDATE pending_reviews 
                        SET status = 'auto_sent', processed_at = ?
                        WHERE review_id = ?
                    """, (current_time, review_id))
                except Exception as e:
                    logger.warning(
                        f"Could not update review status for review_id {review_id}: {e}")

                logger.info(
                    f"[SUCCESS] Successfully sent and marked as sent: ID {schedule_id}")
                processed_count += 1

            else:
                # Mark as failed
                cursor.execute("""
                    UPDATE scheduled_responses 
                    SET status = 'failed'
                    WHERE schedule_id = ?
                """, (schedule_id,))

                logger.error(
                    f"[ERROR] Failed to send response ID {schedule_id}, marked as failed")

        # Commit all changes
        conn.commit()
        conn.close()

        if processed_count > 0:
            logger.info(
                f"[COMPLETE] Successfully processed {processed_count} scheduled responses")

        return processed_count

    except Exception as e:
        logger.error(
            f"Error processing scheduled responses: {e}", exc_info=True)
        return 0


def check_auto_mode_status() -> bool:
    """Check if Auto Mode is enabled via status file"""
    try:
        # Check current directory first, then absolute path
        status_file = "auto_mode_status.json"
        if not os.path.exists(status_file):
            status_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\dashboard_modules\auto_mode_status.json"

        if not os.path.exists(status_file):
            logger.warning(f"Auto mode status file not found, creating it...")
            # Create the status file with auto mode enabled
            status_data = {
                'auto_mode_enabled': True,
                'last_updated': datetime.now().isoformat(),
                'updated_by': 'auto_sender_init'
            }
            with open("auto_mode_status.json", 'w') as f:
                json.dump(status_data, f, indent=2)
            logger.info("Created auto_mode_status.json with auto mode ENABLED")
            return True

        with open(status_file, 'r') as f:
            status_data = json.load(f)

        # Support both formats: dashboard uses 'active', we use 'auto_mode_enabled'
        is_enabled = status_data.get(
            'auto_mode_enabled', status_data.get('active', False))
        last_updated = status_data.get(
            'last_updated', status_data.get('updated_at', 'Unknown'))

        logger.info(
            f"Auto Mode Status: {'ENABLED' if is_enabled else 'DISABLED'} (updated: {last_updated})")
        return is_enabled

    except Exception as e:
        logger.error(f"Error checking auto mode status: {e}")
        return False


def get_stats() -> Dict[str, Any]:
    """Get statistics about scheduled responses"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}

        cursor = conn.cursor()

        # Get status counts
        cursor.execute(
            "SELECT status, COUNT(*) FROM scheduled_responses GROUP BY status")
        status_counts = dict(cursor.fetchall())

        # Get overdue count
        current_time = datetime.now().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM scheduled_responses 
            WHERE status = 'scheduled' AND scheduled_send_time <= ?
        """, (current_time,))
        overdue_count = cursor.fetchone()[0]

        conn.close()

        return {
            'status_counts': status_counts,
            'overdue_count': overdue_count,
            'current_time': current_time
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {}


def main():
    """Main loop for auto response sender"""
    logger.info("[START] Starting Auto Response Sender")
    logger.info("Press Ctrl+C to stop")

    check_interval = 60  # Check every 60 seconds

    try:
        while True:
            # Check if auto mode is enabled
            if not check_auto_mode_status():
                logger.info("Auto Mode is disabled, skipping this cycle")
                time.sleep(check_interval)
                continue

            # Get current stats
            stats = get_stats()
            if stats:
                logger.info(f"[STATS] Current stats: {stats['status_counts']}")
                if stats['overdue_count'] > 0:
                    logger.info(
                        f"[WARNING] Found {stats['overdue_count']} overdue responses")

            # Process scheduled responses
            processed = process_scheduled_responses()

            if processed == 0:
                logger.info("[IDLE] No responses to process, waiting...")

            # Wait before next check
            logger.info(
                f"[TIMER] Waiting {check_interval} seconds until next check...")
            time.sleep(check_interval)

    except KeyboardInterrupt:
        logger.info("[STOP] Auto Response Sender stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)


if __name__ == "__main__":
    main()
