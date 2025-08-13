#!/usr/bin/env python3
"""
Test script for check-in trigger functionality
"""

from webhook_handlers import update_analytics_data
import sys
import os
import sqlite3

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_checkin_triggers():
    """Test the check-in trigger functionality"""
    print("🧪 Testing check-in trigger functionality...")

    # Test data
    test_ig_username = "test_user_checkin"
    test_subscriber_id = "123456789"
    test_first_name = "Test"
    test_last_name = "User"

    # Test Monday check-in trigger
    print("\n1️⃣ Testing Monday check-in trigger...")
    try:
        update_analytics_data(
            ig_username=test_ig_username,
            user_message="",
            ai_response="",
            subscriber_id=test_subscriber_id,
            first_name=test_first_name,
            last_name=test_last_name,
            is_in_checkin_flow_mon=True,
            is_in_checkin_flow_wed=False
        )
        print("✅ Monday check-in trigger successful")
    except Exception as e:
        print(f"❌ Monday check-in trigger failed: {e}")

    # Test Wednesday check-in trigger
    print("\n2️⃣ Testing Wednesday check-in trigger...")
    try:
        update_analytics_data(
            ig_username=test_ig_username,
            user_message="",
            ai_response="",
            subscriber_id=test_subscriber_id,
            first_name=test_first_name,
            last_name=test_last_name,
            is_in_checkin_flow_mon=False,
            is_in_checkin_flow_wed=True
        )
        print("✅ Wednesday check-in trigger successful")
    except Exception as e:
        print(f"❌ Wednesday check-in trigger failed: {e}")

    # Verify database state
    print("\n3️⃣ Verifying database state...")
    try:
        db_path = os.path.join(os.path.dirname(
            __file__), "analytics_data_good.sqlite")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute(
                "SELECT is_in_checkin_flow_mon, is_in_checkin_flow_wed FROM users WHERE ig_username = ?",
                (test_ig_username,)
            )
            result = c.fetchone()
            conn.close()

            if result:
                mon_status, wed_status = result
                print(
                    f"📊 Database state: Monday={bool(mon_status)}, Wednesday={bool(wed_status)}")
                if wed_status:  # Should be Wednesday based on last update
                    print("✅ Database state matches expected (Wednesday active)")
                else:
                    print("⚠️ Database state doesn't match expected")
            else:
                print("ℹ️ Test user not found in database (might be expected)")
        else:
            print(f"⚠️ Database not found at: {db_path}")
    except Exception as e:
        print(f"❌ Database verification failed: {e}")

    # Clean up test data
    print("\n4️⃣ Cleaning up test data...")
    try:
        db_path = os.path.join(os.path.dirname(
            __file__), "analytics_data_good.sqlite")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE ig_username = ?",
                      (test_ig_username,))
            c.execute("DELETE FROM messages WHERE ig_username = ?",
                      (test_ig_username,))
            conn.commit()
            conn.close()
            print("✅ Test data cleaned up")
    except Exception as e:
        print(f"⚠️ Cleanup failed (might be OK): {e}")

    print("\n🎉 Check-in trigger test completed!")


if __name__ == "__main__":
    test_checkin_triggers()
