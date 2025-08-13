#!/usr/bin/env python3
"""Check pending_reviews table schema"""

import sqlite3


def main():
    try:
        conn = sqlite3.connect('../analytics_data_good.sqlite')
        cursor = conn.cursor()

        # Check pending_reviews table schema
        cursor.execute('PRAGMA table_info(pending_reviews)')
        schema = cursor.fetchall()

        print("pending_reviews table schema:")
        for row in schema:
            print(f"- {row[1]} ({row[2]})")

        # Check if it has review_id column
        has_review_id = any(row[1] == 'review_id' for row in schema)
        print(f"\nHas review_id column: {has_review_id}")

        # Check sample data
        cursor.execute('SELECT COUNT(*) FROM pending_reviews')
        count = cursor.fetchone()[0]
        print(f"Records count: {count}")

        if count > 0:
            cursor.execute('SELECT * FROM pending_reviews LIMIT 1')
            sample = cursor.fetchone()
            print(f"Sample record: {sample}")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
