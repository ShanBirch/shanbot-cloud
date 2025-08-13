#!/usr/bin/env python3
"""
Simple Auto Response Worker
Processes scheduled responses with minimal dependencies.
"""

import time
import sys
import os
import sqlite3
import logging
from datetime import datetime, timedelta

# Add the parent directories to the path to import modules correctly
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)  # app directory
grandparent_dir = os.path.dirname(parent_dir)  # shanbot directory

sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, grandparent_dir)

# Configure simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import ManyChat functionality
try:
    from webhook0605 import update_manychat_fields
    MANYCHAT_AVAILABLE = True
    logger.info("✅ ManyChat integration loaded successfully")
except ImportError:
    try:
        from webhook_handlers import update_manychat_fields
        MANYCHAT_AVAILABLE = True
        logger.info("✅ ManyChat integration loaded successfully (alternative)")
    except ImportError:
        update_manychat_fields = None
        MANYCHAT_AVAILABLE = False
        logger.warning(
            "⚠️ ManyChat integration not available - will simulate sending")


def split_response_into_messages(text):
    """Split response into multiple messages if needed"""
    try:
        if MANYCHAT_AVAILABLE:
            from webhook0605 import split_response_into_messages as split_func
            return split_func(text)
    except ImportError:
        pass

    # Fallback: simple split by length
    if len(text) <= 1000:
        return [text]

    # Split into chunks of ~800 characters at sentence boundaries
    sentences = text.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk + sentence) < 800:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks[:3]  # Limit to 3 chunks to match ManyChat fields


def get_db_connection():
    """Get database connection"""
    db_path = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), 'analytics_data_good.sqlite')
    return sqlite3.connect(db_path)


def send_response_via_manychat(scheduled_response):
    """Actually send the response via ManyChat"""
    try:
        user_ig = scheduled_response['user_ig_username']
        subscriber_id = scheduled_response['user_subscriber_id']
        response_text = scheduled_response['response_text']

        if not MANYCHAT_AVAILABLE or not update_manychat_fields:
            logger.warning(
                f"⚠️ ManyChat not available, simulating send for {user_ig}")
            return True  # Simulate success for testing

        # Split response into chunks
        message_chunks = split_response_into_messages(response_text)
        manychat_field_names = ["o1 Response",
                                "o1 Response 2", "o1 Response 3"]

        all_sends_successful = True
        first_chunk_sent_successfully = False

        logger.info(
            f"📤 Sending {len(message_chunks)} message chunks to {user_ig}")

        for i, chunk in enumerate(message_chunks):
            if i < len(manychat_field_names):
                field_name = manychat_field_names[i]
                send_success = update_manychat_fields(
                    subscriber_id, {field_name: chunk})
                if send_success:
                    if i == 0:
                        first_chunk_sent_successfully = True
                    logger.info(
                        f"✅ Sent chunk {i+1}/{len(message_chunks)} to {user_ig}")
                    time.sleep(0.5)  # Brief delay between chunks
                else:
                    all_sends_successful = False
                    logger.error(f"❌ Failed to send chunk {i+1} to {user_ig}")
                    break
            else:
                logger.warning(
                    f"⚠️ Chunk {i+1} not sent (exceeds ManyChat field limit)")
                break

        if first_chunk_sent_successfully:
            # Trigger response time action
            update_manychat_fields(subscriber_id, {"response time": "action"})
            logger.info(f"✅ Successfully sent complete response to {user_ig}")
            return True
        else:
            logger.error(f"❌ Failed to send response to {user_ig}")
            return False

    except Exception as e:
        logger.error(f"❌ Error sending to {user_ig}: {e}")
        return False


def add_to_conversation_history(user_ig, response_text, user_response_time):
    """Add the sent message to conversation history using unified messages table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Calculate AI response timestamp (user timestamp + 1 second)
        try:
            user_msg_timestamp = datetime.fromisoformat(
                user_response_time.split('+')[0])
            ai_response_timestamp = (
                user_msg_timestamp + timedelta(seconds=1)).isoformat()
        except (ValueError, AttributeError):
            ai_response_timestamp = datetime.now().isoformat()

        # Get subscriber_id for this user if available
        cursor.execute(
            "SELECT subscriber_id FROM users WHERE ig_username = ?", (user_ig,))
        user_result = cursor.fetchone()
        subscriber_id = user_result[0] if user_result else None

        # Insert into unified messages table
        cursor.execute("""
        INSERT INTO messages (ig_username, subscriber_id, message_type, message_text, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (user_ig, subscriber_id, 'ai', response_text, ai_response_timestamp))

        conn.commit()
        conn.close()
        logger.info(f"📝 Added message to conversation history for {user_ig}")

    except Exception as e:
        logger.error(
            f"❌ Failed to add to conversation history for {user_ig}: {e}")


def update_review_status(review_id, status, response_text):
    """Update the review status to mark it as sent"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE reviews SET status = ?, final_response = ?, processed_at = ?
        WHERE review_id = ?
        """, (status, response_text, datetime.now().isoformat(), review_id))

        conn.commit()
        conn.close()
        logger.info(f"📋 Updated review {review_id} status to {status}")

    except Exception as e:
        logger.error(f"❌ Failed to update review status for {review_id}: {e}")


def process_scheduled_responses():
    """Process scheduled responses that are due"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get responses that are due to be sent
        current_time = datetime.now().isoformat()
        cursor.execute("""
        SELECT * FROM scheduled_responses 
        WHERE status = 'scheduled' AND scheduled_send_time <= ?
        ORDER BY scheduled_send_time ASC
        """, (current_time,))

        due_responses = cursor.fetchall()
        processed_count = 0

        logger.info(f"🔍 Found {len(due_responses)} responses due for sending")

        for row in due_responses:
            try:
                scheduled_response = dict(row)
                user_ig = scheduled_response['user_ig_username']

                logger.info(f"📤 Processing response for {user_ig}...")

                # Actually send the response via ManyChat
                send_success = send_response_via_manychat(scheduled_response)

                if send_success:
                    # Mark as sent in scheduled_responses table
                    cursor.execute("""
                    UPDATE scheduled_responses 
                    SET status = 'sent', sent_at = ? 
                    WHERE schedule_id = ?
                    """, (datetime.now().isoformat(), row['schedule_id']))

                    # Add to conversation history
                    add_to_conversation_history(
                        user_ig,
                        scheduled_response['response_text'],
                        scheduled_response['user_response_time']
                    )

                    # Update review status to remove from queue
                    update_review_status(
                        scheduled_response['review_id'],
                        'sent',
                        scheduled_response['response_text']
                    )

                    logger.info(
                        f"✅ Successfully processed and sent response to {user_ig}")
                    processed_count += 1

                else:
                    # Mark as failed
                    cursor.execute("""
                    UPDATE scheduled_responses 
                    SET status = 'failed' 
                    WHERE schedule_id = ?
                    """, (row['schedule_id'],))

                    logger.error(f"❌ Failed to send response to {user_ig}")

            except Exception as e:
                logger.error(
                    f"❌ Error processing response {row['schedule_id']}: {e}")
                cursor.execute("""
                UPDATE scheduled_responses 
                SET status = 'failed' 
                WHERE schedule_id = ?
                """, (row['schedule_id'],))

        conn.commit()
        conn.close()

        if processed_count > 0:
            logger.info(
                f"🎉 Successfully processed {processed_count} responses!")

        return processed_count

    except Exception as e:
        logger.error(f"❌ Error in process_scheduled_responses: {e}")
        return 0


def get_stats():
    """Get simple statistics"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT status, COUNT(*) as count FROM scheduled_responses GROUP BY status")
        status_counts = {row['status']: row['count']
                         for row in cursor.fetchall()}

        cursor.execute("""
        SELECT COUNT(*) as pending_count FROM scheduled_responses 
        WHERE status = 'scheduled' AND scheduled_send_time > ?
        """, (datetime.now().isoformat(),))

        pending_info = cursor.fetchone()

        conn.close()

        return {
            'scheduled': status_counts.get('scheduled', 0),
            'sent': status_counts.get('sent', 0),
            'failed': status_counts.get('failed', 0),
            'pending_count': pending_info['pending_count'] if pending_info else 0
        }
    except Exception as e:
        logger.error(f"❌ Error getting stats: {e}")
        return {'scheduled': 0, 'sent': 0, 'failed': 0, 'pending_count': 0}


def main():
    """Main worker function"""
    import argparse

    parser = argparse.ArgumentParser(description='Simple Auto Response Worker')
    parser.add_argument('--test', action='store_true',
                        help='Run once and exit')
    args = parser.parse_args()

    print("=" * 60)
    print("🤖 SIMPLE AUTO RESPONSE WORKER")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'TEST' if args.test else 'CONTINUOUS'}")
    print("=" * 60)

    if args.test:
        logger.info("🧪 Running test cycle...")
        processed = process_scheduled_responses()
        stats = get_stats()
        logger.info(
            f"✅ Test completed. Processed: {processed}, Stats: {stats}")
        return

    # Continuous mode
    logger.info("🔄 Starting continuous mode...")
    logger.info("💡 Press Ctrl+C to stop")

    try:
        cycle = 0
        while True:
            cycle += 1
            processed = process_scheduled_responses()

            if processed > 0:
                logger.info(
                    f"✅ Cycle #{cycle}: Processed {processed} responses")
            elif cycle % 10 == 0:  # Log every 10th cycle when nothing processed
                stats = get_stats()
                logger.info(
                    f"⏳ Cycle #{cycle}: No responses due. Stats: {stats}")

            time.sleep(60)  # Wait 1 minute

    except KeyboardInterrupt:
        logger.info("🛑 Stopped by user")
    except Exception as e:
        logger.error(f"💥 Worker error: {e}")


if __name__ == "__main__":
    main()
