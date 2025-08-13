#!/usr/bin/env python3
"""Debug scheduled responses"""

import sqlite3
from datetime import datetime


def main():
    try:
        conn = sqlite3.connect('../analytics_data_good.sqlite')
        cursor = conn.cursor()

        # Check recent scheduled responses
        cursor.execute('''
            SELECT schedule_id, user_ig_username, status, scheduled_send_time, created_at 
            FROM scheduled_responses 
            ORDER BY schedule_id DESC 
            LIMIT 5
        ''')

        rows = cursor.fetchall()

        print("=== RECENT SCHEDULED RESPONSES ===")
        print("ID | Username | Status | Send Time | Created")
        print("-" * 60)

        if rows:
            for row in rows:
                print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")
        else:
            print("No scheduled responses found")

        # Check current time vs scheduled times
        current_time = datetime.now().isoformat()
        print(f"\nCurrent time: {current_time}")

        # Check what auto sender should find
        cursor.execute('''
            SELECT COUNT(*) FROM scheduled_responses 
            WHERE status = 'scheduled' 
            AND datetime(scheduled_send_time) <= datetime('now')
        ''')

        due_count = cursor.fetchone()[0]
        print(f"\nResponses due for sending now: {due_count}")

        # Check all scheduled (not sent)
        cursor.execute('''
            SELECT COUNT(*) FROM scheduled_responses 
            WHERE status = 'scheduled'
        ''')

        total_scheduled = cursor.fetchone()[0]
        print(f"Total scheduled (not sent): {total_scheduled}")

        # Show specific due responses
        if due_count > 0:
            cursor.execute('''
                SELECT schedule_id, user_ig_username, scheduled_send_time 
                FROM scheduled_responses 
                WHERE status = 'scheduled' 
                AND datetime(scheduled_send_time) <= datetime('now')
                ORDER BY scheduled_send_time
            ''')

            due_responses = cursor.fetchall()
            print(f"\nDUE RESPONSES ({due_count}):")
            for resp in due_responses:
                print(f"  ID {resp[0]} -> {resp[1]} (was due at {resp[2]})")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
