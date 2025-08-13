import sqlite3
from datetime import datetime, timedelta


def main():
    print("🚀 Quick Auto Response System Test")
    print("=" * 50)

    # Test database connection
    try:
        db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("✅ Database connection successful")

        # Check scheduled responses table
        cursor.execute("SELECT COUNT(*) FROM scheduled_responses")
        total = cursor.fetchone()[0]
        print(f"📊 Total scheduled responses: {total}")

        # Check status breakdown
        cursor.execute(
            "SELECT status, COUNT(*) FROM scheduled_responses GROUP BY status")
        status_counts = cursor.fetchall()
        print("\n📈 Status breakdown:")
        for status, count in status_counts:
            print(f"  {status or 'NULL'}: {count}")

        # Update any NULL status to scheduled
        cursor.execute(
            "UPDATE scheduled_responses SET status = 'scheduled' WHERE status IS NULL")
        null_updated = cursor.rowcount
        if null_updated > 0:
            print(f"\n🔧 Updated {null_updated} NULL statuses to 'scheduled'")
            conn.commit()

        # Check for overdue responses
        current_time = datetime.now().isoformat()
        cursor.execute("""
            SELECT schedule_id, user_ig_username, scheduled_send_time, status 
            FROM scheduled_responses 
            WHERE status = 'scheduled' AND scheduled_send_time <= ?
            ORDER BY scheduled_send_time ASC
            LIMIT 5
        """, (current_time,))

        overdue = cursor.fetchall()
        print(f"\n⏰ Responses due for sending: {len(overdue)}")
        for row in overdue:
            print(f"  ID {row[0]}: @{row[1]} at {row[2]}")

        # Create a test response if none exist
        if len(overdue) == 0:
            print("\n📝 Creating test response...")
            test_time = (datetime.now() - timedelta(minutes=1)).isoformat()
            cursor.execute("""
                INSERT INTO scheduled_responses (
                    review_id, user_ig_username, user_subscriber_id, response_text,
                    scheduled_send_time, status, incoming_message_text,
                    incoming_message_timestamp, calculated_delay_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                999999,
                'test_user_' + datetime.now().strftime('%H%M%S'),
                'test_subscriber',
                'Test auto response from quick test script',
                test_time,
                'scheduled',
                'Test incoming message',
                test_time,  # Use same time for incoming message timestamp
                1
            ))

            test_id = cursor.lastrowid
            print(f"✅ Created test response ID {test_id}")
            conn.commit()

            # Check again for due responses
            cursor.execute("""
                SELECT schedule_id, user_ig_username, scheduled_send_time, status 
                FROM scheduled_responses 
                WHERE status = 'scheduled' AND scheduled_send_time <= ?
                ORDER BY scheduled_send_time ASC
                LIMIT 5
            """, (current_time,))

            overdue = cursor.fetchall()
            print(f"\n🔄 After creating test, responses due: {len(overdue)}")
            for row in overdue:
                print(f"  ID {row[0]}: @{row[1]} at {row[2]}")

        conn.close()

        # Check auto mode status
        print("\n🔧 Checking auto mode status...")
        import json
        import os

        status_file = "auto_mode_status.json"
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                auto_status = json.load(f)
            print(
                f"Auto Mode: {'ENABLED' if auto_status.get('auto_mode_enabled') else 'DISABLED'}")
            print(
                f"Last updated: {auto_status.get('last_updated', 'Unknown')}")
        else:
            print("❌ Auto mode status file not found")
            # Create it
            auto_status = {
                'auto_mode_enabled': True,
                'last_updated': datetime.now().isoformat(),
                'updated_by': 'quick_test'
            }
            with open(status_file, 'w') as f:
                json.dump(auto_status, f, indent=2)
            print("✅ Created auto mode status file (ENABLED)")

        print("\n" + "=" * 50)
        print("🎉 Quick test completed!")
        print("\nNext steps:")
        print("1. Run 'python response_auto_sender.py' to test the auto sender")
        print("2. Check the dashboard Response Review Queue")
        print("3. Try enabling/disabling Auto Mode in the dashboard")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
