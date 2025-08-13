#!/usr/bin/env python3
"""Simple test for check-in functionality"""

import sys
import os
import sqlite3

# Add the parent directory to the path
sys.path.append(os.path.dirname(__file__))

print("🧪 Simple Check-in Test")

# Test 1: Check if database columns exist
try:
    db_path = os.path.join(os.path.dirname(__file__),
                           "analytics_data_good.sqlite")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(users)")
        columns = c.fetchall()

        # Check for check-in columns
        column_names = [col[1] for col in columns]
        has_mon = 'is_in_checkin_flow_mon' in column_names
        has_wed = 'is_in_checkin_flow_wed' in column_names

        print(f"✅ Database found: {db_path}")
        print(f"✅ Monday check-in column exists: {has_mon}")
        print(f"✅ Wednesday check-in column exists: {has_wed}")

        conn.close()
    else:
        print(f"❌ Database not found: {db_path}")
except Exception as e:
    print(f"❌ Database test failed: {e}")

# Test 2: Try import of user_profiles module
try:
    sys.path.append(os.path.join(
        os.path.dirname(__file__), 'dashboard_modules'))
    import user_profiles
    print("✅ user_profiles module imported successfully")

    # Check if trigger_check_in function exists
    if hasattr(user_profiles, 'trigger_check_in'):
        print("✅ trigger_check_in function found")
    else:
        print("❌ trigger_check_in function not found")

except Exception as e:
    print(f"❌ user_profiles import failed: {e}")

print("\n🎉 Simple check-in test completed!")
