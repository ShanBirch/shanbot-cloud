import sqlite3


def check_user_in_db():
    try:
        conn = sqlite3.connect('analytics_data_good.sqlite')
        cursor = conn.cursor()

        # Check available tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Available tables:", tables)

        # Check for interstellarwitch in users table
        cursor.execute(
            "SELECT * FROM users WHERE ig_username LIKE ?", ('%interstellarwitch%',))
        user_results = cursor.fetchall()
        print(
            f"Users table search for 'interstellarwitch': {user_results if user_results else 'No records found'}")

        # Also check messages table if it exists
        try:
            cursor.execute(
                "SELECT * FROM messages WHERE ig_username LIKE ?", ('%interstellarwitch%',))
            message_results = cursor.fetchall()
            print(
                f"Messages table search for 'interstellarwitch': {message_results if message_results else 'No records found'}")
        except sqlite3.OperationalError as e:
            print(f"Messages table query error: {e}")

        # Check total number of users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        print(f"Total users in database: {total_users}")

        conn.close()

    except Exception as e:
        print(f"Error checking database: {e}")


if __name__ == "__main__":
    check_user_in_db()
