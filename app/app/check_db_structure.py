import sqlite3
import json


def check_db_structure():
    """Check the database structure and Lia_romy's messages"""
    try:
        conn = sqlite3.connect('app/analytics_data_good.sqlite')
        cursor = conn.cursor()

        # Check available tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Available tables:", tables)

        # Check users table structure
        cursor.execute("PRAGMA table_info(users)")
        users_columns = cursor.fetchall()
        print("\nUsers table columns:")
        for col in users_columns:
            print(f"  {col[1]} {col[2]}")

        # Check messages table structure
        cursor.execute("PRAGMA table_info(messages)")
        messages_columns = cursor.fetchall()
        print("\nMessages table columns:")
        for col in messages_columns:
            print(f"  {col[1]} {col[2]}")

        # Check for blissedlia in users table
        cursor.execute("SELECT * FROM users WHERE ig_username = 'blissedlia'")
        user_result = cursor.fetchone()
        print(f"\nUser blissedlia found: {user_result is not None}")

        if user_result:
            print(f"User data: {user_result}")

        # Check messages for blissedlia
        cursor.execute(
            "SELECT * FROM messages WHERE ig_username = 'blissedlia' ORDER BY timestamp")
        messages = cursor.fetchall()
        print(f"\nTotal messages for blissedlia: {len(messages)}")

        print("\nLast 10 messages for blissedlia:")
        for i, msg in enumerate(messages[-10:], 1):
            print(f"{i}. Type: {msg[3]}, Text: {msg[4][:100]}...")

        conn.close()

    except Exception as e:
        print(f"Error checking database: {e}")


if __name__ == "__main__":
    check_db_structure()
