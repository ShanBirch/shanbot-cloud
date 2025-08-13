# DUMMY streamlit module to avoid heavy import when used server-side
import sys
import types
if 'streamlit' not in sys.modules:
    dummy = types.ModuleType('streamlit')

    def _noop(*args, **kwargs):
        return None
    dummy.__getattr__ = lambda name: _noop
    sys.modules['streamlit'] = dummy

import logging
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import time
import random
import re  # Added for column type manipulation
import json  # Added for JSON parsing

logger = logging.getLogger(__name__)

# Define the absolute path to the Instagram analyzer script
# Assuming it's in the same directory as this script for now, adjust if needed.
# Construct the absolute path to the SQLite database
# Current file: C:\Users\Shannon\OneDrive\Desktop\shanbot\app\dashboard_modules\dashboard_sqlite_utils.py
# DB location:  C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SQLITE_DB_PATH = os.path.join(APP_DIR, "analytics_data_good.sqlite")
ANALYZER_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "anaylize_followers.py")

# Fallback logic in case the above relative pathing fails (e.g. sharing the script)
if not os.path.exists(SQLITE_DB_PATH):
    SQLITE_DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
if not os.path.exists(ANALYZER_SCRIPT_PATH):
    ANALYZER_SCRIPT_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\anaylize_followers.py"

logger.info(f"Using SQLite DB Path: {SQLITE_DB_PATH}")
logger.info(f"Using Analyzer Script Path: {ANALYZER_SCRIPT_PATH}")


def ensure_db_schema():
    """
    Ensure the database has the required tables and columns.
    """
    logger.info(f"Checking database schema at {SQLITE_DB_PATH}...")
    try:
        with get_db_connection() as conn:
            # Ensure all core tables exist
            ensure_core_tables_exist(conn)

            # Ensure nutrition/calorie tracking columns exist on users
            try:
                ensure_all_columns_exist(conn, 'users', {
                    'calorie_tracking_json': 'TEXT',
                    'metrics_json': 'TEXT',
                    'is_in_calorie_flow': 'INTEGER DEFAULT 0',
                })
            except Exception:
                pass
            logger.info("All core tables verified.")

    except sqlite3.Error as e:
        logger.error(f"Database error in ensure_db_schema: {e}", exc_info=True)
    except Exception as e:
        logger.error(
            f"Unexpected error in ensure_db_schema: {e}", exc_info=True)


def initialize_database():
    """Initializes the database and ensures table structures are correct."""
    logger.info("Initializing database...")
    conn = None
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()

        # ... (rest of the initialize_database function remains the same)
        c.execute('''
            CREATE TABLE IF NOT EXISTS paid_challenge_bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                booking_date TEXT,
                payment_status TEXT,
                challenge_type TEXT
            )
        ''')

        conn.commit()
        logger.info("Successfully ensured all tables exist.")

        # Call the new schema check function
        ensure_db_schema()

    except Exception as e:
        logger.error(f"Error initializing database: {e}")


def get_db_connection():
    """Get a tuned SQLite connection for faster dashboard reads."""
    # The schema check should be done once at startup, not per-connection.
    # ensure_db_schema()
    conn = sqlite3.connect(
        SQLITE_DB_PATH, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        # Pragmas to improve read performance for dashboard workloads
        # WAL enables concurrent reads while writes happen
        conn.execute("PRAGMA journal_mode=WAL;")
        # Reasonable durability/perf tradeoff
        conn.execute("PRAGMA synchronous=NORMAL;")
        # Keep temps in memory where possible
        conn.execute("PRAGMA temp_store=MEMORY;")
        # Expand page cache (~64MB, negative means KB units)
        conn.execute("PRAGMA cache_size=-65536;")
        # Busy timeout to avoid immediate lock errors
        conn.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        # Pragmas are best-effort; ignore if not supported
        pass
    return conn


def create_all_tables_if_not_exists(conn):
    """Helper to ensure all necessary tables exist."""
    create_workout_tables_if_not_exist(conn)
    create_conversation_history_table_if_not_exists(conn)
    create_scheduled_responses_table_if_not_exists(conn)
    create_auto_mode_tracking_tables_if_not_exists(conn)
    create_paid_challenge_bookings_table_if_not_exists(conn)
    create_learning_feedback_log_table_if_not_exists(conn)  # Add this line
    # Also ensure the main users and messages tables are covered
    ensure_db_schema()
    logger.info("All core tables verified.")


def create_workout_tables_if_not_exist(conn):
    """Ensures the client_workouts and client_workout_sessions tables exist."""
    try:
        cursor = conn.cursor()
        # client_workouts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                workout_name TEXT NOT NULL,
                date_assigned TEXT,
                is_completed INTEGER DEFAULT 0,
                UNIQUE(client_id, workout_name)
            )
        ''')

        # client_workout_sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_workout_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER,
                session_date TEXT,
                notes TEXT,
                FOREIGN KEY(workout_id) REFERENCES client_workouts(id)
            )
        ''')

        # Drop the old unique index if it exists
        try:
            cursor.execute(
                "DROP INDEX IF EXISTS idx_unique_workout_session")
            logger.info("Attempted to drop old unique index if it existed.")
        except sqlite3.OperationalError:
            pass  # Index didn't exist, which is fine

        # Create the new, more specific unique index
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_workout_session_v2 ON client_workout_sessions (workout_id, session_date)
        ''')
        logger.info(
            "Ensured new unique index idx_unique_workout_session_v2 exists.")

        conn.commit()
        logger.info(
            "Successfully ensured 'client_workout_sessions' table structure and unique index are up-to-date.")

    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating workout tables: {e}")


def create_conversation_history_table_if_not_exists(conn):
    """Ensures the 'conversation_history' table exists for logging messages."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ig_username TEXT NOT NULL,
                subscriber_id TEXT,
                timestamp TEXT,
                message_type TEXT,
                message_text TEXT
            )
        ''')
        conn.commit()
        logger.info("Ensured 'conversation_history' table exists.")
    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating the conversation_history table: {e}")


def create_scheduled_responses_table_if_not_exists(conn):
    """Ensures the 'scheduled_responses' table exists for follow-ups."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER,
                user_ig_username TEXT,
                user_subscriber_id TEXT,
                response_text TEXT,
                incoming_message_text TEXT,
                incoming_message_timestamp TEXT,
                user_response_time TEXT,
                calculated_delay_minutes INTEGER,
                scheduled_send_time TEXT,
                status TEXT DEFAULT 'scheduled',
                user_notes TEXT,
                manual_context TEXT,
                FOREIGN KEY(review_id) REFERENCES pending_reviews(id)
            )
        ''')
        conn.commit()
        logger.info("Ensured 'scheduled_responses' table exists.")
    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating the scheduled_responses table: {e}")


def ensure_pending_reviews_rationale_column(conn: sqlite3.Connection):
    """Ensure pending_reviews has a model_rationale column for reviewer explanations."""
    try:
        cursor = conn.cursor()
        # Check if column exists
        cursor.execute("PRAGMA table_info(pending_reviews)")
        cols = [row[1] for row in cursor.fetchall()]
        if "model_rationale" not in cols:
            cursor.execute(
                "ALTER TABLE pending_reviews ADD COLUMN model_rationale TEXT")
            conn.commit()
            logger.info("Added model_rationale column to pending_reviews")
    except sqlite3.Error as e:
        # If table doesn't exist here, skip; it's created elsewhere in the system
        logger.warning(
            f"Could not ensure model_rationale column on pending_reviews: {e}")


def create_review_candidates_table_if_not_exists(conn: sqlite3.Connection):
    """Create table to store multiple candidate responses for a review."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS review_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                variant_index INTEGER NOT NULL,
                response_text TEXT NOT NULL,
                is_selected INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(review_id, variant_index),
                FOREIGN KEY(review_id) REFERENCES pending_reviews(id)
            )
            '''
        )
        conn.commit()
        logger.info("Ensured review_candidates table exists.")
    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating the review_candidates table: {e}")


def save_review_rationale(review_id: int, rationale: str) -> bool:
    """Persist model rationale for a pending review."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE pending_reviews SET model_rationale = ? WHERE review_id = ?",
            (rationale, review_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Error saving rationale for review {review_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_review_rationale(review_id: int) -> Optional[str]:
    """Fetch stored rationale text for a review (if any)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT model_rationale FROM pending_reviews WHERE review_id = ?",
            (review_id,),
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching rationale for review {review_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def save_review_candidates(review_id: int, responses: list[str]) -> bool:
    """Replace candidate responses for a review with new variants."""
    conn = get_db_connection()
    try:
        create_review_candidates_table_if_not_exists(conn)
        cursor = conn.cursor()
        # Clear existing
        cursor.execute("DELETE FROM review_candidates WHERE review_id = ?",
                       (review_id,))
        # Insert new
        for idx, text in enumerate(responses, start=1):
            cursor.execute(
                "INSERT INTO review_candidates (review_id, variant_index, response_text) VALUES (?, ?, ?)",
                (review_id, idx, text),
            )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error saving review candidates for {review_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_review_candidates(review_id: int) -> list[dict]:
    """Return candidate responses for a review, ordered by variant_index."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        create_review_candidates_table_if_not_exists(conn)
        cursor.execute(
            "SELECT variant_index, response_text, is_selected FROM review_candidates WHERE review_id = ? ORDER BY variant_index ASC",
            (review_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "variant_index": r[0],
                "response_text": r[1],
                "is_selected": bool(r[2]) if r[2] is not None else False,
            }
            for r in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"Error fetching review candidates for {review_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def mark_review_candidate_selected(review_id: int, variant_index: int) -> bool:
    """Mark one candidate as selected and unselect others for the review."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE review_candidates SET is_selected = 0 WHERE review_id = ?",
            (review_id,),
        )
        cursor.execute(
            "UPDATE review_candidates SET is_selected = 1 WHERE review_id = ? AND variant_index = ?",
            (review_id, variant_index),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(
            f"Error marking selected candidate for review {review_id}, variant {variant_index}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_auto_mode_tracking_tables_if_not_exists(conn):
    """Ensures all auto mode tracking tables exist."""
    try:
        cursor = conn.cursor()

        # Auto mode sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_mode_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                total_responses_sent INTEGER DEFAULT 0,
                total_errors INTEGER DEFAULT 0
            )
        ''')

        # Auto mode responses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_mode_responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                review_id INTEGER,
                ig_username TEXT,
                response_text TEXT,
                timestamp TEXT,
                status TEXT,
                error_message TEXT,
                FOREIGN KEY(session_id) REFERENCES auto_mode_sessions(session_id),
                FOREIGN KEY(review_id) REFERENCES pending_reviews(id)
            )
        ''')

        # Auto mode heartbeat table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_mode_heartbeat (
                id INTEGER PRIMARY KEY,
                last_heartbeat TEXT,
                status TEXT DEFAULT 'active',
                additional_data TEXT
            )
        ''')

        # Auto mode processing table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_mode_processing (
                id INTEGER PRIMARY KEY,
                processing_status TEXT,
                details TEXT,
                timestamp TEXT
            )
        ''')

        # Auto mode activities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_mode_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT,
                details TEXT,
                success INTEGER DEFAULT 1,
                error_message TEXT,
                timestamp TEXT
            )
        ''')

        conn.commit()
        logger.info("Ensured all auto mode tracking tables exist.")
    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating auto mode tracking tables: {e}")


def create_paid_challenge_bookings_table_if_not_exists(conn):
    """Ensures the 'paid_challenge_bookings' table exists for tracking paid challenge sign-ups."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paid_challenge_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wix_order_id TEXT UNIQUE NOT NULL,
                ig_username TEXT,
                subscriber_id TEXT,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                booking_date TEXT,
                challenge_type TEXT,
                amount_paid REAL,
                is_processed INTEGER DEFAULT 0,
                processed_timestamp TEXT
            )
        ''')
        conn.commit()
        logger.info("Ensured 'paid_challenge_bookings' table exists.")
    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating the paid_challenge_bookings table: {e}")


def create_learning_feedback_log_table_if_not_exists(conn):
    """Ensures the 'learning_feedback_log' table exists for tracking review actions."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_feedback_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER,
                ig_username TEXT,
                subscriber_id TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                original_prompt_text TEXT,
                original_gemini_response TEXT,
                edited_response_text TEXT,
                user_notes TEXT,
                action_taken TEXT,
                is_good_example_for_few_shot INTEGER,
                FOREIGN KEY(review_id) REFERENCES pending_reviews(id)
            )
        ''')
        conn.commit()
        logger.info("Ensured 'learning_feedback_log' table exists.")
    except sqlite3.Error as e:
        logger.error(
            f"An error occurred while creating the learning_feedback_log table: {e}")


def ensure_core_tables_exist(conn):
    """Helper to ensure all necessary tables exist."""
    create_workout_tables_if_not_exist(conn)
    create_conversation_history_table_if_not_exists(conn)
    create_scheduled_responses_table_if_not_exists(conn)
    create_auto_mode_tracking_tables_if_not_exists(conn)
    create_paid_challenge_bookings_table_if_not_exists(
        conn)  # Add new table here
    # Ensure high-value indexes exist
    ensure_performance_indexes(conn)
    # Ensure rationale column and candidates table exist
    ensure_pending_reviews_rationale_column(conn)
    create_review_candidates_table_if_not_exists(conn)

    # Also ensure a simple meals table for per-meal logs (optional)
    try:
        cursor = conn.cursor()
        # Per-user nutrition profile table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_nutrition_profiles (
                ig_username TEXT PRIMARY KEY,
                sex TEXT,
                dob TEXT,
                age INTEGER,
                height_cm INTEGER,
                weight_kg REAL,
                activity_level TEXT,
                main_goal TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ig_username TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                meal_name TEXT,
                calories INTEGER,
                protein INTEGER,
                carbs INTEGER,
                fats INTEGER
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_meals_user_time ON meal_logs(ig_username, timestamp)')
        conn.commit()
    except sqlite3.Error:
        pass


def ensure_performance_indexes(conn: sqlite3.Connection):
    """Create the most impactful indexes used by the dashboard if they don't exist."""
    try:
        cur = conn.cursor()
        # Messages queried by user and timestamp (recent first)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_user_time ON messages(ig_username, timestamp);"
        )
        # Users looked up by ig_username and subscriber_id
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_ig ON users(ig_username);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_sub ON users(subscriber_id);"
        )
        # Pending reviews filtered by status and ordered by created time
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_reviews_status_time ON pending_reviews(status, created_timestamp);"
        )
        conn.commit()
        logger.info("Ensured performance indexes exist.")
    except sqlite3.Error as e:
        logger.warning(f"Could not create performance indexes: {e}")


# ... (The rest of your functions: load_conversations_from_sqlite, add_response_to_review_queue, etc.)
# Make sure to remove the old ensure_challenge_columns_exist function


def load_conversations_from_sqlite() -> Dict[str, Dict]:
    """Load all user conversations and metrics from SQLite with performance optimizations."""
    # Add caching to prevent repeated database calls
    import streamlit as st

    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def _load_conversations_cached():
        return _load_conversations_impl()

    return _load_conversations_cached()


def _load_conversations_impl() -> Dict[str, Dict]:
    """Internal implementation of conversation loading."""
    conn = None
    try:
        db_path = SQLITE_DB_PATH
        conn = get_db_connection()
        if not conn:
            return {}

        cursor = conn.cursor()

        # OPTIMIZATION: Add LIMIT for performance while keeping all fields
        cursor.execute("""
            SELECT ig_username, subscriber_id, metrics_json, calorie_tracking_json, 
                   workout_program_json, meal_plan_json, client_analysis_json, is_onboarding,
                   is_in_checkin_flow_mon, is_in_checkin_flow_wed, client_status, bio,
                   first_name, last_name, bio_analysis_status, last_updated, is_in_ad_flow,
                   ad_script_state, ad_scenario, lead_source, offer_made, challenge_email,
                   challenge_type, challenge_signup_date, paid_challenge_booking_status,
                   paid_challenge_booking_date, last_interaction_timestamp, bio_context,
                   client_stage, client_next_step, client_style, client_goals, client_barriers,
                   client_interests, client_motivation, client_personality, email, phone_number,
                   journey_stage, last_follow_up_timestamp, follow_up_count, tags
            FROM users
            WHERE ig_username IS NOT NULL AND ig_username != ''
            ORDER BY last_interaction_timestamp DESC
            LIMIT 1000  -- Limit to most recent 1000 users for performance
        """)
        users = cursor.fetchall()

        all_conversations = {}

        # OPTIMIZATION: Process users in batches to avoid memory issues
        batch_size = 100
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]

            for user_row in batch:
                ig_username = user_row[0]
                if not ig_username:
                    continue

                # OPTIMIZATION: Only load recent conversation history (last 100 messages)
                history = []

                # Get recent messages from the unified 'messages' table with tighter LIMIT
                cursor.execute(
                    """
                    SELECT timestamp, message_type, message_text, type, text, sender, message
                    FROM messages
                    WHERE ig_username = ?
                    ORDER BY timestamp DESC
                    LIMIT 30
                    """,
                    (ig_username,),
                )

                for row in cursor.fetchall():
                    timestamp, new_msg_type, new_msg_text, old_type, old_text, sender, message = row

                    # Use the new standardized columns first, fall back to old columns
                    final_type = new_msg_type if new_msg_type is not None else (
                        old_type if old_type is not None else sender)
                    final_text = new_msg_text if new_msg_text is not None else (
                        old_text if old_text is not None else message)

                    # Only add messages that have actual content
                    if final_text is not None and final_text.strip():
                        history.append({
                            "timestamp": timestamp,
                            "type": final_type if final_type is not None else "unknown",
                            "text": final_text,
                            "source": "unified_messages_table"
                        })

                # NOTE: conversation_history is no longer needed as all data is now in messages table

                # 3. Sort all messages chronologically and remove duplicates
                # Remove duplicates based on timestamp + text combination
                seen = set()
                unique_history = []
                for msg in history:
                    # Use first 50 chars to detect duplicates
                    key = (msg["timestamp"], msg["text"][:50])
                    if key not in seen:
                        seen.add(key)
                        unique_history.append(msg)

                # Sort by timestamp (recent first, then reverse for chronological)
                try:
                    unique_history.sort(
                        key=lambda x: x["timestamp"], reverse=True)
                    # Keep only last 30 messages
                    unique_history = unique_history[:30]
                    unique_history.reverse()  # Put back in chronological order
                except Exception as e:
                    logger.warning(
                        f"Error sorting conversation history for {ig_username}: {e}")

                # Clean up the final history (remove source field for compatibility)
                history = [{k: v for k, v in msg.items() if k != "source"}
                           for msg in unique_history]

                # Parse JSON fields safely using correct column indices
                # Parse each JSON field safely
                def safe_json_parse(json_str, default=None):
                    if default is None:
                        default = {}
                    if isinstance(json_str, str) and json_str.strip():
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse JSON for {ig_username}: {json_str[:100]}...")
                            return default
                    return default

                metrics = safe_json_parse(user_row[2])  # metrics_json
                calorie_tracking = safe_json_parse(
                    user_row[3])  # calorie_tracking_json
                workout_program = safe_json_parse(
                    user_row[4])  # workout_program_json
                meal_plan = safe_json_parse(user_row[5])  # meal_plan_json
                client_analysis = safe_json_parse(
                    user_row[6])  # client_analysis_json
                journey_stage = safe_json_parse(
                    user_row[38])  # journey_stage (index 38)

                all_conversations[ig_username] = {
                    "metrics": {
                        "ig_username": ig_username,                            # 0
                        # 1
                        "subscriber_id": user_row[1],
                        # 2 (parsed)
                        "metrics_json": metrics,
                        # 3 (parsed)
                        "calorie_tracking": calorie_tracking,
                        # 4 (parsed)
                        "workout_program": workout_program,
                        # 5 (parsed)
                        "meal_plan": meal_plan,
                        # 6 (raw)
                        "client_analysis_json": user_row[6],
                        # 6 (parsed)
                        "client_analysis": client_analysis,
                        # 7
                        "is_onboarding": bool(user_row[7]) if user_row[7] is not None else False,
                        # 8
                        "is_in_checkin_flow_mon": bool(user_row[8]) if user_row[8] is not None else False,
                        # 9
                        "is_in_checkin_flow_wed": bool(user_row[9]) if user_row[9] is not None else False,
                        # 10
                        "client_status": user_row[10],
                        # 11
                        "bio": user_row[11],
                        # 12
                        "first_name": user_row[12],
                        # 13
                        "last_name": user_row[13],
                        # 14
                        "bio_analysis_status": user_row[14],
                        # 15
                        "last_updated": user_row[15],
                        # 16
                        "is_in_ad_flow": bool(user_row[16]) if user_row[16] is not None else False,
                        # 17
                        "ad_script_state": user_row[17],
                        # 18
                        "ad_scenario": user_row[18],
                        # 19
                        "lead_source": user_row[19],
                        # 20
                        "offer_made": bool(user_row[20]) if user_row[20] is not None else False,
                        # 21
                        "challenge_email": user_row[21],
                        # 22
                        "challenge_type": user_row[22],
                        # 23
                        "challenge_signup_date": user_row[23],
                        # 24
                        "paid_challenge_booking_status": user_row[24],
                        # 25
                        "paid_challenge_booking_date": user_row[25],
                        # 26
                        "last_interaction_timestamp": user_row[26],
                        # 27
                        "bio_context": user_row[27],
                        # 28
                        "client_stage": user_row[28],
                        # 29
                        "client_next_step": user_row[29],
                        # 30
                        "client_style": user_row[30],
                        # 31
                        "client_goals": user_row[31],
                        # 32
                        "client_barriers": user_row[32],
                        # 33
                        "client_interests": user_row[33],
                        # 34
                        "client_motivation": user_row[34],
                        # 35
                        "client_personality": user_row[35],
                        # 36
                        "email": user_row[36],
                        # 37
                        "phone_number": user_row[37],
                        # 38 (parsed)
                        "journey_stage": journey_stage,
                        # 39
                        "last_follow_up_timestamp": user_row[39],
                        # 40
                        "follow_up_count": user_row[40] if user_row[40] is not None else 0,
                        # 41
                        "tags": user_row[41],
                        "total_messages": len(history),
                        "conversation_history": history
                    },
                    "history": history
                }

        logger.info(
            f"Successfully loaded {len(all_conversations)} users from SQLite (optimized)")
        return all_conversations

    except Exception as e:
        logger.error(
            f"Error loading conversations from SQLite: {e}", exc_info=True)
        return {}
    finally:
        if conn:
            conn.close()


def ensure_table_exists(conn: sqlite3.Connection, table_name: str, columns: Dict[str, str]):
    """Ensure a specific table exists with its primary key."""
    try:
        cursor = conn.cursor()
        cols_with_types = ", ".join(
            [f'"{k}" {v}' for k, v in columns.items() if v and 'PRIMARY KEY' not in v.upper()])
        pk_col = [k for k, v in columns.items(
        ) if v and 'PRIMARY KEY' in v.upper()]
        pk_statement = f", PRIMARY KEY (\"{pk_col[0]}\")" if pk_col else ""
        create_statement = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" ({cols_with_types}{pk_statement})"
        cursor.execute(create_statement)
        conn.commit()
        logger.info(f"Ensured '{table_name}' table exists.")
    except sqlite3.Error as e:
        logger.error(
            f"Error ensuring table '{table_name}': {e}", exc_info=True)
        raise


def ensure_all_columns_exist(conn: sqlite3.Connection, table_name: str, columns: Dict[str, str]):
    """Ensure all columns for a specific table exist."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info(\"{table_name}\")")
        existing_columns = {row[1] for row in cursor.fetchall()}

        for col, col_type in columns.items():
            if col not in existing_columns:
                try:
                    # Remove NOT NULL for initial creation to avoid default value issues
                    col_type_safe = col_type.upper().replace(' NOT NULL', '')
                    # Remove default constraints that are not constant
                    col_type_safe = re.sub(
                        r'DEFAULT\s+CURRENT_TIMESTAMP', '', col_type_safe)

                    logger.info(
                        f"Adding missing column '{col}' to '{table_name}' with type {col_type_safe}.")
                    cursor.execute(
                        f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" {col_type_safe}')

                    # If the original type had 'DEFAULT CURRENT_TIMESTAMP', update existing rows
                    if 'DEFAULT CURRENT_TIMESTAMP' in col_type.upper():
                        cursor.execute(
                            f'UPDATE "{table_name}" SET "{col}" = CURRENT_TIMESTAMP WHERE "{col}" IS NULL')

                    # If the original type was NOT NULL, populate with a default and warn
                    if 'NOT NULL' in col_type.upper():
                        default_value = "''" if 'TEXT' in col_type.upper() else 0
                        logger.info(
                            f"Populating new column '{col}' with default value: {default_value}")
                        cursor.execute(
                            f'UPDATE "{table_name}" SET "{col}" = ? WHERE "{col}" IS NULL', (default_value,))
                        logger.warning(
                            f"Added column '{col}' as nullable; application logic must handle NOT NULL enforcement.")

                except sqlite3.OperationalError as e:
                    logger.error(
                        f"Failed to add column '{col}' to '{table_name}': {e}", exc_info=True)
        conn.commit()
    except sqlite3.Error as e:
        logger.error(
            f"Error ensuring columns for table '{table_name}': {e}", exc_info=True)
        raise


def add_response_to_review_queue(*args, **kwargs):
    """Adds a generated response to the review queue. Accepts both legacy positional args and newer keyword args."""
    # Support legacy positional arg order
    if args and len(args) >= 6:
        ig_username, subscriber_id, user_message, timestamp, prompt_text, response_text = args[
            :6]
        prompt_type = args[6] if len(args) > 6 else 'general_chat'
        status = args[7] if len(args) > 7 else 'pending_review'
    else:
        # Support newer keyword style
        ig_username = kwargs.get(
            'ig_username') or kwargs.get('user_ig_username')
        subscriber_id = kwargs.get(
            'subscriber_id') or kwargs.get('user_subscriber_id')
        user_message = kwargs.get('user_message') or kwargs.get(
            'incoming_message_text')
        timestamp = kwargs.get('timestamp') or kwargs.get(
            'incoming_message_timestamp') or kwargs.get('incoming_message_timestamp_iso')
        prompt_text = kwargs.get('prompt_text') or kwargs.get(
            'generated_prompt_text')
        response_text = kwargs.get('response_text') or kwargs.get(
            'proposed_response_text')
        prompt_type = kwargs.get('prompt_type', 'general_chat')
        status = kwargs.get('status', 'pending_review')

    from datetime import datetime
    if not timestamp:
        timestamp = datetime.now().isoformat()
    if not prompt_text:
        prompt_text = ""

    # Debug logging to see what parameters we actually received
    logger.info(
        f"add_response_to_review_queue called with ig_username='{ig_username}', subscriber_id='{subscriber_id}', user_message='{user_message}', response_text='{response_text}', prompt_type='{prompt_type}', status='{status}'")

    if not all([ig_username, subscriber_id, user_message, response_text]):
        logger.error(
            f"add_response_to_review_queue missing critical parameters - ig_username: {'✓' if ig_username else '✗'}, subscriber_id: {'✓' if subscriber_id else '✗'}, user_message: {'✓' if user_message else '✗'}, response_text: {'✓' if response_text else '✗'}")
        return None

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check for existing reviews for the same user and message within the last 5 minutes
        from datetime import datetime, timedelta
        five_minutes_ago = (datetime.now() - timedelta(minutes=5)).isoformat()

        cursor.execute("""
            SELECT review_id, status, created_timestamp 
            FROM pending_reviews 
            WHERE user_ig_username = ? 
            AND incoming_message_text = ? 
            AND created_timestamp > ?
            ORDER BY created_timestamp DESC
            LIMIT 1
        """, (ig_username, user_message, five_minutes_ago))

        existing_review = cursor.fetchone()

        if existing_review:
            existing_review_id, existing_status, existing_timestamp = existing_review
            logger.info(
                f"Found existing review (ID: {existing_review_id}, status: {existing_status}) for {ig_username} with same message. Skipping duplicate.")
            return existing_review_id

        # Check for similar messages (fuzzy match) within last 2 minutes
        two_minutes_ago = (datetime.now() - timedelta(minutes=2)).isoformat()
        cursor.execute("""
            SELECT review_id, incoming_message_text, created_timestamp 
            FROM pending_reviews 
            WHERE user_ig_username = ? 
            AND created_timestamp > ?
            ORDER BY created_timestamp DESC
            LIMIT 5
        """, (ig_username, two_minutes_ago))

        recent_reviews = cursor.fetchall()
        for recent_review in recent_reviews:
            recent_id, recent_message, recent_timestamp = recent_review
            # Simple similarity check - if messages are very similar, skip
            if recent_message and user_message:
                similarity = _calculate_message_similarity(
                    user_message, recent_message)
                if similarity > 0.8:  # 80% similarity threshold
                    logger.info(
                        f"Found similar recent message (ID: {recent_id}, similarity: {similarity:.2f}) for {ig_username}. Skipping duplicate.")
                    return recent_id

        # No duplicates found, proceed with creating new review
        cursor.execute("""
            INSERT INTO pending_reviews (user_ig_username, user_subscriber_id, incoming_message_text, incoming_message_timestamp, generated_prompt_text, proposed_response_text, prompt_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ig_username, subscriber_id, user_message, timestamp, prompt_text, response_text, prompt_type, status))
        conn.commit()
        logger.info(
            f"✅ Added review to queue with prompt_type='{prompt_type}' and status='{status}'")
        return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Error adding response to review queue: {e}")
        return None
    finally:
        if conn:
            conn.close()


def _calculate_message_similarity(msg1: str, msg2: str) -> float:
    """Calculate similarity between two messages using simple character-based comparison."""
    if not msg1 or not msg2:
        return 0.0

    # Normalize messages
    msg1_clean = msg1.strip().lower()
    msg2_clean = msg2.strip().lower()

    if msg1_clean == msg2_clean:
        return 1.0

    # Simple character-based similarity
    shorter = msg1_clean if len(msg1_clean) < len(msg2_clean) else msg2_clean
    longer = msg2_clean if len(msg1_clean) < len(msg2_clean) else msg1_clean

    if len(shorter) == 0:
        return 0.0

    # Count matching characters
    matches = sum(1 for c1, c2 in zip(shorter, longer) if c1 == c2)
    similarity = matches / len(longer)

    return similarity


def get_live_auto_mode_stats():
    """Get live auto mode statistics - stub function to prevent errors."""
    return {
        'scheduled': 0,
        'recent_activity': 0,
        'sent_today': 0,
        'avg_processing_time_ms': 0
    }


def get_recent_auto_activities(limit=50):
    """Get recent auto activities - stub function to prevent errors."""
    return []


def get_auto_mode_heartbeat():
    """Get auto mode heartbeat - stub function to prevent errors."""
    return {'last_heartbeat': None}


def get_current_processing():
    """Get current processing status - stub function to prevent errors."""
    return None


def create_auto_mode_tracking_tables_if_not_exists(conn):
    """Create auto mode tracking tables if they don't exist - stub function."""
    pass


def get_pending_reviews():
    """Fetches all responses from the queue that are pending review."""
    conn = get_db_connection()
    try:
        # Enable row factory to get dictionaries instead of tuples
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM pending_reviews WHERE status = 'pending_review' ORDER BY created_timestamp DESC")
        rows = cursor.fetchall()
        # Convert Row objects to dictionaries for easier access
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error getting pending reviews: {e}")
        return []
    finally:
        if conn:
            conn.close()


def update_review_status(review_id, new_status, final_response_text=None):
    """Updates the status of a review item and logs the final approved/sent text."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pending_reviews 
            SET status = ?, final_response_text = ?, reviewed_timestamp = ?
            WHERE review_id = ?
        """, (new_status, final_response_text, datetime.now().isoformat(), review_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating review status for ID {review_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_review_proposed_response(review_id, new_proposed_response):
    """Updates the proposed response text for a review item."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pending_reviews 
            SET proposed_response_text = ?, regeneration_count = COALESCE(regeneration_count, 0) + 1
            WHERE review_id = ?
        """, (new_proposed_response, review_id))
        conn.commit()
        rows_affected = cursor.rowcount
        logger.info(
            f"Updated proposed response for review ID {review_id}, rows affected: {rows_affected}")
        return rows_affected > 0
    except sqlite3.Error as e:
        logger.error(
            f"Error updating proposed response for ID {review_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_good_few_shot_examples(limit: int = 50) -> List[Dict[str, str]]:
    """
    Fetches approved and marked examples from the learning_feedback_log
    to be used as few-shot examples in prompts.
    """
    examples = []
    conn = get_db_connection()
    if not conn:
        return examples
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT original_prompt_text, edited_response_text
            FROM learning_feedback_log
            WHERE is_good_example_for_few_shot = 1
            AND (conversation_type IS NULL OR conversation_type = 'general')
            ORDER BY RANDOM()
            LIMIT ?
        """, (limit,))

        for row in cursor.fetchall():
            # Ensure the structure matches what the prompt expects
            # Example: {"input": "User's message/prompt", "output": "Ideal AI response"}
            # Adjust the keys if your prompt template uses different ones.
            examples.append(
                {"input": row['original_prompt_text'], "output": row['edited_response_text']})

    except sqlite3.Error as e:
        logger.error(
            f"Failed to fetch few-shot examples from the database: {e}")
    finally:
        if conn:
            conn.close()

    return examples


def get_vegan_few_shot_examples(limit: int = 50) -> List[Dict[str, str]]:
    """
    Fetches vegan-specific examples from the learning_feedback_log
    to be used as few-shot examples for vegan ad conversations.
    """
    examples = []
    conn = get_db_connection()
    if not conn:
        return examples
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT original_prompt_text, edited_response_text
            FROM learning_feedback_log
            WHERE is_good_example_for_few_shot = 1
            AND conversation_type = 'vegan'
            ORDER BY RANDOM()
            LIMIT ?
        """, (limit,))

        for row in cursor.fetchall():
            examples.append(
                {"input": row['original_prompt_text'], "output": row['edited_response_text']})

    except sqlite3.Error as e:
        logger.error(
            f"Failed to fetch vegan few-shot examples from the database: {e}")
    finally:
        if conn:
            conn.close()

    return examples


# ---------------- Nutrition/Calorie Tracking Helpers (SQLite) ---------------- #

def _safe_parse_json(text: Optional[str]) -> dict:
    try:
        if isinstance(text, str) and text.strip():
            return json.loads(text)
    except Exception:
        pass
    return {}


def get_user_metrics_json(ig_username: str) -> dict:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
        row = cur.fetchone()
        return _safe_parse_json(row[0]) if row else {}
    except sqlite3.Error:
        return {}
    finally:
        if conn:
            conn.close()


def set_user_metrics_json_field(ig_username: str, key: str, value: Any) -> bool:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
        row = cur.fetchone()
        metrics = _safe_parse_json(row[0]) if row else {}
        metrics[key] = value
        cur.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?',
                    (json.dumps(metrics), ig_username))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(
            f"Failed to set metrics_json field for {ig_username}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_nutrition_targets(ig_username: str) -> Optional[dict]:
    """Return stored per-user targets from users.calorie_tracking_json if present."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT calorie_tracking_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
        row = cur.fetchone()
        data = _safe_parse_json(row[0]) if row else {}
        # Require a complete target set; otherwise treat as missing
        if not isinstance(data, dict) or not data:
            return None
        daily_target = int(data.get('daily_target', 0) or 0)
        macros = data.get('macros') or {}
        try:
            p_tgt = int(
                ((macros.get('protein') or {}).get('daily_target', 0)) or 0)
            c_tgt = int(
                ((macros.get('carbs') or {}).get('daily_target', 0)) or 0)
            f_tgt = int(
                ((macros.get('fats') or {}).get('daily_target', 0)) or 0)
        except Exception:
            p_tgt = c_tgt = f_tgt = 0
        if daily_target <= 0 or p_tgt <= 0 or c_tgt <= 0 or f_tgt <= 0:
            return None
        return data
    except sqlite3.Error as e:
        logger.error(f"get_nutrition_targets error for {ig_username}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def upsert_nutrition_targets(ig_username: str, targets: dict) -> bool:
    """Create/update users.calorie_tracking_json with targets and reset daily counters."""
    try:
        daily_target = int(targets.get('target_calories'))
        protein_target = int(targets.get('target_protein'))
        carbs_target = int(targets.get('target_carbs'))
        fats_target = int(targets.get('target_fats'))
    except Exception:
        return False

    tracking = {
        'daily_target': daily_target,
        'current_date': datetime.now().date().isoformat(),
        'calories_consumed': 0,
        'remaining_calories': daily_target,
        'macros': {
            'protein': {'daily_target': protein_target, 'consumed': 0, 'remaining': protein_target},
            'carbs': {'daily_target': carbs_target, 'consumed': 0, 'remaining': carbs_target},
            'fats': {'daily_target': fats_target, 'consumed': 0, 'remaining': fats_target},
        },
        'meals_today': []
    }

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Keep/merge existing user row fields if present
        cur.execute(
            'SELECT calorie_tracking_json, first_name, last_name, client_status FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
        existing = cur.fetchone()
        if existing:
            cur.execute('UPDATE users SET calorie_tracking_json = ? WHERE ig_username = ?',
                        (json.dumps(tracking), ig_username))
        else:
            cur.execute('INSERT INTO users (ig_username, calorie_tracking_json) VALUES (?, ?)',
                        (ig_username, json.dumps(tracking)))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"upsert_nutrition_targets error for {ig_username}: {e}")
        # Attempt to add missing columns and retry once
        try:
            ensure_all_columns_exist(
                conn, 'users', {'calorie_tracking_json': 'TEXT'})
            cur = conn.cursor()
            cur.execute('UPDATE users SET calorie_tracking_json = ? WHERE ig_username = ?',
                        (json.dumps(tracking), ig_username))
            if cur.rowcount == 0:
                cur.execute('INSERT INTO users (ig_username, calorie_tracking_json) VALUES (?, ?)',
                            (ig_username, json.dumps(tracking)))
            conn.commit()
            return True
        except Exception as e2:
            logger.error(
                f"Retry failed for upsert_nutrition_targets {ig_username}: {e2}")
            return False
    finally:
        if conn:
            conn.close()


def _load_tracking(conn: sqlite3.Connection, ig_username: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        'SELECT calorie_tracking_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
    row = cur.fetchone()
    return _safe_parse_json(row[0]) if row else None


def _save_tracking(conn: sqlite3.Connection, ig_username: str, tracking: dict) -> None:
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET calorie_tracking_json = ? WHERE ig_username = ?',
                    (json.dumps(tracking), ig_username))
    except sqlite3.Error:
        ensure_all_columns_exist(
            conn, 'users', {'calorie_tracking_json': 'TEXT'})
        cur.execute('UPDATE users SET calorie_tracking_json = ? WHERE ig_username = ?',
                    (json.dumps(tracking), ig_username))


def reset_daily_calorie_tracking_if_new_day(ig_username: str) -> bool:
    """Reset the user's daily calorie/macros if the stored date is not today.

    Returns True if a reset occurred, False otherwise.
    """
    conn = get_db_connection()
    try:
        tracking = _load_tracking(conn, ig_username)
        if not tracking:
            return False
        today = datetime.now().date().isoformat()
        if tracking.get('current_date') == today:
            return False

        # Perform reset using existing targets
        daily_target = int(tracking.get('daily_target', 2000))
        for macro in ('protein', 'carbs', 'fats'):
            tgt = int(tracking['macros'][macro]['daily_target'])
            tracking['macros'][macro] = {
                'daily_target': tgt,
                'consumed': 0,
                'remaining': tgt,
            }
        tracking.update({
            'current_date': today,
            'calories_consumed': 0,
            'remaining_calories': daily_target,
            'meals_today': []
        })

        # Persist tracking
        _save_tracking(conn, ig_username, tracking)

        # Mirror into metrics_json for quick dashboard reads
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
            row = cur.fetchone()
            metrics = _safe_parse_json(row[0]) if row else {}
            metrics.setdefault('nutrition', {})
            metrics['nutrition'].update({
                'calories_consumed_today': 0,
                'remaining_calories_today': daily_target,
                'protein_remaining': tracking['macros']['protein']['remaining'],
                'carbs_remaining': tracking['macros']['carbs']['remaining'],
                'fats_remaining': tracking['macros']['fats']['remaining'],
                'last_meal': None,
            })
            cur.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?',
                        (json.dumps(metrics), ig_username))
            conn.commit()
        except Exception:
            pass

        return True
    except Exception:
        return False
    finally:
        if conn:
            conn.close()


def log_meal_and_update_calorie_tracking(ig_username: str, meal_description: str, calories: int, protein: int, carbs: int, fats: int) -> bool:
    conn = get_db_connection()
    try:
        tracking = _load_tracking(conn, ig_username)
        if not tracking:
            return False
        # Reset if new day
        today = datetime.now().date().isoformat()
        if tracking.get('current_date') != today:
            daily_target = tracking.get('daily_target', 2000)
            for macro in ('protein', 'carbs', 'fats'):
                tgt = tracking['macros'][macro]['daily_target']
                tracking['macros'][macro] = {
                    'daily_target': tgt, 'consumed': 0, 'remaining': tgt}
            tracking.update({'current_date': today, 'calories_consumed': 0,
                            'remaining_calories': daily_target, 'meals_today': []})

        # Update totals
        tracking['calories_consumed'] = int(
            tracking.get('calories_consumed', 0)) + int(calories)
        tracking['remaining_calories'] = int(tracking.get(
            'daily_target', 0)) - int(tracking['calories_consumed'])
        for macro, amt in (('protein', protein), ('carbs', carbs), ('fats', fats)):
            tracking['macros'][macro]['consumed'] = int(
                tracking['macros'][macro].get('consumed', 0)) + int(amt)
            tracking['macros'][macro]['remaining'] = int(
                tracking['macros'][macro]['daily_target']) - int(tracking['macros'][macro]['consumed'])

        # Append meal
        tracking['meals_today'].append({
            'time': datetime.now().isoformat(),
            'description': meal_description,
            'calories': int(calories),
            'protein': int(protein),
            'carbs': int(carbs),
            'fats': int(fats),
        })

        # Persist tracking and separate meal log
        _save_tracking(conn, ig_username, tracking)
        cur = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO meal_logs (ig_username, timestamp, meal_name, calories, protein, carbs, fats) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (ig_username, datetime.now().isoformat(), meal_description,
                 int(calories), int(protein), int(carbs), int(fats))
            )
        except sqlite3.Error:
            # Try to create table and retry once
            try:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS meal_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ig_username TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        meal_name TEXT,
                        calories INTEGER,
                        protein INTEGER,
                        carbs INTEGER,
                        fats INTEGER
                    )
                ''')
                cur.execute(
                    'CREATE INDEX IF NOT EXISTS idx_meals_user_time ON meal_logs(ig_username, timestamp)')
                cur.execute(
                    'INSERT INTO meal_logs (ig_username, timestamp, meal_name, calories, protein, carbs, fats) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (ig_username, datetime.now().isoformat(), meal_description,
                     int(calories), int(protein), int(carbs), int(fats))
                )
            except Exception:
                pass
        conn.commit()

        # Also mirror key daily metrics into users.metrics_json for dashboard quick reads
        try:
            cur.execute(
                'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
            row = cur.fetchone()
            metrics = _safe_parse_json(row[0]) if row else {}
            metrics.setdefault('nutrition', {})
            metrics['nutrition'].update({
                'calories_consumed_today': tracking.get('calories_consumed', 0),
                'remaining_calories_today': tracking.get('remaining_calories', 0),
                'protein_remaining': tracking['macros']['protein']['remaining'],
                'carbs_remaining': tracking['macros']['carbs']['remaining'],
                'fats_remaining': tracking['macros']['fats']['remaining'],
                'last_meal': meal_description,
            })
            cur.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?',
                        (json.dumps(metrics), ig_username))
            conn.commit()
        except Exception:
            pass
        return True
    except sqlite3.Error as e:
        logger.error(
            f"log_meal_and_update_calorie_tracking error for {ig_username}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_calorie_summary_text(ig_username: str) -> Optional[str]:
    conn = get_db_connection()
    try:
        tracking = _load_tracking(conn, ig_username)
        if not tracking:
            return None
        remaining_calories = int(tracking.get('remaining_calories', 0) or 0)
        protein_rem = int(tracking['macros']
                          ['protein'].get('remaining', 0) or 0)
        carbs_rem = int(tracking['macros']['carbs'].get('remaining', 0) or 0)
        fats_rem = int(tracking['macros']['fats'].get('remaining', 0) or 0)
        return (
            f"Remaining today:\n"
            f"Calories: {remaining_calories}\n"
            f"Protein: {protein_rem}g\n"
            f"Carbs: {carbs_rem}g\n"
            f"Fats: {fats_rem}g"
        )
    except Exception:
        return None
    finally:
        if conn:
            conn.close()


def user_has_nutrition_profile(ig_username: str) -> bool:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT 1 FROM user_nutrition_profiles WHERE ig_username = ? LIMIT 1', (ig_username,))
        return cur.fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        if conn:
            conn.close()


def upsert_user_nutrition_profile(
    ig_username: str,
    sex: Optional[str],
    dob: Optional[str],
    age: Optional[int],
    height_cm: Optional[int],
    weight_kg: Optional[float],
    activity_level: Optional[str],
    main_goal: Optional[str]
) -> bool:
    now = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT ig_username FROM user_nutrition_profiles WHERE ig_username = ? LIMIT 1', (ig_username,))
        if cur.fetchone():
            cur.execute(
                '''UPDATE user_nutrition_profiles
                   SET sex=?, dob=?, age=?, height_cm=?, weight_kg=?, activity_level=?, main_goal=?, updated_at=?
                   WHERE ig_username=?''',
                (sex, dob, age, height_cm, weight_kg,
                 activity_level, main_goal, now, ig_username)
            )
        else:
            cur.execute(
                '''INSERT INTO user_nutrition_profiles
                   (ig_username, sex, dob, age, height_cm, weight_kg, activity_level, main_goal, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (ig_username, sex, dob, age, height_cm,
                 weight_kg, activity_level, main_goal, now, now)
            )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(
            f"upsert_user_nutrition_profile error for {ig_username}: {e}")
        # Self-heal if table is missing, then retry once
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS user_nutrition_profiles (
                    ig_username TEXT PRIMARY KEY,
                    sex TEXT,
                    dob TEXT,
                    age INTEGER,
                    height_cm INTEGER,
                    weight_kg REAL,
                    activity_level TEXT,
                    main_goal TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            conn.commit()
            # Retry upsert
            cur.execute(
                'SELECT ig_username FROM user_nutrition_profiles WHERE ig_username = ? LIMIT 1', (ig_username,))
            if cur.fetchone():
                cur.execute(
                    '''UPDATE user_nutrition_profiles
                       SET sex=?, dob=?, age=?, height_cm=?, weight_kg=?, activity_level=?, main_goal=?, updated_at=?
                       WHERE ig_username=?''',
                    (sex, dob, age, height_cm, weight_kg,
                     activity_level, main_goal, now, ig_username)
                )
            else:
                cur.execute(
                    '''INSERT INTO user_nutrition_profiles
                       (ig_username, sex, dob, age, height_cm, weight_kg, activity_level, main_goal, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (ig_username, sex, dob, age, height_cm,
                     weight_kg, activity_level, main_goal, now, now)
                )
            conn.commit()
            return True
        except Exception as e2:
            logger.error(
                f"Failed to self-heal and upsert user_nutrition_profiles for {ig_username}: {e2}")
            return False
    finally:
        if conn:
            conn.close()


def rename_last_meal(ig_username: str, new_meal_name: str) -> bool:
    """Rename the most recent meal for a user in both tracking JSON and meal_logs."""
    conn = get_db_connection()
    try:
        tracking = _load_tracking(conn, ig_username)
        if not tracking:
            return False
        # Update tracking JSON last meal name
        if isinstance(tracking.get('meals_today'), list) and tracking['meals_today']:
            tracking['meals_today'][-1]['description'] = new_meal_name
            _save_tracking(conn, ig_username, tracking)

        # Update last row in meal_logs
        cur = conn.cursor()
        cur.execute(
            'SELECT id FROM meal_logs WHERE ig_username = ? ORDER BY timestamp DESC LIMIT 1',
            (ig_username,),
        )
        row = cur.fetchone()
        if row:
            last_id = row[0]
            cur.execute(
                'UPDATE meal_logs SET meal_name = ? WHERE id = ?', (new_meal_name, last_id))
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"rename_last_meal error for {ig_username}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_member_few_shot_examples(limit: int = 50) -> List[Dict[str, str]]:
    """
    Fetches member-specific examples from the learning_feedback_log
    to be used as few-shot examples for member chat conversations.
    """
    examples = []
    conn = get_db_connection()
    if not conn:
        return examples
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT original_prompt_text, edited_response_text
            FROM learning_feedback_log
            WHERE is_good_example_for_few_shot = 1
            AND conversation_type = 'member'
            ORDER BY RANDOM()
            LIMIT ?
        """, (limit,))

        for row in cursor.fetchall():
            examples.append(
                {"input": row['original_prompt_text'], "output": row['edited_response_text']})

    except sqlite3.Error as e:
        logger.error(
            f"Failed to fetch member few-shot examples from the database: {e}")
    finally:
        if conn:
            conn.close()

    return examples


def is_user_in_vegan_flow(ig_username: str) -> bool:
    """
    Determine if a user is in a vegan ad flow based on their lead source and data.

    Returns:
        bool: True if user is in vegan flow, False otherwise
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Check user's lead source and ad flow status
        cursor.execute("""
            SELECT lead_source, is_in_ad_flow, ad_scenario
            FROM users
            WHERE ig_username = ?
        """, (ig_username,))

        result = cursor.fetchone()
        if not result:
            return False

        lead_source, is_in_ad_flow, ad_scenario = result

        # User is in vegan flow if:
        # 1. Lead source contains 'vegan' or 'plant'
        # 2. They're in an ad flow scenario
        # 3. Or they have vegan-related bio keywords

        if lead_source and ('vegan' in lead_source.lower() or 'plant' in lead_source.lower()):
            return True

        if is_in_ad_flow and ad_scenario:
            return True

        # Check bio for vegan indicators
        cursor.execute("""
            SELECT bio, bio_context, client_interests
            FROM users
            WHERE ig_username = ?
        """, (ig_username,))

        bio_result = cursor.fetchone()
        if bio_result:
            bio, bio_context, client_interests = bio_result
            bio_text = f"{bio or ''} {bio_context or ''} {client_interests or ''}".lower(
            )

            vegan_keywords = ['vegan', 'plant-based',
                              'plantbased', 'plant based', 'cruelty free']
            if any(keyword in bio_text for keyword in vegan_keywords):
                return True

        return False

    except sqlite3.Error as e:
        logger.error(f"Error checking vegan flow for {ig_username}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def add_to_learning_log(review_id: int, user_ig_username: str, user_subscriber_id: str, original_prompt_text: str, original_gemini_response: str, edited_response_text: str, user_notes: str, is_good_example_for_few_shot: Optional[bool] = None, conversation_type: str = 'general'):
    """
    Logs feedback to the learning_feedback_log table for later analysis and fine-tuning.
    Determines if an example is good for few-shot learning based on user actions.

    Args:
        conversation_type: 'general', 'vegan', or other type for specialized few-shot learning
    """
    if is_good_example_for_few_shot is None:
        # Auto-determine if it's a good example
        # It's a good example if the user edited the response or accepted a regenerated response
        was_edited = edited_response_text.strip() != original_gemini_response.strip()
        was_regenerated_and_kept = "regenerated" in user_notes.lower(
        ) and not was_edited

        is_good_example_for_few_shot = 1 if was_edited or was_regenerated_and_kept else 0

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # First ensure the conversation_type column exists
        try:
            cursor.execute(
                "ALTER TABLE learning_feedback_log ADD COLUMN conversation_type TEXT DEFAULT 'general'")
            conn.commit()
            logger.info(
                "Added conversation_type column to learning_feedback_log")
        except sqlite3.OperationalError:
            # Column already exists, that's fine
            pass

        cursor.execute("""
            INSERT INTO learning_feedback_log (
                review_id, user_ig_username, user_subscriber_id,
                original_prompt_text, original_gemini_response,
                edited_response_text, user_notes, is_good_example_for_few_shot,
                conversation_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id, user_ig_username, user_subscriber_id,
            original_prompt_text, original_gemini_response,
            edited_response_text, user_notes,
            is_good_example_for_few_shot, conversation_type
        ))
        conn.commit()
        logger.info(
            f"Successfully logged learning feedback for review ID {review_id} (type: {conversation_type})")
        return True
    except sqlite3.Error as e:
        logger.error(
            f"Error adding to learning_feedback_log for review ID {review_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_review_accuracy_stats():
    """Calculates review accuracy stats from the learning feedback log."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check if table exists and get column info
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learning_feedback_log'")
        if not cursor.fetchone():
            # Table doesn't exist, return empty stats
            return {
                "total_processed": 0, "sent_as_is": 0, "edited_by_user": 0, "regenerated_count": 0,
                "accuracy_percentage": 0.0, "edited_percentage": 0.0, "regenerated_percentage": 0.0,
                "total_processed_including_discarded": 0
            }

        # Get total entries from learning_feedback_log
        cursor.execute("SELECT COUNT(*) FROM learning_feedback_log")
        total_including_discarded = cursor.fetchone()[0]

        if total_including_discarded == 0:
            return {
                "total_processed": 0, "sent_as_is": 0, "edited_by_user": 0, "regenerated_count": 0,
                "accuracy_percentage": 0.0, "edited_percentage": 0.0, "regenerated_percentage": 0.0,
                "total_processed_including_discarded": 0
            }

        # Use simpler logic based on available columns
        # Count entries where response was edited vs sent as-is
        cursor.execute("""
            SELECT COUNT(*) FROM learning_feedback_log 
            WHERE original_gemini_response != edited_response_text AND edited_response_text != ''
        """)
        edited = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM learning_feedback_log 
            WHERE original_gemini_response = edited_response_text OR edited_response_text = ''
        """)
        sent_as_is = cursor.fetchone()[0]

        total_processed = total_including_discarded
        regenerated = 0  # Can't determine this from current schema

        return {
            "total_processed": total_processed,
            "total_processed_including_discarded": total_including_discarded,
            "sent_as_is": sent_as_is,
            "edited_by_user": edited,
            "regenerated_count": regenerated,
            "accuracy_percentage": round((sent_as_is / total_processed) * 100, 1) if total_processed > 0 else 0.0,
            "edited_percentage": round((edited / total_processed) * 100, 1) if total_processed > 0 else 0.0,
            "regenerated_percentage": round((regenerated / total_processed) * 100, 1) if total_processed > 0 else 0.0,
        }
    except sqlite3.Error as e:
        logger.error(f"Error getting review accuracy stats: {e}")
        return {
            "total_processed": 0, "sent_as_is": 0, "edited_by_user": 0, "regenerated_count": 0,
            "accuracy_percentage": 0.0, "edited_percentage": 0.0, "regenerated_percentage": 0.0,
            "total_processed_including_discarded": 0
        }
    finally:
        if conn:
            conn.close()


def reset_learning_stats():
    """Deletes all records from the learning_feedback_log table."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM learning_feedback_log")
        conn.commit()
        logger.info("Successfully reset all learning feedback statistics.")
        return True, "✅ Learning stats reset successfully!"
    except sqlite3.Error as e:
        logger.error(f"Error resetting learning stats: {e}")
        return False, f"❌ Database error: {e}"
    finally:
        if conn:
            conn.close()


def insert_manual_context_message(user_ig_username: str, subscriber_id: str, manual_message_text: str, user_message_timestamp_str: str) -> bool:
    """
    Inserts a manual context message from Shannon into the conversation history using unified messages table,
    positioning it just before the user's reply.
    """
    try:
        user_msg_timestamp = datetime.fromisoformat(
            user_message_timestamp_str.split('+')[0])
        manual_msg_timestamp = (
            user_msg_timestamp - timedelta(seconds=1)).isoformat()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (ig_username, subscriber_id, timestamp, message_type, message_text)
            VALUES (?, ?, ?, ?, ?)
        """, (user_ig_username, subscriber_id, manual_msg_timestamp, 'ai', manual_message_text))
        conn.commit()
        logger.info(
            f"Successfully inserted manual context for {user_ig_username}")
        return True
    except Exception as e:
        logger.error(
            f"Error inserting manual context for {user_ig_username}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


def get_ig_username_from_subscriber_id(subscriber_id: str) -> Optional[str]:
    """Fetches an Instagram username from the database using a subscriber ID."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ig_username FROM users WHERE subscriber_id = ?", (subscriber_id,))
        result = cursor.fetchone()
        return result['ig_username'] if result else None
    except sqlite3.Error as e:
        logger.error(
            f"Error fetching ig_username for subscriber_id {subscriber_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_all_user_photos_links() -> Dict[str, List[str]]:
    """Retrieves all user photo links from the database."""
    # This function might need to be adjusted based on where photo links are stored.
    # Assuming for now they are in a table named 'user_photos' for demonstration.
    conn = get_db_connection()
    user_photos = {}
    try:
        cursor = conn.cursor()
        # This is a hypothetical query. You'll need to adjust it to your actual schema.
        # For instance, if links are in the 'messages' table:
        cursor.execute("""
            SELECT subscriber_id, message FROM messages WHERE message LIKE '%cdn.fbsbx.com%'
        """)
        for row in cursor.fetchall():
            subscriber_id = row['subscriber_id']
            link = row['message']
            if subscriber_id not in user_photos:
                user_photos[subscriber_id] = []
            user_photos[subscriber_id].append(link)
        return user_photos
    except sqlite3.Error as e:
        logger.error(f"Error fetching user photo links: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def add_message_to_history(ig_username: str, message_type: str, message_text: str, message_timestamp: Optional[str] = None):
    """Adds a message to the unified messages table."""
    if not message_timestamp:
        message_timestamp = datetime.now().isoformat()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Get subscriber_id for this user if available
        cursor.execute(
            "SELECT subscriber_id FROM users WHERE ig_username = ?", (ig_username,))
        user_result = cursor.fetchone()
        subscriber_id = user_result[0] if user_result else None

        # Normalize message_type to 'user'/'ai'
        mt = (message_type or '').strip().lower()
        if mt in ['incoming', 'client', 'lead', 'human']:
            mt = 'user'
        elif mt in ['outgoing', 'bot', 'shanbot', 'shannon', 'assistant', 'system']:
            mt = 'ai'
        elif mt not in ['user', 'ai']:
            mt = 'unknown'

        cursor.execute("""
            INSERT INTO messages (ig_username, subscriber_id, timestamp, message_type, message_text)
            VALUES (?, ?, ?, ?, ?)
        """, (ig_username, subscriber_id, message_timestamp, mt, message_text))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(
            f"Error adding message to conversation history for {ig_username}: {e}")
    finally:
        if conn:
            conn.close()


def backfill_messages_from_pending_reviews(ig_username: str, max_rows: int = 200) -> int:
    """Backfill missing conversation rows in messages from pending_reviews for a user.
    Returns number of rows inserted.
    """
    inserted = 0
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Get subscriber_id for reuse
        cursor.execute(
            "SELECT subscriber_id FROM users WHERE ig_username = ? LIMIT 1", (ig_username,))
        user_row = cursor.fetchone()
        subscriber_id = user_row[0] if user_row else None

        # Load recent reviews
        cursor.execute(
            """
            SELECT incoming_message_text, incoming_message_timestamp, proposed_response_text, final_response_text, created_timestamp
            FROM pending_reviews
            WHERE user_ig_username = ?
            ORDER BY created_timestamp DESC
            LIMIT ?
            """,
            (ig_username, max_rows),
        )
        reviews = cursor.fetchall() or []

        for inc_text, inc_ts, proposed_ai, final_ai, created_ts in reviews:
            # Write user line
            if inc_text and str(inc_text).strip():
                try:
                    add_message_to_history(ig_username, 'user', str(
                        inc_text).strip(), (inc_ts or created_ts))
                    inserted += 1
                except Exception:
                    pass
            # Write ai line
            ai_text = (final_ai or proposed_ai)
            if ai_text and str(ai_text).strip():
                try:
                    add_message_to_history(
                        ig_username, 'ai', str(ai_text).strip(), created_ts)
                    inserted += 1
                except Exception:
                    pass

        # Optional cleanup: delete rows with no text at all
        try:
            cursor.execute(
                "DELETE FROM messages WHERE ig_username = ? AND IFNULL(message_text, '') = '' AND IFNULL(message, '') = ''",
                (ig_username,),
            )
            conn.commit()
        except Exception:
            pass

        return inserted
    except Exception as e:
        logger.error(f"Backfill failed for {ig_username}: {e}")
        return inserted
    finally:
        if conn:
            conn.close()


def delete_reviews_for_user(ig_username: str) -> tuple[bool, int]:
    """
    Deletes all pending review items for a specific user from the pending_reviews table.
    """
    conn = get_db_connection()
    deleted_count = 0
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM pending_reviews WHERE user_ig_username = ?", (ig_username,))
        deleted_count = cursor.rowcount
        conn.commit()
        logger.info(
            f"Deleted {deleted_count} review items for user {ig_username}")
        return True, deleted_count
    except sqlite3.Error as e:
        logger.error(f"Error deleting reviews for user {ig_username}: {e}")
        return False, 0
    finally:
        if conn:
            conn.close()


def update_analytics_data(
    subscriber_id: str,
    ig_username: str,
    message_text: str,
    message_direction: str,
    timestamp: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    client_status: Optional[str] = "Not a Client",
    journey_stage: Optional[str] = "Initial Inquiry",
    is_onboarding: bool = False,
    is_in_checkin_flow_mon: bool = False,
    is_in_checkin_flow_wed: bool = False,
    client_analysis_json: Optional[str] = None,
    offer_made: bool = False,
    is_in_ad_flow: bool = False,
    ad_script_state: Optional[str] = None,
    ad_scenario: Optional[int] = None,
    lead_source: Optional[str] = None,
):
    """
    Updates the analytics data in the SQLite database with the latest interaction
    and user information. Creates a new user if one doesn't exist.
    """
    logger.debug(f"Updating analytics for subscriber_id: {subscriber_id}")

    conn = None
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()

        # Check if user exists by subscriber_id first
        cursor.execute(
            "SELECT * FROM users WHERE subscriber_id = ?", (subscriber_id,))
        user_exists = cursor.fetchone()
        logger.debug(
            f"User lookup by subscriber_id '{subscriber_id}': {'Found' if user_exists else 'Not found'}")

        if not user_exists and ig_username:
            # Fallback to ig_username lookup (handles cases where subscriber_id is missing/blank)
            cursor.execute(
                "SELECT * FROM users WHERE ig_username = ?", (ig_username,))
            user_exists = cursor.fetchone()
            logger.debug(
                f"User lookup by ig_username '{ig_username}': {'Found' if user_exists else 'Not found'}")

            # If we found the user by ig_username but not by subscriber_id,
            # we need to update the subscriber_id to match
            if user_exists and subscriber_id and subscriber_id != ig_username:
                logger.debug(
                    f"Updating subscriber_id for {ig_username} from {user_exists['subscriber_id']} to {subscriber_id}")
                cursor.execute(
                    "UPDATE users SET subscriber_id = ? WHERE ig_username = ?",
                    (subscriber_id, ig_username)
                )

        if not subscriber_id:
            subscriber_id_to_use = ig_username
        else:
            subscriber_id_to_use = subscriber_id

        # If user is not in an ad flow, ensure ad-related fields are not set to avoid carrying over old state.
        ad_script_state_to_set = ad_script_state if is_in_ad_flow else None
        ad_scenario_to_set = ad_scenario if is_in_ad_flow else None

        if user_exists:
            # Update existing user
            logger.debug(f"Updating existing user: {subscriber_id}")
            cursor.execute(
                """
                UPDATE users
                SET first_name = ?, last_name = ?, client_status = ?, journey_stage = ?,
                    is_onboarding = ?, is_in_checkin_flow_mon = ?, is_in_checkin_flow_wed = ?,
                    last_interaction_timestamp = ?, client_analysis_json = ?, offer_made = ?,
                    is_in_ad_flow = ?, ad_script_state = ?, ad_scenario = ?, lead_source = ?,
                    subscriber_id = ?
                WHERE ig_username = ?
                """,
                (
                    first_name, last_name, client_status, journey_stage,
                    is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                    timestamp, client_analysis_json, offer_made,
                    is_in_ad_flow, ad_script_state_to_set, ad_scenario_to_set, lead_source,
                    subscriber_id_to_use, ig_username
                ),
            )
        else:
            # Insert new user (robust upsert by ig_username)
            logger.debug(f"Creating new user: {subscriber_id}")
            try:
                cursor.execute(
                    """
                    INSERT INTO users (
                        ig_username, subscriber_id, first_name, last_name, client_status,
                        journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                        last_interaction_timestamp, client_analysis_json, offer_made, is_in_ad_flow,
                        ad_script_state, ad_scenario, lead_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ig_username, subscriber_id_to_use, first_name, last_name, client_status,
                        journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                        timestamp, client_analysis_json, offer_made, is_in_ad_flow,
                        ad_script_state_to_set, ad_scenario_to_set, lead_source
                    ),
                )
            except sqlite3.IntegrityError as ie:
                # Row already exists for ig_username; perform UPDATE instead of failing
                logger.warning(
                    f"INSERT collided on ig_username='{ig_username}'. Falling back to UPDATE. Error: {ie}")
                cursor.execute(
                    """
                    UPDATE users
                    SET subscriber_id = ?, first_name = ?, last_name = ?, client_status = ?,
                        journey_stage = ?, is_onboarding = ?, is_in_checkin_flow_mon = ?, is_in_checkin_flow_wed = ?,
                        last_interaction_timestamp = ?, client_analysis_json = ?, offer_made = ?, is_in_ad_flow = ?,
                        ad_script_state = ?, ad_scenario = ?, lead_source = ?
                    WHERE ig_username = ?
                    """,
                    (
                        subscriber_id_to_use, first_name, last_name, client_status,
                        journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                        timestamp, client_analysis_json, offer_made, is_in_ad_flow,
                        ad_script_state_to_set, ad_scenario_to_set, lead_source,
                        ig_username,
                    ),
                )

        # Insert the new message (prefer new schema; fallback to legacy)
        logger.debug(
            f"Inserting message for {subscriber_id}: '{message_text}' as '{message_direction}' at {timestamp}")

        def _normalize_direction(direction: str) -> str:
            if not direction:
                return 'unknown'
            d = direction.strip().lower()
            if d in ['incoming', 'user', 'client', 'lead', 'human']:
                return 'user'
            if d in ['outgoing', 'ai', 'bot', 'shanbot', 'shannon', 'assistant', 'system']:
                return 'ai'
            return d

        normalized_type = _normalize_direction(message_direction)
        try:
            cursor.execute(
                """
                INSERT INTO messages (ig_username, subscriber_id, timestamp, message_type, message_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ig_username, subscriber_id_to_use,
                 timestamp, normalized_type, message_text),
            )
        except Exception:
            cursor.execute(
                """
                INSERT INTO messages (ig_username, subscriber_id, message, sender, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ig_username, subscriber_id_to_use,
                 message_text, normalized_type, timestamp),
            )

        conn.commit()
        logger.info(f"Successfully updated analytics for {subscriber_id}")
        return True

    except sqlite3.Error as e:
        logger.error(
            f"Database error in update_analytics_data for subscriber {subscriber_id}: {e}")
        return False
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in update_analytics_data for subscriber {subscriber_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def add_scheduled_response(
    review_id: int,
    user_ig_username: str,
    user_subscriber_id: str,
    response_text: str,
    incoming_message_text: str,
    incoming_message_timestamp: str,
    user_response_time: str,
    calculated_delay_minutes: int,
    scheduled_send_time: str,
    user_notes: str = "",
    manual_context: str = ""
) -> bool:
    """
    Add a response to the scheduled_responses table for auto-sending.

    Args:
        review_id: ID of the review item
        user_ig_username: Instagram username
        user_subscriber_id: ManyChat subscriber ID
        response_text: The response text to send
        incoming_message_text: Original incoming message
        incoming_message_timestamp: When the incoming message was received
        user_response_time: When the user responded
        calculated_delay_minutes: Calculated delay in minutes
        scheduled_send_time: When to send the response (ISO format)
        user_notes: Optional notes about the response
        manual_context: Optional manual context to include

    Returns:
        bool: True if successfully added, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the scheduled_responses table exists
        create_scheduled_responses_table_if_not_exists(conn)

        # Insert the scheduled response
        cursor.execute("""
        INSERT INTO scheduled_responses (
            review_id, user_ig_username, user_subscriber_id, response_text,
            incoming_message_text, incoming_message_timestamp, user_response_time,
            calculated_delay_minutes, scheduled_send_time, status, user_notes, manual_context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id, user_ig_username, user_subscriber_id, response_text,
            incoming_message_text, incoming_message_timestamp, user_response_time,
            calculated_delay_minutes, scheduled_send_time, 'scheduled', user_notes, manual_context
        ))

        conn.commit()

        # Also persist to messages table so history is complete
        try:
            add_message_to_history(
                user_ig_username, 'ai', response_text, message_timestamp=scheduled_send_time)
        except Exception:
            pass
        conn.close()

        logger.info(
            f"✅ Successfully scheduled response for {user_ig_username} at {scheduled_send_time}")
        return True

    except Exception as e:
        logger.error(
            f"❌ Error adding scheduled response for {user_ig_username}: {e}")
        return False


def log_auto_mode_activity(activity_type: str = None, details: str = "", success: bool = True, error_message: str = None, user_ig_username: str = None, action_type: str = None, message_preview: str = None, status: str = None, auto_mode_type: str = None, processing_time_ms: int = None, action_details: str = None):
    """
    Log auto mode activity to the database for tracking and debugging.

    Args:
        activity_type: Type of activity (e.g., 'response_sent', 'response_failed', 'mode_enabled')
        details: Detailed description of the activity
        success: Whether the activity was successful
        error_message: Error message if the activity failed
        user_ig_username: Instagram username being processed (optional)
        action_type: Type of action being performed (optional)
        message_preview: Preview of the message being processed (optional)
        status: Current status of the activity (optional)
        auto_mode_type: Type of auto mode (general/vegan) (optional)
        processing_time_ms: Processing time in milliseconds (optional)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the auto_mode_activities table exists
        create_auto_mode_tracking_tables_if_not_exists(conn)

        # Use action_type as activity_type if not provided
        if not activity_type and action_type:
            activity_type = action_type

        # Prepare detailed description
        full_details = details
        if user_ig_username:
            full_details += f" | User: {user_ig_username}"
        if message_preview:
            full_details += f" | Message: {message_preview}"
        if status:
            full_details += f" | Status: {status}"
        if auto_mode_type:
            full_details += f" | Mode: {auto_mode_type}"
        if processing_time_ms:
            full_details += f" | Processing Time: {processing_time_ms}ms"
        if action_details:
            full_details += f" | Action Details: {action_details}"

        # Insert the activity log
        cursor.execute("""
        INSERT INTO auto_mode_activities (
            activity_type, details, success, error_message, timestamp
        ) VALUES (?, ?, ?, ?, ?)
        """, (
            activity_type or "auto_mode_activity", full_details, success, error_message, datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        logger.info(
            f"✅ Logged auto mode activity: {activity_type} - {full_details}")

    except Exception as e:
        logger.error(f"❌ Error logging auto mode activity: {e}")


def update_current_processing(processing_status: str = None, details: str = "", user_ig_username: str = None, review_id: int = None, action_type: str = None, step_number: int = None, total_steps: int = None, step_description: str = None, message_text: str = None):
    """
    Update the current processing status for auto mode.

    Args:
        processing_status: Current processing status
        details: Additional details about the processing
        user_ig_username: Instagram username being processed (optional)
        review_id: Review ID being processed (optional)
        action_type: Type of action being performed (optional)
        step_number: Current step number (optional)
        total_steps: Total number of steps (optional)
        step_description: Description of current step (optional)
        message_text: Message text being processed (optional)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the auto_mode_processing table exists
        create_auto_mode_tracking_tables_if_not_exists(conn)

        # Prepare additional details
        additional_details = details
        if user_ig_username:
            additional_details += f" | User: {user_ig_username}"
        if review_id:
            additional_details += f" | Review ID: {review_id}"
        if action_type:
            additional_details += f" | Action: {action_type}"
        if step_number and total_steps:
            additional_details += f" | Step: {step_number}/{total_steps}"
        if step_description:
            additional_details += f" | {step_description}"
        if message_text:
            additional_details += f" | Message: {message_text[:50]}..."

        # Use action_type as processing_status if not provided
        if not processing_status and action_type:
            processing_status = action_type

        # Update or insert the current processing status
        cursor.execute("""
        INSERT OR REPLACE INTO auto_mode_processing (
            id, processing_status, details, timestamp
        ) VALUES (1, ?, ?, ?)
        """, (processing_status or "processing", additional_details, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error updating current processing: {e}")


def clear_current_processing():
    """
    Clear the current processing status.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the auto_mode_processing table exists
        create_auto_mode_tracking_tables_if_not_exists(conn)

        # Clear the current processing status
        cursor.execute("DELETE FROM auto_mode_processing WHERE id = 1")

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error clearing current processing: {e}")


def update_auto_mode_heartbeat(status='active', cycle_count=None, performance_stats=None, error_message=None):
    """
    Update the auto mode heartbeat timestamp.

    Args:
        status: Current status ('active', 'idle', 'error', 'stopped', 'running')
        cycle_count: Current cycle count
        performance_stats: Dictionary of performance statistics
        error_message: Error message if status is 'error'
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the auto_mode_heartbeat table exists
        create_auto_mode_tracking_tables_if_not_exists(conn)

        # Convert performance_stats to JSON string if provided
        performance_stats_json = json.dumps(
            performance_stats) if performance_stats else None

        # Update the heartbeat using the existing table structure
        cursor.execute("""
        INSERT OR REPLACE INTO auto_mode_heartbeat (
            id, last_heartbeat, auto_sender_status, cycle_count, last_error, performance_stats
        ) VALUES (1, ?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), status, cycle_count or 0, error_message, performance_stats_json))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error updating auto mode heartbeat: {e}")


def set_user_in_calorie_flow(ig_username: str, is_in_flow: bool):
    """Sets the is_in_calorie_flow flag for a user. If the column is missing, add it and retry once."""
    with get_db_connection() as conn:
        try:
            conn.execute(
                "UPDATE users SET is_in_calorie_flow = ? WHERE ig_username = ?",
                (int(is_in_flow), ig_username),
            )
            conn.commit()
            logger.info(
                f"Set is_in_calorie_flow to {is_in_flow} for {ig_username}")
        except sqlite3.OperationalError as e:
            if "no such column: is_in_calorie_flow" in str(e).lower():
                try:
                    ensure_all_columns_exist(
                        conn, 'users', {'is_in_calorie_flow': 'INTEGER DEFAULT 0'})
                    conn.execute(
                        "UPDATE users SET is_in_calorie_flow = ? WHERE ig_username = ?",
                        (int(is_in_flow), ig_username),
                    )
                    conn.commit()
                    logger.info(
                        f"Added is_in_calorie_flow and set to {is_in_flow} for {ig_username}")
                except Exception as e2:
                    logger.error(
                        f"Failed to add or set is_in_calorie_flow for {ig_username}: {e2}")
            else:
                logger.error(
                    f"Failed to set calorie flow status for {ig_username}: {e}")
        except sqlite3.Error as e:
            logger.error(
                f"Failed to set calorie flow status for {ig_username}: {e}")


def is_user_in_calorie_flow(ig_username: str) -> bool:
    """Checks if a user is currently in the calorie tracking flow. If column is missing, create it and return False."""
    with get_db_connection() as conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT is_in_calorie_flow FROM users WHERE ig_username = ? LIMIT 1",
                (ig_username,),
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False
        except sqlite3.OperationalError as e:
            if "no such column: is_in_calorie_flow" in str(e).lower():
                try:
                    ensure_all_columns_exist(
                        conn, 'users', {'is_in_calorie_flow': 'INTEGER DEFAULT 0'})
                except Exception:
                    pass
                return False
            return False
        except sqlite3.Error:
            return False


if __name__ == '__main__':  # pragma: no cover
    # This block can be used for direct testing of the utility functions
    try:
        ensure_db_schema()
        print("Database schema verification process completed.")
    except Exception as e:
        print(f"Schema verification failed: {e}")
    # You could add more test calls here, for example:
    # conversations = load_conversations_from_sqlite()
    # print(f"Loaded {len(conversations)} conversations.")
