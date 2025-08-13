import sqlite3

try:
    conn = sqlite3.connect('analytics_data_good.sqlite')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT ig_username, client_status, bio FROM users WHERE ig_username = 'interstellarwitch'")
    result = cursor.fetchone()

    if result:
        print(
            f"User found: {result[0]}, Status: {result[1]}, Bio: {result[2]}")
    else:
        print("User not found")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
