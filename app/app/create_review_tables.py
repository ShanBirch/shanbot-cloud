import sqlite3
import os

# Determine the absolute path to the database, assuming it's in the same directory as this script
# or in a known relative location. For now, let's assume it's in the same 'app' directory.
# If analytics_data_good.sqlite is in the 'app' directory:
DB_PATH = os.path.join(os.path.dirname(__file__), "analytics_data_good.sqlite")

# If analytics_data_good.sqlite is in the main 'shanbot' directory (one level up from 'app'):
# DB_PATH = os.path.join(os.path.dirname(__file__), "..", "analytics_data_good.sqlite")

# Or, if you prefer an absolute path (less portable but explicit):
# DB_PATH = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\app\\analytics_data_good.sqlite"


create_pending_reviews_table_sql = """
CREATE TABLE IF NOT EXISTS pending_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_ig_username TEXT NOT NULL,
    user_subscriber_id TEXT NOT NULL,
    incoming_message_text TEXT,
    incoming_message_timestamp TEXT,
    generated_prompt_text TEXT,
    proposed_response_text TEXT,
    status TEXT DEFAULT \'pending_review\',
    created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_timestamp TEXT,
    final_response_text TEXT
);
"""

create_learning_feedback_log_table_sql = """
CREATE TABLE IF NOT EXISTS learning_feedback_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER,
    user_ig_username TEXT,
    user_subscriber_id TEXT,
    original_prompt_text TEXT,
    original_gemini_response TEXT,
    edited_response_text TEXT,
    user_notes TEXT,
    is_good_example_for_few_shot INTEGER DEFAULT 0,
    logged_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES pending_reviews(review_id)
);
"""


def main():
    conn = None
    try:
        print(f"Attempting to connect to database at: {DB_PATH}")
        if not os.path.exists(os.path.dirname(DB_PATH)):
            print(
                f"Error: The directory for the database does not exist: {os.path.dirname(DB_PATH)}")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("Executing SQL to create pending_reviews table (if not exists)...")
        cursor.execute(create_pending_reviews_table_sql)
        print("'pending_reviews' table processed.")

        print("Executing SQL to create learning_feedback_log table (if not exists)...")
        cursor.execute(create_learning_feedback_log_table_sql)
        print("'learning_feedback_log' table processed.")

        conn.commit()
        print("Tables created successfully (or already existed).")

    except sqlite3.Error as e:
        print(f"An SQLite error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    main()
