
import sqlite3
import os
import logging
from typing import Optional, Any, Dict, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_PATH = os.path.join("app", "analytics_data_good.sqlite")


def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise


def initialize_schema():
    """
    Initializes the database schema, creating tables if they don't exist.
    This can be expanded to create all necessary tables for the application.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    ig_username TEXT,
                    subscriber_id TEXT
                );
            """)
            logging.info(
                "Database schema initialized successfully. 'system_logs' table is ready.")
    except sqlite3.Error as e:
        logging.error(f"Schema initialization error: {e}")
    finally:
        conn.close()


if __name__ == '__main__':
    # This allows the script to be run directly to initialize the database
    initialize_schema()
