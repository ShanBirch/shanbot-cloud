#!/usr/bin/env python3
"""
Simple test for stage switching
"""

import sys
import os
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), 'dashboard_modules'))

try:
    from dashboard_sqlite_utils import load_conversations_from_sqlite, save_metrics_to_sqlite
    from user_profiles import update_user_stage

    print("✅ Imports successful!")

    # Load conversations
    conversations = load_conversations_from_sqlite()
    print(f"📊 Loaded {len(conversations)} users from database")

    if conversations:
        # Get first user for testing
        test_username = list(conversations.keys())[0]
        test_user_data = conversations[test_username]
        test_ig_username = test_user_data['metrics'].get(
            'ig_username', test_username)

        print(f"🧪 Testing with user: {test_ig_username}")

        # Test updating to Lead stage
        print("🔄 Testing stage update to Lead...")
        success = update_user_stage(test_ig_username, "Lead", test_user_data)

        if success:
            print("✅ Stage switching functionality works!")
        else:
            print("❌ Stage switching failed")
    else:
        print("❌ No users found in database")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("�� Test completed")
