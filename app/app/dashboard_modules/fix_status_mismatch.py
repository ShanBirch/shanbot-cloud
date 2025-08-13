#!/usr/bin/env python3
"""Fix status mismatch for scheduled responses"""

import sqlite3
from datetime import datetime


def main():
    try:
        conn = sqlite3.connect('../analytics_data_good.sqlite')
        cursor = conn.cursor()

        print("=== BEFORE FIX ===")
        cursor.execute(
            "SELECT COUNT(*), status FROM scheduled_responses GROUP BY status")
        for row in cursor.fetchall():
            print(f"{row[1]}: {row[0]}")

        # Update pending to scheduled
        cursor.execute(
            "UPDATE scheduled_responses SET status = 'scheduled' WHERE status = 'pending'")
        updated = cursor.rowcount

        print(f"\n✅ Updated {updated} responses from 'pending' to 'scheduled'")

        # Show what's now due for sending
        current_time = datetime.now().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM scheduled_responses 
            WHERE status = 'scheduled' 
            AND scheduled_send_time <= ?
        """, (current_time,))

        due_count = cursor.fetchone()[0]
        print(f"📤 Responses now due for sending: {due_count}")

        # Show all current statuses
        print("\n=== AFTER FIX ===")
        cursor.execute(
            "SELECT COUNT(*), status FROM scheduled_responses GROUP BY status")
        for row in cursor.fetchall():
            print(f"{row[1]}: {row[0]}")

        conn.commit()
        conn.close()

        print(
            f"\n🎉 Status mismatch fixed! Auto sender should now find the {due_count} overdue responses.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
