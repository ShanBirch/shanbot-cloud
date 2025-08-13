import logging
import sqlite3
import os

logger = logging.getLogger(__name__)

# Correctly determine the absolute path to the database
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(APP_DIR, "analytics_data_good.sqlite")


def get_db_connection():
    """Establish and return a database connection."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise


def ensure_db_structure():
    """
    Ensures the database schema is up-to-date.
    Checks for the 'users' table and adds any missing columns.
    """
    logger.info("Ensuring database schema is up-to-date...")
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()

            # 1. Check if 'users' table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone() is None:
                logger.warning(
                    "Table 'users' not found. Skipping schema update for now.")
                return

            # 2. Get existing columns from the 'users' table
            cursor.execute("PRAGMA table_info(users)")
            existing_columns = {row['name'] for row in cursor.fetchall()}
            logger.debug(
                f"Existing columns in 'users' table: {sorted(list(existing_columns))}")

            # 3. Define all expected columns and their types
            expected_columns = {
                'ig_username': 'TEXT PRIMARY KEY', 'subscriber_id': 'TEXT UNIQUE', 'first_name': 'TEXT',
                'last_name': 'TEXT', 'email': 'TEXT', 'client_status': 'TEXT', 'journey_stage': 'TEXT',
                'is_in_checkin_flow_mon': 'BOOLEAN', 'is_in_checkin_flow_wed': 'BOOLEAN',
                'last_interaction_timestamp': 'TEXT', 'client_analysis_json': 'TEXT', 'is_onboarding': 'BOOLEAN',
                'onboarding_step': 'TEXT', 'paid_client': 'BOOLEAN', 'has_active_subscription': 'BOOLEAN',
                'subscription_id': 'TEXT', 'phone_number': 'TEXT', 'timezone': 'TEXT',
                'last_checkin_timestamp': 'TEXT', 'needs_special_care': 'BOOLEAN',
                'special_care_details': 'TEXT', 'offer_made': 'BOOLEAN', 'is_in_ad_flow': 'BOOLEAN',
                'ad_script_state': 'TEXT', 'ad_scenario': 'INTEGER', 'lead_source': 'TEXT'
            }

            # 4. Add any missing columns
            added_columns = False
            for col_name, col_type in expected_columns.items():
                if col_name not in existing_columns:
                    try:
                        logger.info(
                            f"Adding missing column '{col_name}' to 'users' table...")
                        cursor.execute(
                            f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                        added_columns = True
                    except sqlite3.OperationalError as e:
                        logger.error(f"Failed to add column '{col_name}': {e}")

            if not added_columns:
                logger.info("✓ 'users' table schema is already up-to-date.")
            else:
                logger.info(
                    "✓ 'users' table schema has been successfully updated.")

    except sqlite3.Error as e:
        logger.error(f"A database error occurred during schema check: {e}")
    finally:
        if conn:
            conn.close()


def initialize_database():
    """Initializes all necessary tables and ensures the schema is correct."""
    logger.info("Initializing database...")
    ensure_db_structure()
    # You can add other table initializations here if needed in the future
    logger.info("✓ Database initialization complete.")


if __name__ == '__main__':
    # Allows running this script directly to set up the DB
    logging.basicConfig(level=logging.INFO)
    initialize_database()
