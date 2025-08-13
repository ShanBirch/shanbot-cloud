#!/usr/bin/env python3
"""
Complete Auto Response Worker
Processes scheduled responses with full ManyChat integration.
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection"""
    db_path = os.path.join(parent_dir, 'analytics_data_good.sqlite')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# Import required functions
try:
    from dashboard_sqlite_utils import (
        update_review_status,
        add_to_learning_log,
        add_message_to_history,
        insert_manual_context_message
    )
    logger.info("✅ Successfully imported database utilities")
except ImportError as e:
    logger.error(f"❌ Failed to import database utilities: {e}")
    sys.exit(1)

try:
    # Try to import ManyChat functions
    try:
        from webhook0605 import split_response_into_messages, update_manychat_fields
        logger.info(
            "✅ Successfully imported ManyChat functions from webhook0605")
    except ImportError:
        try:
            from webhook_handlers import split_response_into_messages, update_manychat_fields
            logger.info(
                "✅ Successfully imported ManyChat functions from webhook_handlers")
        except ImportError:
            logger.error("❌ Could not import ManyChat functions")
            def split_response_into_messages(text): return [text]
            update_manychat_fields = None
except Exception as e:
    logger.error(f"❌ Error importing ManyChat functions: {e}")
    def split_response_into_messages(text): return [text]
    update_manychat_fields = None


def send_scheduled_response(scheduled_response):
    """
    Send a scheduled response via ManyChat - full implementation
    """
    try:
        if not update_manychat_fields:
            logger.error("❌ ManyChat integration not available")
            return False

        user_ig = scheduled_response['user_ig_username']
        subscriber_id = scheduled_response['user_subscriber_id']
        response_text = scheduled_response['response_text']
        review_id = scheduled_response['review_id']
        manual_context = scheduled_response.get('manual_context', '')

        logger.info(f"🚀 Sending scheduled response to {user_ig}")

        # Handle manual context if provided
        if manual_context and manual_context.strip():
            try:
                context_inserted = insert_manual_context_message(
                    user_ig_username=user_ig,
                    subscriber_id=subscriber_id,
                    manual_message_text=manual_context.strip(),
                    user_message_timestamp_str=scheduled_response['user_response_time']
                )
                if context_inserted:
                    logger.info(f"📝 Manual context saved for {user_ig}")
            except Exception as e:
                logger.warning(
                    f"⚠️ Could not save manual context for {user_ig}: {e}")

        # Send message via ManyChat
        message_chunks = split_response_into_messages(response_text)
        manychat_field_names = ["o1 Response",
                                "o1 Response 2", "o1 Response 3"]

        all_sends_successful = True
        first_chunk_sent_successfully = False

        for i, chunk in enumerate(message_chunks):
            if i < len(manychat_field_names):
                field_name = manychat_field_names[i]
                logger.info(
                    f"📤 Sending chunk {i+1}/{len(message_chunks)} to {user_ig}: {chunk[:50]}...")

                send_success = update_manychat_fields(
                    subscriber_id, {field_name: chunk})

                if send_success:
                    if i == 0:
                        first_chunk_sent_successfully = True
                    logger.info(f"✅ Chunk {i+1} sent successfully")
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
            logger.info(f"🎯 Triggering response time action for {user_ig}")
            update_manychat_fields(subscriber_id, {"response time": "action"})

            # Add to conversation history
            try:
                user_msg_timestamp = datetime.fromisoformat(
                    scheduled_response['user_response_time'].split('+')[0])
                ai_response_timestamp = (
                    user_msg_timestamp + timedelta(seconds=1)).isoformat()
            except (ValueError, KeyError):
                ai_response_timestamp = None

            add_message_to_history(
                ig_username=user_ig,
                message_type='ai',
                message_text=response_text,
                message_timestamp=ai_response_timestamp
            )
            logger.info(f"📚 Added to conversation history for {user_ig}")

            # Add to learning log (mark as auto-sent)
            add_to_learning_log(
                review_id=review_id,
                user_ig_username=user_ig,
                user_subscriber_id=subscriber_id,
                original_prompt_text="[AUTO MODE]",
                original_gemini_response=response_text,
                edited_response_text=response_text,
                user_notes=f"[AUTO MODE] {scheduled_response.get('user_notes', '')}".strip(
                ),
                is_good_example_for_few_shot=None
            )
            logger.info(f"📊 Added to learning log for {user_ig}")

            # Mark the review as sent so it gets removed from the queue
            update_review_status(review_id, "sent", response_text)
            logger.info(f"✅ Marked review as sent for {user_ig}")

            logger.info(f"🎉 Successfully sent auto-response to {user_ig}")
            return True
        else:
            logger.error(f"❌ Failed to send auto-response to {user_ig}")
            return False

    except Exception as e:
        logger.error(
            f"💥 Error sending scheduled response to {user_ig}: {e}", exc_info=True)
        return False


def process_scheduled_responses():
    """Process scheduled responses that are due"""
    try:
        conn = get_db_connection()
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

        if due_responses:
            logger.info(
                f"📋 Found {len(due_responses)} responses due for sending")

        for row in due_responses:
            try:
                # Actually send the response via ManyChat
                success = send_scheduled_response(dict(row))

                if success:
                    # Update status to sent
                    cursor.execute("""
                    UPDATE scheduled_responses 
                    SET status = 'sent', sent_at = ? 
                    WHERE schedule_id = ?
                    """, (datetime.now().isoformat(), row['schedule_id']))

                    processed_count += 1
                    logger.info(
                        f"✅ Successfully processed response for {row['user_ig_username']}")
                else:
                    # Mark as failed
                    cursor.execute("""
                    UPDATE scheduled_responses 
                    SET status = 'failed' 
                    WHERE schedule_id = ?
                    """, (row['schedule_id'],))

                    logger.error(
                        f"❌ Failed to process response for {row['user_ig_username']}")

            except Exception as e:
                logger.error(
                    f"💥 Error processing response {row['schedule_id']}: {e}")
                cursor.execute("""
                UPDATE scheduled_responses 
                SET status = 'failed' 
                WHERE schedule_id = ?
                """, (row['schedule_id'],))

        conn.commit()
        conn.close()
        return processed_count

    except Exception as e:
        logger.error(
            f"💥 Error in process_scheduled_responses: {e}", exc_info=True)
        return 0


def get_stats():
    """Get statistics about scheduled responses"""
    try:
        conn = get_db_connection()
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

    parser = argparse.ArgumentParser(
        description='Complete Auto Response Worker')
    parser.add_argument('--test', action='store_true',
                        help='Run once and exit')
    args = parser.parse_args()

    print("=" * 60)
    print("🤖 COMPLETE AUTO RESPONSE WORKER")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'TEST' if args.test else 'CONTINUOUS'}")
    print(
        f"ManyChat Available: {'✅ YES' if update_manychat_fields else '❌ NO'}")
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
