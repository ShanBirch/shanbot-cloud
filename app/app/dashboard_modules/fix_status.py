#!/usr/bin/env python3
"""Fix the status issue for scheduled responses"""

import sqlite3
from datetime import datetime


def fix_status():
    # Connect to database
    conn = sqlite3.connect('../analytics_data_good.sqlite')
    cursor = conn.cursor()

    # Show current status
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

    # Show what's due now
    current_time = datetime.now().isoformat()
    cursor.execute("""
    SELECT user_ig_username, scheduled_send_time, status 
    FROM scheduled_responses 
    WHERE status = 'scheduled' AND scheduled_send_time <= ?
    ORDER BY scheduled_send_time
    """, (current_time,))

    due_now = cursor.fetchall()
    print(f"\n=== RESPONSES DUE NOW ({len(due_now)}) ===")
    for row in due_now:
        print(f"👤 {row[0]} - {row[1]} ({row[2]})")

    # Show after fix
    print("\n=== AFTER FIX ===")
    cursor.execute(
        "SELECT COUNT(*), status FROM scheduled_responses GROUP BY status")
    for row in cursor.fetchall():
        print(f"{row[1]}: {row[0]}")

    conn.commit()
    conn.close()

    print(f"\n🎯 Your auto sender should now process {len(due_now)} responses!")
    print("💡 Go check your auto sender terminal - it should find them now!")


if __name__ == "__main__":
    fix_status()
