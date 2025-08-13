#!/usr/bin/env python3
"""Direct test of check-in functionality without user_profiles import"""

import sys
import os
import sqlite3

# Add the parent directory to the path
sys.path.append(os.path.dirname(__file__))

print("🧪 Direct Check-in Test")

# Test 1: Direct import of webhook_handlers
try:
    from webhook_handlers import update_analytics_data
    print("✅ update_analytics_data imported successfully")

    # Test 2: Test the function directly
    test_ig_username = "test_checkin_direct"
    print(f"📞 Testing check-in trigger for {test_ig_username}...")

    # Test Monday check-in
    try:
        update_analytics_data(
            ig_username=test_ig_username,
            user_message="",  # Empty message since this is manual trigger
            ai_response="",   # Empty response since this is manual trigger
            subscriber_id="test_subscriber_123",
            first_name="Test",
            last_name="User",
            is_in_checkin_flow_mon=True,
            is_in_checkin_flow_wed=False
        )
        print("✅ Monday check-in trigger successful")

        # Verify in database
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
                if mon_status:
                    print("✅ Database correctly shows Monday check-in active")
                else:
                    print("❌ Database doesn't show Monday check-in active")
            else:
                print("⚠️ User not found in database after update")

        # Clean up test data
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
        print(f"❌ Monday check-in test failed: {e}")

except ImportError as e:
    print(f"❌ Could not import update_analytics_data: {e}")

print("\n🎉 Direct check-in test completed!")
