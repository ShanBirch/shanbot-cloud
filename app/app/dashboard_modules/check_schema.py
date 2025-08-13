#!/usr/bin/env python3
"""Check table schema"""

import sqlite3


def main():
    try:
        conn = sqlite3.connect('../analytics_data_good.sqlite')
        cursor = conn.cursor()

        cursor.execute('PRAGMA table_info(scheduled_responses)')
        schema = cursor.fetchall()

        print('scheduled_responses table schema:')
        print('Column | Type | NotNull | Default')
        print('-' * 40)

        for row in schema:
            print(f'{row[1]} | {row[2]} | {row[3]} | {row[4]}')

        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
