import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import sqlite3
import json

logger = logging.getLogger(__name__)

SQLITE_DB_PATH = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\app\\analytics_data_good.sqlite"


def ensure_db_schema():
    """Ensures the database schema is up-to-date."""
    conn = None
    try:
        logger.info("Verifying database schema...")
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()

        # Check for 'users' table columns
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = {
            "last_interaction_timestamp": "TEXT",
            "is_in_ad_flow": "BOOLEAN",
            "ad_script_state": "TEXT",
            "ad_scenario": "INTEGER",
            "lead_source": "TEXT"
        }

        for col, col_type in required_columns.items():
            if col not in columns:
                logger.info(
                    f"Adding missing column '{col}' to 'users' table.")
                cursor.execute(
                    f"ALTER TABLE users ADD COLUMN {col} {col_type}")

        conn.commit()
        logger.info("✓ Database schema verified and updated.")

    except sqlite3.Error as e:
        logger.error(f"SQLite error in ensure_db_schema: {e}")
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
    fb_ad: bool = False,
):
    """
    Updates the analytics data in the SQLite database with the latest interaction
    and user information. Creates a new user if one doesn't exist.
    """
    logger.debug(f"Updating analytics for subscriber_id: {subscriber_id}")
    ensure_db_schema()

    conn = None
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()

        # Check if user exists by subscriber_id first
        cursor.execute(
            "SELECT * FROM users WHERE subscriber_id = ?", (subscriber_id,))
        user_exists = cursor.fetchone()

        if not user_exists and ig_username:
            # Fallback to ig_username lookup (handles cases where subscriber_id is missing/blank)
            cursor.execute(
                "SELECT * FROM users WHERE ig_username = ?", (ig_username,))
            user_exists = cursor.fetchone()

        if not subscriber_id:
            subscriber_id_to_use = ig_username
        else:
            subscriber_id_to_use = subscriber_id

        # Preserve existing ad flow state if not explicitly provided
        if user_exists:
            # Check if ad flow parameters were explicitly provided (not using defaults)
            import inspect
            frame = inspect.currentframe()
            args, _, _, values = inspect.getargvalues(frame)
            # Get the current ad flow state from database
            cursor.execute(
                "SELECT is_in_ad_flow, ad_script_state, ad_scenario, lead_source, fb_ad FROM users WHERE subscriber_id = ? OR ig_username = ?", (subscriber_id, ig_username))
            current_ad_state = cursor.fetchone()

            if current_ad_state:
                current_is_in_ad_flow, current_ad_script_state, current_ad_scenario, current_lead_source, current_fb_ad = current_ad_state
                # Only use provided values if they're not the defaults, otherwise preserve existing
                is_in_ad_flow_to_use = is_in_ad_flow if 'is_in_ad_flow' in locals(
                ) and is_in_ad_flow != False else current_is_in_ad_flow
                ad_script_state_to_set = ad_script_state if ad_script_state is not None else current_ad_script_state
                ad_scenario_to_set = ad_scenario if ad_scenario is not None else current_ad_scenario
                lead_source_to_use = lead_source if lead_source is not None else current_lead_source
                fb_ad_to_use = fb_ad if fb_ad else current_fb_ad
            else:
                is_in_ad_flow_to_use = is_in_ad_flow
                ad_script_state_to_set = ad_script_state if is_in_ad_flow else None
                ad_scenario_to_set = ad_scenario if is_in_ad_flow else None
                lead_source_to_use = lead_source
        else:
            is_in_ad_flow_to_use = is_in_ad_flow
            ad_script_state_to_set = ad_script_state if is_in_ad_flow else None
            ad_scenario_to_set = ad_scenario if is_in_ad_flow else None
            lead_source_to_use = lead_source
            fb_ad_to_use = fb_ad

        if user_exists:
            # Update existing user
            logger.debug(f"Updating existing user: {subscriber_id}")

            # Build the SET part of the query dynamically to only update non-None values if needed
            # For now, we update all fields based on the function call for simplicity
            cursor.execute(
                """
                UPDATE users
                SET first_name = ?, last_name = ?, client_status = ?, journey_stage = ?,
                    is_onboarding = ?, is_in_checkin_flow_mon = ?, is_in_checkin_flow_wed = ?,
                    last_interaction_timestamp = ?, client_analysis_json = ?, offer_made = ?,
                    is_in_ad_flow = ?, ad_script_state = ?, ad_scenario = ?, lead_source = ?,
                    fb_ad = ?, ig_username = ?
                WHERE subscriber_id = ?
                """,
                (
                    first_name, last_name, client_status, journey_stage,
                    is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                    timestamp, client_analysis_json, offer_made,
                    is_in_ad_flow_to_use, ad_script_state_to_set, ad_scenario_to_set, lead_source_to_use,
                    fb_ad_to_use, ig_username, subscriber_id_to_use
                ),
            )
        else:
            # Insert new user
            logger.debug(f"Creating new user: {subscriber_id}")
            cursor.execute(
                """
                INSERT INTO users (
                    ig_username, subscriber_id, first_name, last_name, client_status,
                    journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                    last_interaction_timestamp, client_analysis_json, offer_made, is_in_ad_flow,
                    ad_script_state, ad_scenario, lead_source, fb_ad
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ig_username, subscriber_id_to_use, first_name, last_name, client_status,
                    journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                    timestamp, client_analysis_json, offer_made, is_in_ad_flow_to_use,
                    ad_script_state_to_set, ad_scenario_to_set, lead_source_to_use, fb_ad_to_use
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
            # Fallback to legacy columns
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

    except sqlite3.Error as e:
        logger.error(
            f"Database error in update_analytics_data for subscriber {subscriber_id}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in update_analytics_data for subscriber {subscriber_id}: {e}")
    finally:
        if conn:
            conn.close()
