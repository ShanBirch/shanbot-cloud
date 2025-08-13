import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

# Construct the absolute path to the SQLite database
# App directory is the parent of the current file's directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(APP_DIR, "analytics_data_good.sqlite")

# Fallback logic in case the above relative pathing fails (e.g. script is run from a different CWD)
if not os.path.exists(SQLITE_DB_PATH):
    logger.warning(
        f"Database not found at calculated path: {SQLITE_DB_PATH}. Trying fallback path.")
    # This is a hardcoded path, which is not ideal but serves as a backup
    SQLITE_DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
    logger.info(f"Using fallback DB path: {SQLITE_DB_PATH}")


def ensure_db_structure():
    """
    Connects to the SQLite database and ensures the 'users' table has all
    the necessary columns, adding any that are missing. This makes the schema
    more robust to changes. Also ensures 'messages' table exists.
    """
    required_columns = {
        'ig_username': 'TEXT PRIMARY KEY',
        'subscriber_id': 'TEXT UNIQUE',
        'first_name': 'TEXT',
        'last_name': 'TEXT',
        'email': 'TEXT',
        'client_status': 'TEXT',
        'journey_stage': 'TEXT',
        'is_in_checkin_flow_mon': 'BOOLEAN',
        'is_in_checkin_flow_wed': 'BOOLEAN',
        'last_interaction_timestamp': 'TEXT',
        'client_analysis_json': 'TEXT',
        'is_onboarding': 'BOOLEAN DEFAULT FALSE',
        'is_in_ad_flow': 'BOOLEAN DEFAULT FALSE',
        'ad_script_state': 'TEXT',
        'ad_scenario': 'INTEGER',
        'lead_source': 'TEXT'
    }

    conn = None
    try:
        logger.info(f"Ensuring DB structure for {SQLITE_DB_PATH}")
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()

        # Check for users table and create if it doesn't exist
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS users (ig_username TEXT PRIMARY KEY)")

        # Get existing columns from the users table
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        logger.debug(f"Existing columns in 'users' table: {existing_columns}")

        # Add any missing columns to the users table
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                logger.info(
                    f"Column '{col_name}' not found in 'users' table. Adding it.")
                try:
                    cursor.execute(
                        f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Successfully added column '{col_name}'.")
                except sqlite3.OperationalError as e:
                    logger.error(
                        f"Failed to add column '{col_name}': {e}. This might happen in rare race conditions but is generally safe to ignore.")

        # Check for messages table and create if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ig_username TEXT,
                timestamp TEXT,
                type TEXT,
                text TEXT,
                FOREIGN KEY (ig_username) REFERENCES users (ig_username)
            )
        """)

        conn.commit()
        logger.info("Database schema verification complete.")

    except sqlite3.Error as e:
        logger.error(f"Database error during schema check: {e}")
    finally:
        if conn:
            conn.close()
