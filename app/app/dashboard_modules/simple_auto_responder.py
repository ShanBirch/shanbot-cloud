#!/usr/bin/env python3
"""
Simple Auto Responder - A reliable system for automatically responding with proper timing delays
"""

import sqlite3
import json
import logging
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add path for imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import ManyChat functionality
try:
    from webhook0605 import update_manychat_fields, split_response_into_messages
    MANYCHAT_AVAILABLE = True
    logger.info("✅ ManyChat integration loaded successfully")
except ImportError:
    try:
        from webhook_handlers import update_manychat_fields, split_response_into_messages
        MANYCHAT_AVAILABLE = True
        logger.info("✅ ManyChat integration loaded (alternative)")
    except ImportError:
        update_manychat_fields = None
        def split_response_into_messages(x): return [x]
        MANYCHAT_AVAILABLE = False
        logger.warning(
            "⚠️ ManyChat integration not available - will simulate sending")

# Database path
DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_response_delay_minutes(user_message_timestamp: str, user_ig_username: str) -> int:
    """
    Calculate delay in minutes based on how long the user took to respond.
    This calculates ONCE and that's it - no recalculation.
    """
    try:
        user_msg_time = datetime.fromisoformat(
            user_message_timestamp.split('+')[0])

        # Get the last AI message before this user message
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT timestamp FROM conversation_history
        WHERE ig_username = ? AND message_type = 'ai' AND timestamp < ?
        ORDER BY timestamp DESC LIMIT 1
        """, (user_ig_username, user_message_timestamp))

        result = cursor.fetchone()
        conn.close()

        if result:
            last_ai_time = datetime.fromisoformat(
                result['timestamp'].split('+')[0])
            user_response_time = user_msg_time - last_ai_time
            delay_minutes = int(user_response_time.total_seconds() / 60)
            logger.info(
                f"User {user_ig_username} took {delay_minutes} minutes to respond")
        else:
            # Default delay if no conversation history
            delay_minutes = 30
            logger.info(
                f"No conversation history for {user_ig_username}, using 30-minute default")

        # Cap between 5 minutes and 12 hours (720 minutes)
        delay_minutes = max(5, min(delay_minutes, 720))

        # Add ±10% randomness to make it more human-like
        import random
        variation = random.uniform(0.9, 1.1)
        delay_minutes = int(delay_minutes * variation)

        return delay_minutes

    except Exception as e:
        logger.error(f"Error calculating delay: {e}")
        return 30  # Safe default


def add_auto_response(review_id: int, user_ig: str, subscriber_id: str, message_text: str,
                      incoming_msg: str, incoming_timestamp: str, delay_minutes: int) -> bool:
    """
    Add a response to the simple auto response queue.
    This stores it with a calculated send time and doesn't recalculate.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create the simple auto responses table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS simple_auto_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER UNIQUE,
            user_ig_username TEXT NOT NULL,
            user_subscriber_id TEXT NOT NULL,
            response_text TEXT NOT NULL,
            incoming_message TEXT NOT NULL,
            incoming_timestamp TEXT NOT NULL,
            delay_minutes INTEGER NOT NULL,
            send_at_timestamp TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT NULL
        )
        """)

        # Calculate exact send time (ONCE, never changes)
        send_at = datetime.now() + timedelta(minutes=delay_minutes)
        send_at_str = send_at.isoformat()

        # Insert the auto response
        cursor.execute("""
        INSERT OR REPLACE INTO simple_auto_responses 
        (review_id, user_ig_username, user_subscriber_id, response_text, 
         incoming_message, incoming_timestamp, delay_minutes, send_at_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (review_id, user_ig, subscriber_id, message_text,
              incoming_msg, incoming_timestamp, delay_minutes, send_at_str))

        conn.commit()
        conn.close()

        logger.info(
            f"✅ Auto response scheduled for {user_ig} in {delay_minutes} minutes (at {send_at.strftime('%H:%M:%S')})")
        return True

    except Exception as e:
        logger.error(f"Error adding auto response: {e}")
        return False


def send_auto_response(response_row) -> bool:
    """
    Actually send the auto response via ManyChat
    """
    try:
        user_ig = response_row['user_ig_username']
        subscriber_id = response_row['user_subscriber_id']
        response_text = response_row['response_text']

        if not MANYCHAT_AVAILABLE:
            logger.warning(
                f"⚠️ ManyChat not available, simulating send for {user_ig}")
            return True  # Simulate success for testing

        # Split response into chunks
        message_chunks = split_response_into_messages(response_text)
        manychat_fields = ["o1 Response", "o1 Response 2", "o1 Response 3"]

        logger.info(
            f"📤 Sending response to {user_ig}: {response_text[:50]}...")

        # Send each chunk
        for i, chunk in enumerate(message_chunks[:3]):  # Max 3 chunks
            field_name = manychat_fields[i]
            success = update_manychat_fields(
                subscriber_id, {field_name: chunk})

            if not success:
                logger.error(f"❌ Failed to send chunk {i+1} to {user_ig}")
                return False

            time.sleep(0.5)  # Brief delay between chunks

        # Trigger the response time action
        update_manychat_fields(subscriber_id, {"response time": "action"})

        # Add to conversation history
        add_to_conversation_history(user_ig, response_text)

        logger.info(f"✅ Successfully sent auto response to {user_ig}")
        return True

    except Exception as e:
        logger.error(f"❌ Error sending auto response to {user_ig}: {e}")
        return False


def add_to_conversation_history(user_ig: str, response_text: str):
    """Add the sent message to conversation history using unified messages table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get subscriber_id for this user if available
        cursor.execute(
            "SELECT subscriber_id FROM users WHERE ig_username = ?", (user_ig,))
        user_result = cursor.fetchone()
        subscriber_id = user_result[0] if user_result else None

        cursor.execute("""
        INSERT INTO messages (ig_username, subscriber_id, message_type, message_text, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (user_ig, subscriber_id, 'ai', response_text, datetime.now().isoformat()))

        conn.commit()
        conn.close()

        logger.info(f"📝 Added response to conversation history for {user_ig}")

    except Exception as e:
        logger.error(f"❌ Failed to add to conversation history: {e}")


def process_pending_auto_responses():
    """
    Process auto responses that are due to be sent.
    This is the main worker function.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure table exists first
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS simple_auto_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER UNIQUE,
            user_ig_username TEXT NOT NULL,
            user_subscriber_id TEXT NOT NULL,
            response_text TEXT NOT NULL,
            incoming_message TEXT NOT NULL,
            incoming_timestamp TEXT NOT NULL,
            delay_minutes INTEGER NOT NULL,
            send_at_timestamp TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT NULL
        )
        """)

        # Get responses that are due (send time has passed)
        current_time = datetime.now().isoformat()

        cursor.execute("""
        SELECT * FROM simple_auto_responses 
        WHERE status = 'pending' AND send_at_timestamp <= ?
        ORDER BY send_at_timestamp ASC
        """, (current_time,))

        due_responses = cursor.fetchall()

        if not due_responses:
            return 0

        logger.info(
            f"🔍 Found {len(due_responses)} auto responses ready to send")

        processed = 0
        for response_row in due_responses:
            try:
                # Send the response
                if send_auto_response(response_row):
                    # Mark as sent
                    cursor.execute("""
                    UPDATE simple_auto_responses 
                    SET status = 'sent', sent_at = ?
                    WHERE id = ?
                    """, (datetime.now().isoformat(), response_row['id']))

                    # Update the original review status
                    cursor.execute("""
                    UPDATE pending_reviews 
                    SET status = 'sent'
                    WHERE review_id = ?
                    """, (response_row['review_id'],))

                    processed += 1
                    logger.info(
                        f"✅ Processed auto response for {response_row['user_ig_username']}")

                else:
                    # Mark as failed
                    cursor.execute("""
                    UPDATE simple_auto_responses 
                    SET status = 'failed'
                    WHERE id = ?
                    """, (response_row['id'],))

                    logger.error(
                        f"❌ Failed to send auto response for {response_row['user_ig_username']}")

            except Exception as e:
                logger.error(
                    f"❌ Error processing auto response {response_row['id']}: {e}")
                cursor.execute("""
                UPDATE simple_auto_responses 
                SET status = 'failed'
                WHERE id = ?
                """, (response_row['id'],))

        conn.commit()
        conn.close()

        return processed

    except Exception as e:
        logger.error(f"❌ Error in process_pending_auto_responses: {e}")
        return 0


def get_auto_response_stats():
    """Get statistics about auto responses"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='simple_auto_responses'
        """)

        if not cursor.fetchone():
            return {"pending": 0, "sent": 0, "failed": 0, "next_send": None}

        # Get status counts
        cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM simple_auto_responses 
        GROUP BY status
        """)

        status_counts = {row['status']: row['count']
                         for row in cursor.fetchall()}

        # Get next send time
        cursor.execute("""
        SELECT MIN(send_at_timestamp) as next_send
        FROM simple_auto_responses
        WHERE status = 'pending'
        """)

        next_result = cursor.fetchone()
        next_send = next_result['next_send'] if next_result else None

        conn.close()

        return {
            "pending": status_counts.get('pending', 0),
            "sent": status_counts.get('sent', 0),
            "failed": status_counts.get('failed', 0),
            "next_send": next_send
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"pending": 0, "sent": 0, "failed": 0, "next_send": None}


def main():
    """
    Main worker loop for processing auto responses
    """
    print("🤖 SIMPLE AUTO RESPONDER")
    print("=" * 50)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        f"ManyChat Available: {'YES' if MANYCHAT_AVAILABLE else 'NO (simulated)'}")
    print("=" * 50)

    cycle = 0

    try:
        while True:
            cycle += 1

            # Process due responses
            processed = process_pending_auto_responses()

            if processed > 0:
                logger.info(
                    f"✅ Cycle {cycle}: Processed {processed} auto responses")

            # Show stats every 10 cycles
            if cycle % 10 == 0:
                stats = get_auto_response_stats()
                logger.info(
                    f"📊 Stats: {stats['pending']} pending, {stats['sent']} sent, {stats['failed']} failed")

                if stats['next_send']:
                    try:
                        next_time = datetime.fromisoformat(stats['next_send'])
                        wait_time = next_time - datetime.now()
                        if wait_time.total_seconds() > 0:
                            logger.info(
                                f"⏰ Next auto response in: {str(wait_time).split('.')[0]}")
                    except:
                        pass

            # Wait 30 seconds before next check
            time.sleep(30)

    except KeyboardInterrupt:
        logger.info("🛑 Stopped by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
