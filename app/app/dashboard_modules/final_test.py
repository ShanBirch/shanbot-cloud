#!/usr/bin/env python3
"""
Final comprehensive test of the auto response system
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta


def test_database():
    """Test database functionality"""
    print("🗄️ Testing Database...")

    db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_responses'")
        table_exists = cursor.fetchone() is not None
        print(f"  ✅ scheduled_responses table exists: {table_exists}")

        # Check current status
        cursor.execute(
            "SELECT status, COUNT(*) FROM scheduled_responses GROUP BY status")
        status_counts = dict(cursor.fetchall())
        print(f"  📊 Current status counts: {status_counts}")

        conn.close()
        return True

    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False


def test_auto_mode_status():
    """Test auto mode status file"""
    print("\n🔧 Testing Auto Mode Status...")

    status_file = "auto_mode_status.json"

    try:
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status_data = json.load(f)

            enabled = status_data.get('auto_mode_enabled', False)
            last_updated = status_data.get('last_updated', 'Unknown')

            print(f"  ✅ Status file exists")
            print(f"  📋 Auto Mode: {'ENABLED' if enabled else 'DISABLED'}")
            print(f"  🕒 Last updated: {last_updated}")

            return enabled
        else:
            print(f"  ❌ Status file not found")
            return False

    except Exception as e:
        print(f"  ❌ Status file error: {e}")
        return False


def test_insert_statements():
    """Test that INSERT statements work properly"""
    print("\n📝 Testing INSERT Statements...")

    try:
        db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Try to insert a test response with proper status
        test_time = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                scheduled_send_time, status, incoming_message_text,
                incoming_message_timestamp, calculated_delay_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            888888,  # test review ID
            'insert_test_user',
            'test_subscriber',
            'Test INSERT statement with status field',
            (datetime.now() + timedelta(minutes=30)).isoformat(),  # Future time
            'scheduled',  # Explicit status
            'Test incoming message',
            test_time,
            30
        ))

        test_id = cursor.lastrowid
        print(f"  ✅ Successfully inserted test response ID {test_id}")

        # Verify it was inserted correctly
        cursor.execute(
            "SELECT status FROM scheduled_responses WHERE schedule_id = ?", (test_id,))
        inserted_status = cursor.fetchone()[0]
        print(f"  ✅ Inserted status: {inserted_status}")

        # Clean up the test response
        cursor.execute(
            "DELETE FROM scheduled_responses WHERE schedule_id = ?", (test_id,))
        print(f"  🧹 Cleaned up test response")

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print(f"  ❌ INSERT test error: {e}")
        return False


def test_auto_sender_import():
    """Test that auto sender can be imported and key functions work"""
    print("\n🤖 Testing Auto Sender Import...")

    try:
        import sys
        sys.path.append('.')
        from response_auto_sender import check_auto_mode_status, get_stats

        print(f"  ✅ Successfully imported auto sender")

        # Test auto mode check
        enabled = check_auto_mode_status()
        print(f"  📋 Auto mode check works: {enabled}")

        # Test stats
        stats = get_stats()
        print(f"  📊 Stats function works: {len(stats)} keys")

        return True

    except Exception as e:
        print(f"  ❌ Auto sender import error: {e}")
        return False


def main():
    print("🚀 FINAL AUTO RESPONSE SYSTEM TEST")
    print("=" * 50)

    tests = [
        ("Database", test_database),
        ("Auto Mode Status", test_auto_mode_status),
        ("INSERT Statements", test_insert_statements),
        ("Auto Sender Import", test_auto_sender_import),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ {test_name} test crashed: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 50)
    print("📋 TEST RESULTS:")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\nYour auto response system is ready!")
        print("\n📋 How to use:")
        print("1. Enable Auto Mode in the dashboard Response Review Queue")
        print("2. Run 'python response_auto_sender.py' in background")
        print("3. Scheduled responses will be automatically sent")
        print("4. Monitor the dashboard for activity")
    else:
        print("⚠️ SOME TESTS FAILED")
        print("\nPlease check the failed tests above and fix any issues.")

    print("=" * 50)


if __name__ == "__main__":
    main()
