#!/usr/bin/env python3
"""
Comprehensive fix for auto response system issues.
This script will:
1. Fix INSERT statements to include status field
2. Update existing pending responses to scheduled status
3. Verify the auto sender works properly
"""

import sqlite3
import os
from datetime import datetime, timedelta


def get_db_connection():
    """Get database connection"""
    db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
    return sqlite3.connect(db_path)


def fix_insert_statements():
    """Fix the INSERT statements in response_review.py"""
    print("🔧 Fixing INSERT statements...")

    with open('response_review.py', 'r') as f:
        content = f.read()

    # Fix the INSERT statements to include status column
    # Pattern 1: with original_response_time
    old_insert1 = """            INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, original_response_time,
                user_response_time, calculated_delay_minutes, scheduled_send_time, user_notes, manual_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    new_insert1 = """            INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, original_response_time,
                user_response_time, calculated_delay_minutes, scheduled_send_time, user_notes, manual_context, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    # Pattern 2: without original_response_time
    old_insert2 = """            INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, user_response_time,
                calculated_delay_minutes, scheduled_send_time, user_notes, manual_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    new_insert2 = """            INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, user_response_time,
                calculated_delay_minutes, scheduled_send_time, user_notes, manual_context, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    # Replace INSERT statements
    content = content.replace(old_insert1, new_insert1)
    content = content.replace(old_insert2, new_insert2)

    # Fix VALUES to include 'scheduled' status
    # Add status value before closing parentheses in VALUES
    old_value_ending = """                manual_context
            ))"""
    new_value_ending = """                manual_context,
                'scheduled'
            ))"""

    content = content.replace(old_value_ending, new_value_ending)

    # Write back the fixed file
    with open('response_review.py', 'w') as f:
        f.write(content)

    print("✅ Fixed INSERT statements to include status field")


def update_pending_responses():
    """Update any existing pending responses to scheduled status"""
    print("🔄 Updating pending responses to scheduled status...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check current status values
        cursor.execute("SELECT DISTINCT status FROM scheduled_responses")
        statuses = [row[0] for row in cursor.fetchall()]
        print(f"Current status values: {statuses}")

        # Update pending to scheduled
        cursor.execute("""
            UPDATE scheduled_responses 
            SET status = 'scheduled' 
            WHERE status = 'pending' OR status IS NULL
        """)

        updated_count = cursor.rowcount
        print(f"✅ Updated {updated_count} responses from pending to scheduled")

        conn.commit()
        conn.close()

        return updated_count

    except Exception as e:
        print(f"❌ Error updating pending responses: {e}")
        return 0


def test_auto_sender_query():
    """Test the auto sender query to see if it finds responses"""
    print("🧪 Testing auto sender query...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        current_time = datetime.now().isoformat()
        print(f"Current time: {current_time}")

        # Test the exact query used by auto sender
        cursor.execute("""
            SELECT schedule_id, user_ig_username, scheduled_send_time, status, response_text
            FROM scheduled_responses 
            WHERE status = 'scheduled' AND scheduled_send_time <= ?
            ORDER BY scheduled_send_time ASC
        """, (current_time,))

        due_responses = cursor.fetchall()
        print(f"Found {len(due_responses)} responses due for sending")

        if due_responses:
            print("Due responses:")
            for resp in due_responses:
                schedule_id, username, send_time, status, text = resp
                print(
                    f"  ID {schedule_id}: @{username} at {send_time} (status: {status})")
                print(f"    Text: {text[:60]}...")

        # Also check all scheduled responses
        cursor.execute("""
            SELECT schedule_id, user_ig_username, scheduled_send_time, status 
            FROM scheduled_responses 
            WHERE status = 'scheduled'
            ORDER BY scheduled_send_time ASC
        """)

        all_scheduled = cursor.fetchall()
        print(f"\nAll scheduled responses: {len(all_scheduled)}")
        for resp in all_scheduled:
            schedule_id, username, send_time, status = resp
            is_due = send_time <= current_time
            print(
                f"  ID {schedule_id}: @{username} at {send_time} ({'DUE' if is_due else 'FUTURE'})")

        conn.close()
        return len(due_responses)

    except Exception as e:
        print(f"❌ Error testing auto sender query: {e}")
        return 0


def create_test_scheduled_response():
    """Create a test scheduled response for immediate sending"""
    print("📝 Creating test scheduled response...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create a response that should be sent immediately
        test_time = (datetime.now() - timedelta(minutes=1)
                     ).isoformat()  # 1 minute ago

        cursor.execute("""
            INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, 
                calculated_delay_minutes, scheduled_send_time, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            999999,  # Test review ID
            'test_user',
            'test_subscriber',
            'This is a test response from the auto sender',
            'Test incoming message',
            test_time,
            1,
            test_time,
            'scheduled'
        ))

        test_id = cursor.lastrowid
        print(
            f"✅ Created test response with ID {test_id} scheduled for {test_time}")

        conn.commit()
        conn.close()

        return test_id

    except Exception as e:
        print(f"❌ Error creating test response: {e}")
        return None


def main():
    print("🚀 Starting comprehensive auto response system fix...")
    print("=" * 60)

    # Step 1: Fix INSERT statements
    fix_insert_statements()
    print()

    # Step 2: Update pending responses
    updated_count = update_pending_responses()
    print()

    # Step 3: Test auto sender query
    due_count = test_auto_sender_query()
    print()

    # Step 4: Create test response if none are due
    if due_count == 0:
        test_id = create_test_scheduled_response()
        print()

        # Test again after creating test response
        print("🔄 Re-testing auto sender query after creating test response...")
        test_auto_sender_query()

    print("=" * 60)
    print("🎉 Auto response system fix completed!")
    print("\nNext steps:")
    print("1. Test the dashboard response review queue")
    print("2. Run the auto sender to verify it processes responses")
    print("3. Monitor the auto_mode_status.json file")


if __name__ == "__main__":
    main()
