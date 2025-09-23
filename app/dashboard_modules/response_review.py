"""
Response Review Queue Module
Handles the review and approval of AI-generated responses before sending
"""

import app.dashboard_modules.dashboard_sqlite_utils as db_utils
from typing import List, Dict, Any, Optional, Tuple
import threading
import time
import sqlite3
from app.dashboard_modules.auto_mode_state import (
    is_auto_mode_active,
    is_vegan_auto_mode_active,
    set_auto_mode_status,
    set_vegan_auto_mode_status,
    is_vegan_ad_auto_mode_active,
    set_vegan_ad_auto_mode_status
)
from googleapiclient.discovery import build
import googleapiclient.discovery
import google.oauth2.service_account
import json
import google.generativeai as genai
import random
import sys
import os
from pathlib import Path
import streamlit as st
import logging
from datetime import datetime, timedelta

# Import prompts module
try:
    from app import prompts
except ImportError:
    # Fallback - create a minimal prompts module
    class PromptsModule:
        COMBINED_AD_RESPONSE_PROMPT_TEMPLATE = "System prompt template"
        MEMBER_CONVERSATION_PROMPT_TEMPLATE = "Member chat template"
        MONDAY_MORNING_TEXT_PROMPT_TEMPLATE = "Monday morning template"
        CHECKINS_PROMPT_TEMPLATE = "Check-ins template"
        COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE = "General chat template"

    prompts = PromptsModule()

# Set up logger
logger = logging.getLogger(__name__)
try:
    # Prefer absolute import to ensure availability in Streamlit/module contexts
    from app.dashboard_modules.shared_utils import (
        call_gemini_with_retry_sync,
        GEMINI_MODEL_PRO,
        GEMINI_MODEL_FLASH,
    )
except Exception:
    try:
        # Fallback to local-relative import when running inside app/dashboard_modules
        from shared_utils import (
            call_gemini_with_retry_sync,
            GEMINI_MODEL_PRO,
            GEMINI_MODEL_FLASH,
        )
    except Exception:
        # Final fallback: minimal direct Gemini call with simple one-step fallback
        import google.generativeai as _genai
        try:
            # Configure if key present in env; ignore errors here
            _api_key = os.getenv("GEMINI_API_KEY")
            if _api_key:
                _genai.configure(api_key=_api_key)
        except Exception:
            pass

    GEMINI_MODEL_PRO = "gemini-2.5-flash-lite"
    GEMINI_MODEL_FLASH = "gemini-2.0-flash-thinking-exp-01-21"

    def call_gemini_with_retry_sync(model_name: str, prompt: str, retry_count: int = 0) -> str:
        try:
            _model = _genai.GenerativeModel(model_name)
            _resp = _model.generate_content(prompt)
            return (_resp.text or "").strip()
        except Exception:
            # Simple fallback to a broadly available flash model
            if model_name != "gemini-2.0-flash":
                return call_gemini_with_retry_sync("gemini-2.0-flash", prompt, retry_count + 1)
            return ""
# --- Safe DB helper wrappers (work even if module lacks new helpers) ---


def get_review_rationale_safe(review_id: int) -> Optional[str]:
    try:
        if hasattr(db_utils, "get_review_rationale"):
            return db_utils.get_review_rationale(review_id)
    except Exception:
        pass
    # Fallback: direct SQL
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT model_rationale FROM pending_reviews WHERE review_id = ?",
            (review_id,),
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def save_review_rationale_safe(review_id: int, rationale: str) -> bool:
    try:
        if hasattr(db_utils, "save_review_rationale"):
            return db_utils.save_review_rationale(review_id, rationale)
    except Exception:
        pass
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE pending_reviews SET model_rationale = ? WHERE review_id = ?",
            (rationale, review_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_review_candidates_safe(review_id: int) -> list:
    try:
        if hasattr(db_utils, "get_review_candidates"):
            return db_utils.get_review_candidates(review_id)
    except Exception:
        pass
    # Fallback: direct SQL
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT variant_index, response_text, is_selected FROM review_candidates WHERE review_id = ? ORDER BY variant_index ASC",
            (review_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "variant_index": r[0],
                "response_text": r[1],
                "is_selected": bool(r[2]) if r[2] is not None else False,
            }
            for r in rows
        ]
    except Exception:
        return []


def save_review_candidates_safe(review_id: int, responses: list) -> bool:
    try:
        if hasattr(db_utils, "save_review_candidates"):
            return db_utils.save_review_candidates(review_id, responses)
    except Exception:
        pass
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        # Ensure table exists
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS review_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                variant_index INTEGER NOT NULL,
                response_text TEXT NOT NULL,
                is_selected INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(review_id, variant_index)
            )
            """
        )
        cur.execute("DELETE FROM review_candidates WHERE review_id = ?",
                    (review_id,))
        for idx, text in enumerate(responses, start=1):
            cur.execute(
                "INSERT INTO review_candidates (review_id, variant_index, response_text) VALUES (?, ?, ?)",
                (review_id, idx, text),
            )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def mark_review_candidate_selected_safe(review_id: int, variant_index: int) -> bool:
    try:
        if hasattr(db_utils, "mark_review_candidate_selected"):
            return db_utils.mark_review_candidate_selected(review_id, variant_index)
    except Exception:
        pass
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE review_candidates SET is_selected = 0 WHERE review_id = ?",
                    (review_id,))
        cur.execute(
            "UPDATE review_candidates SET is_selected = 1 WHERE review_id = ? AND variant_index = ?",
            (review_id, variant_index),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def add_message_to_history_pg(ig_username: str, message_type: str, message_text: str, message_timestamp: Optional[str] = None):
    """Add a message to PostgreSQL messages table"""
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return False

        import psycopg2
        from psycopg2.extras import RealDictCursor

        if not message_timestamp:
            message_timestamp = datetime.now().isoformat()

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Ensure required tables exist (dashboard may run without webhook initializers)
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id SERIAL PRIMARY KEY,
                  ig_username TEXT UNIQUE,
                  subscriber_id TEXT UNIQUE,
                  first_name TEXT,
                  last_name TEXT,
                  client_status TEXT DEFAULT 'Not a Client',
                  journey_stage TEXT DEFAULT 'Initial Inquiry',
                  is_onboarding BOOLEAN DEFAULT FALSE,
                  is_in_checkin_flow_mon BOOLEAN DEFAULT FALSE,
                  is_in_checkin_flow_wed BOOLEAN DEFAULT FALSE,
                  is_in_ad_flow BOOLEAN DEFAULT FALSE,
                  ad_script_state TEXT,
                  ad_scenario INTEGER,
                  lead_source TEXT,
                  last_interaction_timestamp TEXT,
                  profile_bio_text TEXT,
                  interests_json TEXT DEFAULT '[]',
                  conversation_topics_json TEXT DEFAULT '[]',
                  client_analysis_json TEXT DEFAULT '{}',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                  id SERIAL PRIMARY KEY,
                  ig_username TEXT,
                  subscriber_id TEXT,
                  message_type TEXT,
                  message_text TEXT,
                  sender TEXT,
                  message TEXT,
                  timestamp TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
        except Exception:
            # If ensures fail, continue; insert may still work if tables already exist
            pass

        # Get subscriber_id for this user if available
        cursor.execute(
            "SELECT subscriber_id FROM users WHERE ig_username = %s LIMIT 1", (ig_username,))
        user_result = cursor.fetchone()
        subscriber_id = user_result['subscriber_id'] if user_result else None

        # Normalize message_type to 'user'/'ai'
        mt = (message_type or '').strip().lower()
        if mt in ['incoming', 'client', 'lead', 'human']:
            mt = 'user'
        elif mt in ['outgoing', 'bot', 'shanbot', 'shannon', 'assistant', 'system']:
            mt = 'ai'
        elif mt not in ['user', 'ai']:
            mt = 'unknown'

        # Deduplication: skip insert if same sender+text exists recently
        # Use the provided message_timestamp when available to avoid false negatives
        recent_cutoff = (
            datetime.fromisoformat(message_timestamp.split(
                '+')[0]) if message_timestamp else datetime.now()
        ) - timedelta(minutes=5)
        cursor.execute(
            """
            SELECT COUNT(1) AS cnt FROM messages
            WHERE ig_username = %s AND message_type = %s AND message_text = %s
              AND (created_at >= NOW() - INTERVAL '5 minutes' OR (timestamp IS NOT NULL AND timestamp >= %s))
            """,
            (ig_username, mt, message_text, recent_cutoff.isoformat()),
        )

        row = cursor.fetchone()
        try:
            if isinstance(row, dict):
                exists_recent = int(row.get('cnt', 0)) > 0
            else:
                exists_recent = int((row or [0])[0]) > 0
        except Exception:
            exists_recent = False

        if exists_recent:
            logging.info(
                f"[add_message_to_history_pg] Skipping duplicate recent message for {ig_username} ({mt}): '{message_text[:80]}'")
            conn.close()
            return True

        # Insert into PostgreSQL messages table
        cursor.execute("""
            INSERT INTO messages (ig_username, subscriber_id, message_type, message_text, timestamp, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (ig_username, subscriber_id, mt, message_text, message_timestamp))

        conn.commit()
        conn.close()

        logging.info(
            f"✅ Added {mt} message to PostgreSQL conversation history for {ig_username}")
        return True

    except Exception as e:
        logging.error(
            f"❌ Failed to add message to PostgreSQL conversation history for {ig_username}: {e}")
        return False


try:
    from webhook_handlers import build_member_chat_prompt, get_user_data, format_conversation_history, get_melbourne_time_str, get_conversation_history_by_username, process_conversation_for_media
except ImportError:
    # Fallback functions for when webhook_handlers is not available
    def build_member_chat_prompt(*args, **kwargs):
        return "System initializing..."

    def process_conversation_for_media(conversation_text: str) -> str:
        """Fallback media processing function."""
        return conversation_text

    def get_user_data(ig_username: str, subscriber_id: Optional[str] = None) -> tuple[list, dict, Optional[str]]:
        """
        Get user data from SQLite database for regeneration.
        Returns: (conversation_history, metrics_dict, user_id_key)
        """
        try:
            # Get user data from SQLite
            conn = db_utils.get_db_connection()
            cursor = conn.cursor()

            # Try to find user by ig_username first
            cursor.execute("""
                SELECT subscriber_id, first_name, last_name, client_status, journey_stage,
                       metrics_json, last_message_timestamp
                FROM users
                WHERE ig_username = ?
            """, (ig_username,))

            user_row = cursor.fetchone()

            if not user_row and subscriber_id:
                # Try by subscriber_id if ig_username not found
                cursor.execute("""
                    SELECT subscriber_id, first_name, last_name, client_status, journey_stage,
                           metrics_json, last_message_timestamp
                    FROM users
                    WHERE subscriber_id = ?
                """, (subscriber_id,))
                user_row = cursor.fetchone()

            if not user_row:
                logger.warning(f"User {ig_username} not found in database")
                return [], {}, None

            # Parse metrics_json
            metrics_dict = {}
            if user_row[5]:  # metrics_json
                try:
                    metrics_dict = json.loads(user_row[5])
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid JSON in metrics for {ig_username}")

            # Get conversation history
            conversation_history = []
            if user_row[0]:  # subscriber_id
                cursor.execute("""
                    SELECT message, timestamp, type, sender
                    FROM messages
                    WHERE subscriber_id = ?
                    ORDER BY timestamp ASC
                """, (user_row[0],))

                for row in cursor.fetchall():
                    conversation_history.append({
                        'text': row[0] or '',
                        'timestamp': row[1] or '',
                        'type': row[2] or 'unknown',
                        'sender': row[3] or 'unknown'
                    })

            conn.close()

            # Add basic user info to metrics_dict
            metrics_dict.update({
                'first_name': user_row[1] or '',
                'last_name': user_row[2] or '',
                'client_status': user_row[3] or 'Not a Client',
                'journey_stage': user_row[4] or 'Initial Inquiry'
            })

            # subscriber_id as user_id_key
            return conversation_history, metrics_dict, user_row[0]

        except Exception as e:
            logger.error(f"Error in get_user_data for {ig_username}: {e}")
            return [], {}, None

    def format_conversation_history(history_list: List[Dict[str, str]]) -> str:
        """Formats the conversation history list into a readable string."""
        formatted_lines = []
        for entry in history_list:
            timestamp = entry.get("timestamp", "")
            msg_type = entry.get("type", "unknown").capitalize()
            text = entry.get("text", "")
            # Format timestamp nicely if possible (optional)
            try:
                # Attempt to parse and format timestamp
                dt_object = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00"))
                formatted_ts = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                formatted_ts = timestamp  # Fallback to original string

            formatted_lines.append(f"{formatted_ts} [{msg_type}]: {text}")
        return "\n".join(formatted_lines)

    def _normalize_sender_label(raw_label: str) -> str:
        if not raw_label:
            return 'unknown'
        lbl = raw_label.strip().lower()
        if lbl in ['incoming', 'user', 'client', 'lead', 'human']:
            return 'user'
        if lbl in ['outgoing', 'ai', 'bot', 'shanbot', 'shannon', 'assistant', 'system']:
            return 'ai'
        return lbl

    def clean_and_dedupe_history(history_list: List[Dict[str, Any]], max_items: int = 30) -> List[Dict[str, Any]]:
        """Normalize, sort, and de-duplicate conversation history for clarity and precision.
        - Keeps only non-empty text
        - Normalizes sender/type casing
        - Dedupes by (sender/type, text, timestamp to seconds)
        - Returns last max_items in chronological order
        """
        if not history_list:
            return []

        normalized: List[Dict[str, Any]] = []
        for msg in history_list:
            text = (msg.get('text') or msg.get('message') or '').strip()
            if not text:
                continue
            sender = (msg.get('sender') or msg.get(
                'type') or 'unknown').strip()
            ts_raw = (msg.get('timestamp') or '').strip()
            # Normalize type capitalization (user/ai)
            sender_norm = _normalize_sender_label(sender)
            # Canonicalize timestamp to second resolution
            ts_norm = ts_raw.split('+')[0].split('.')[0] if ts_raw else ''
            normalized.append({
                'text': text,
                'timestamp': ts_norm,
                'type': sender_norm,
                'sender': sender_norm
            })

        # Sort chronologically if timestamps present
        try:
            normalized.sort(key=lambda m: m.get('timestamp') or '')
        except Exception:
            pass

        # Deduplicate while preserving order
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for m in normalized:
            key = (m['sender'], m['text'], m['timestamp'])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(m)

        # Keep only the last max_items in chronological order
        if len(deduped) > max_items:
            deduped = deduped[-max_items:]
        return deduped

    def get_melbourne_time_str():
        return datetime.now().isoformat()

    def get_conversation_history_by_username(ig_username, limit):
        # Implement the logic to fetch conversation history by ig_username from the messages table
        try:
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                # Use PostgreSQL
                import psycopg2
                from psycopg2.extras import RealDictCursor

                conn = psycopg2.connect(database_url)
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                cursor.execute("""
                    SELECT
                        CASE
                            WHEN created_at IS NOT NULL THEN TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF')
                            ELSE timestamp
                        END AS timestamp,
                        COALESCE(message_type, sender) AS message_type,
                        COALESCE(message_text, message) AS message_text,
                        subscriber_id
                    FROM messages
                    WHERE ig_username = %s
                    ORDER BY COALESCE(created_at, NOW()) DESC
                    LIMIT %s
                """, (ig_username, limit))

                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'text': row['message_text'] or '',
                        'timestamp': row['timestamp'] or '',
                        'type': row['message_type'] or 'unknown',
                        'sender': row['message_type'] or 'unknown',
                        'subscriber_id': row['subscriber_id'] or ''
                    })
                conn.close()
                return messages
            else:
                # Use SQLite fallback
                conn = db_utils.get_db_connection()
                cursor = conn.cursor()

                # Get messages from the unified messages table by ig_username
                cursor.execute("""
                    SELECT message_text, timestamp, message_type, type, sender, subscriber_id, message, text
                    FROM messages
                    WHERE ig_username = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (ig_username, limit))

                messages = []
                for row in cursor.fetchall():
                    new_text, timestamp, new_type, old_type, sender, subscriber_id, old_message, old_text = row

                    # Use new standardized columns first, fall back to old columns
                    final_text = new_text if new_text is not None else (
                        old_text if old_text is not None else old_message)
                    final_type = new_type if new_type is not None else (
                        old_type if old_type is not None else sender)

                    messages.append({
                        'text': final_text or '',
                        'timestamp': timestamp or '',
                        'type': final_type or 'unknown',
                        'sender': final_type or 'unknown',  # Keep for compatibility
                        'subscriber_id': subscriber_id or ''
                    })

                # Augment with recent pending_reviews (fallback when messages table is sparse)
                try:
                    cursor.execute(
                        """
                        SELECT incoming_message_text, incoming_message_timestamp, proposed_response_text, final_response_text, created_timestamp
                        FROM pending_reviews
                        WHERE user_ig_username = ?
                        ORDER BY created_timestamp DESC
                        LIMIT 50
                        """,
                        (ig_username,),
                    )
                    for inc_text, inc_ts, proposed_ai, final_ai, created_ts in cursor.fetchall():
                        if inc_text and inc_text.strip():
                            messages.append({
                                'text': inc_text.strip(),
                                'timestamp': (inc_ts or created_ts) or '',
                                'type': 'user',
                                'sender': 'user',
                                'subscriber_id': subscriber_id or ''
                            })
                        ai_text = (final_ai or proposed_ai or '').strip()
                        if ai_text:
                            messages.append({
                                'text': ai_text,
                                'timestamp': (created_ts or inc_ts) or '',
                                'type': 'ai',
                                'sender': 'ai',
                                'subscriber_id': subscriber_id or ''
                            })
                except Exception:
                    pass

                conn.close()
                logging.info(
                    f"📚 Loaded {len(messages)} conversation history items for {ig_username}")
                # Return newest-first list to match IG/debug view
                return messages
        except Exception as e:
            logging.error(
                f"Error loading conversation history by username {ig_username}: {e}")
            return []
# For few-shot examples
try:
    from app.dashboard_modules.dashboard_sqlite_utils import get_good_few_shot_examples, get_vegan_few_shot_examples, get_member_few_shot_examples, is_user_in_vegan_flow
except ImportError:
    # Fallback for relative import
    from dashboard_sqlite_utils import get_good_few_shot_examples, get_vegan_few_shot_examples, get_member_few_shot_examples, is_user_in_vegan_flow

# Add caching for expensive operations


@st.cache_data(ttl=10)  # Cache for 10 seconds so new messages appear quickly
def get_cached_pending_reviews(limit: int = 50) -> List[Dict]:
    """Get pending reviews with caching to improve performance"""
    try:
        reviews = db_utils.get_pending_reviews()
        # Limit the number of reviews loaded initially
        return reviews[:limit] if reviews else []
    except Exception as e:
        st.error(f"Error loading pending reviews: {e}")
        return []


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_user_data(subscriber_id: str) -> Dict:
    """Cache user data to avoid repeated database calls"""
    try:
        return db_utils.get_user_data(subscriber_id) or {}
    except Exception as e:
        return {}


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_conversation_history(subscriber_id: str, limit: int = 20) -> List[Dict]:
    """Load conversation history. Prefer Postgres when DATABASE_URL is set."""
    try:
        import os
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(database_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT ig_username FROM users WHERE subscriber_id = %s LIMIT 1", (subscriber_id,))
            row = cur.fetchone()
            ig_username = (row or {}).get("ig_username") if row else None

            cur.execute(
                """
                SELECT
                       CASE
                           WHEN created_at IS NOT NULL THEN TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF')
                           ELSE timestamp
                       END AS ts,
                       COALESCE(message_type, sender)   AS kind,
                       COALESCE(message_text, message)  AS text
                FROM messages
                WHERE subscriber_id = %s OR ig_username = %s
                ORDER BY COALESCE(created_at, NOW()) DESC, id DESC
                LIMIT %s
                """,
                (subscriber_id, ig_username or subscriber_id, limit),
            )
            rows = cur.fetchall() or []
            conn.close()
            return [
                {"timestamp": r.get("ts"), "type": r.get(
                    "kind"), "text": r.get("text")}
                for r in rows if r.get("text")
            ]

        # SQLite fallback
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ig_username FROM users WHERE subscriber_id = ?", (subscriber_id,))
        user_result = cursor.fetchone()
        if not user_result:
            conn.close()
            return []
            ig_username = user_result[0]
            history = get_conversation_history_by_username(ig_username, limit)
            conn.close()
            return history[:limit] if history else []
    except Exception as e:
        logging.error(
            f"Error in get_cached_conversation_history for {subscriber_id}: {e}")
        return []


# Import ManyChat functionality
try:
    from app.manychat_utils import update_manychat_fields
except ImportError:
    try:
        from manychat_utils import update_manychat_fields
    except ImportError:
        def update_manychat_fields(subscriber_id, field_updates):
            st.error("ManyChat integration not available")
            return False

# Guidance persistence helpers
try:
    from app.dashboard_modules.dashboard_sqlite_utils import save_prompt_guidance, get_prompt_guidance, mark_guidance_used
except Exception:
    try:
        from dashboard_sqlite_utils import save_prompt_guidance, get_prompt_guidance, mark_guidance_used
    except Exception:
        def save_prompt_guidance(*args, **kwargs):
            return False

        def get_prompt_guidance(*args, **kwargs):
            return []

        def mark_guidance_used(*args, **kwargs):
            return None

# Import split_response_into_messages function with robust path handling and fallback
try:
    import sys
    import os
    import re
    PROJECT_ROOT = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..'))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from webhook_handlers import split_response_into_messages  # shared splitter
except Exception:
    # Robust fallback: split only at paragraph/sentence/whitespace boundaries
    import re

    def split_response_into_messages(text: str, max_parts: int = 3, target_len: int = 320, hard_max: int = 520) -> list:
        text = (text or '').strip()
        if not text:
            return []

        # If already short, return as one
        if len(text) <= hard_max:
            return [text]

        def find_best_break(window: str, prefer: int) -> int | None:
            """Return a safe break index within window.
            Preference order: paragraph (\n\n), sentence end, whitespace.
            Choose the last boundary <= prefer; if none, the first > prefer up to len(window).
            Index returned is the position AFTER the boundary so slicing [:idx] is safe.
            """
            boundaries: list[int] = []
            # Paragraph boundaries
            for m in re.finditer(r"\n\s*\n+", window):
                boundaries.append(m.end())
            # Sentence boundaries
            for m in re.finditer(r"(?<=[.!?])\s+", window):
                boundaries.append(m.end())
            # Any whitespace (word boundary)
            for m in re.finditer(r"\s+", window):
                boundaries.append(m.end())

            if not boundaries:
                return None
            boundaries.sort()
            # Last <= prefer
            le = [b for b in boundaries if b <= prefer]
            if le:
                return le[-1]
            # First > prefer
            gt = [b for b in boundaries if b > prefer]
            return gt[0] if gt else None

        parts: list[str] = []
        remaining = text
        while remaining and len(parts) < max_parts - 1:
            if len(remaining) <= hard_max:
                break
            window = remaining[:hard_max]
            idx = find_best_break(window, target_len)
            if not idx:
                # Fallback: avoid mid-word split by scanning left for non-alnum boundary
                scan = target_len
                while scan > 0 and scan < len(window) and window[scan].isalnum():
                    scan -= 1
                idx = scan if scan > 0 else target_len
            chunk = remaining[:idx].rstrip()
            remaining = remaining[idx:].lstrip()
            if chunk:
                parts.append(chunk)
            else:
                break

        # Add the tail as the last part
        if remaining:
            parts.append(remaining)
        # Cap to max_parts
        return parts[:max_parts]

# Import auto mode tracking functions (with fallback if not available)


def check_auto_mode_tracking_available():
    """Check if auto mode tracking is available by testing the functions"""
    try:
        # Ensure tables exist before testing
        conn = db_utils.get_db_connection()
        db_utils.create_auto_mode_tracking_tables_if_not_exists(conn)
        conn.close()

        # Use the already imported db_utils module to access functions
        # This avoids import path issues in different Streamlit contexts
        test_stats = db_utils.get_live_auto_mode_stats()

        # Verify the result is a dictionary (basic sanity check)
        if not isinstance(test_stats, dict):
            raise ValueError(
                "get_live_auto_mode_stats returned unexpected type")

        return True, {
            'get_recent_auto_activities': db_utils.get_recent_auto_activities,
            'get_current_processing': db_utils.get_current_processing,
            'get_auto_mode_heartbeat': db_utils.get_auto_mode_heartbeat,
            'get_live_auto_mode_stats': db_utils.get_live_auto_mode_stats
        }
    except Exception as e:
        logger.error(f"Auto mode tracking check failed: {e}")
        return False, str(e)


def get_auto_mode_functions():
    """Get auto mode functions with fresh check each time (no caching to avoid stale state)"""
    # Clear any cached data to force fresh check
    if hasattr(st, 'cache_data'):
        try:
            st.cache_data.clear()
        except:
            pass  # Ignore if cache clearing fails

    # Always do a fresh check to avoid Streamlit session state issues
    available, result = check_auto_mode_tracking_available()
    if available:
        return True, result
    else:
        return False, None


# Configure logging
logger = logging.getLogger(__name__)

# Import db_utils alias for dashboard_sqlite_utils

# Make sure all tables are created on startup
db_utils.create_all_tables_if_not_exists(db_utils.get_db_connection())

# GLOBAL SESSION STATE INITIALIZATION - Initialize these at module load
if 'auto_mode_active' not in st.session_state:
    st.session_state.auto_mode_active = False
if 'auto_worker_started' not in st.session_state:
    st.session_state.auto_worker_started = False
if 'auto_mode_processed_count' not in st.session_state:
    st.session_state.auto_mode_processed_count = 0
if 'scheduled_responses_tracking' not in st.session_state:
    st.session_state.scheduled_responses_tracking = {}


def set_auto_mode_active(active: bool):
    """
    Set the auto mode status to be shared across the application.
    This is a simple implementation that just updates session state.
    """
    st.session_state.auto_mode_active = active


def calculate_response_delay(user_message_timestamp: str, user_ig_username: str = None, max_hours: int = 12) -> int:
    """
    Calculates a human-like response delay.
    - Responds quickly (1-3 mins) if user replies in under 5 mins.
    - Matches user's response time for slower replies.
    """
    try:
        user_msg_time = datetime.fromisoformat(
            user_message_timestamp.split('+')[0])

        last_ai_message_time = None
        if user_ig_username:
            try:
                conn = db_utils.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                SELECT timestamp FROM conversation_history
                WHERE ig_username = ? AND message_type = 'ai' AND timestamp < ?
                ORDER BY timestamp DESC LIMIT 1
                """, (user_ig_username, user_message_timestamp))
                result = cursor.fetchone()
                if result:
                    last_ai_message_time = datetime.fromisoformat(
                        result['timestamp'].split('+')[0])
                conn.close()
            except Exception as e:
                logger.warning(
                    f"Could not get conversation history for {user_ig_username}: {e}")

        if last_ai_message_time:
            user_response_seconds = (
                user_msg_time - last_ai_message_time).total_seconds()

            # QUICK RESPONSE MODE: Always respond quickly regardless of user response time
            logger.info(
                "Using quick response mode: 1-3 minute delay for all responses")
            delay_minutes = random.randint(1, 3)
        else:
            # Fallback for new conversations: respond quickly
            delay_minutes = random.randint(1, 3)
            logger.info(
                f"No conversation history. Using default short delay: {delay_minutes} mins.")

        # Cap at maximum hours
        max_delay_minutes = max_hours * 60
        delay_minutes = min(delay_minutes, max_delay_minutes)

        # Ensure a minimum delay of at least 1 minute
        delay_minutes = max(delay_minutes, 1)

        return delay_minutes

    except Exception as e:
        logger.error(f"Error calculating response delay: {e}")
        # Default to a safe 5 minutes on any error
        return 5


def schedule_auto_response(review_item, edited_response, user_notes="", manual_context=""):
    """
    Schedule a response to be sent automatically with calculated timing delay.
    This version updates the review status, removing it from the pending queue.

    Args:
        review_item: The review item containing message details
        edited_response: The response text to send
        user_notes: Optional user notes
        manual_context: Optional manual context

    Returns:
        tuple: (success: bool, message: str, delay_minutes: int)
    """
    try:
        review_id = review_item['review_id']
        logger.info(
            f"Attempting to schedule response for Review ID: {review_id}")

        # More robust check: check the review item's own status first.
        # Allow 'pending' (for manual dashboard clicks) and 'auto_scheduled' (for webhook auto-mode)
        if review_item['status'] not in ['pending_review', 'regenerated', 'auto_scheduled']:
            logger.info(
                f"Review ID {review_id} has status '{review_item['status']}' and will be skipped.")
            return True, f"Review already has status '{review_item['status']}'.", 0

        # Check if the review is already scheduled or sent in the dedicated table
        try:
            conn = db_utils.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM scheduled_responses WHERE review_id = ?", (review_id,))
            existing_status_row = cursor.fetchone()
            conn.close()
        except Exception as e:
            # Broadened exception to catch any DB error, including 'no such table' on first run
            logger.warning(
                f"Could not check for existing schedule, proceeding. Error: {e}")
            existing_status_row = None

        user_ig_username = review_item['user_ig_username']
        user_subscriber_id = review_item.get('user_subscriber_id', '')
        incoming_message_text = review_item['incoming_message_text']
        incoming_message_timestamp = review_item['incoming_message_timestamp']
        delay_minutes = calculate_response_delay(
            incoming_message_timestamp, user_ig_username)

        if existing_status_row and existing_status_row[0] in ['scheduled', 'sent']:
            logger.info(
                f"Review ID {review_id} for {user_ig_username} already {existing_status_row[0]} in scheduled_responses. Skipping re-scheduling.")
            # Also update the main review item's status if it's out of sync
            if review_item['status'] != 'auto_scheduled':
                db_utils.update_review_status(
                    review_id, 'auto_scheduled', review_item['proposed_response'])
            return True, f"Response already {existing_status_row[0]}", delay_minutes

        # Determine scheduled send time
        scheduled_send_time = datetime.now() + timedelta(minutes=delay_minutes)
        logger.info(
            f"Scheduling response for {user_ig_username} at {scheduled_send_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Add to scheduled_responses table
        success_db = db_utils.add_scheduled_response(
            review_id=review_id,
            user_ig_username=user_ig_username,
            user_subscriber_id=user_subscriber_id,
            response_text=edited_response,
            incoming_message_text=incoming_message_text,
            incoming_message_timestamp=incoming_message_timestamp,
            user_response_time=incoming_message_timestamp,
            calculated_delay_minutes=delay_minutes,
            scheduled_send_time=scheduled_send_time.isoformat(),
            user_notes=user_notes,
            manual_context=manual_context
        )

        if success_db:
            # Update review status to 'auto_scheduled'
            db_utils.update_review_status(
                review_id, 'auto_scheduled', edited_response)
            logger.info(
                f"Successfully scheduled response and updated review status for {user_ig_username}")
            return True, "Response scheduled successfully", delay_minutes
        else:
            logger.error(
                f"Failed to add response to scheduled_responses table for review {review_id}.")
            return False, "Error writing to scheduling database", 0
    except Exception as e:
        logger.error(
            f"Error in schedule_auto_response for review {review_item.get('review_id', 'N/A')}: {e}", exc_info=True)
        return False, f"Error scheduling auto response: {e}", 0


def handle_auto_schedule(review_item, edited_response, user_notes, manual_context):
    """
    Handles the 'Auto Schedule' action, scheduling the response and updating its status.
    """
    logger.info(
        f"Handling Auto Schedule for {review_item['user_ig_username']} (Review ID: {review_item['review_id']})")

    # Check if the review is already auto_scheduled or sent to prevent re-scheduling
    conn = db_utils.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM pending_reviews WHERE review_id = ?",
                   (review_item['review_id'],))
    current_status_row = cursor.fetchone()
    conn.close()

    if current_status_row and current_status_row[0] in ['auto_scheduled', 'sent', 'discarded', 'learning_log']:
        st.warning(
            f"This response is already in '{current_status_row[0]}' status and cannot be re-scheduled.")
        return False

    success, message, delay_minutes = schedule_auto_response(
        review_item, edited_response, user_notes, manual_context)

    if success:
        st.success(message)
        # Ensure the review is removed from the visible queue immediately
        # by updating its status and rerunning.
        # This is handled *within* schedule_auto_response now via update_review_status.
        st.session_state.last_action_review_id = review_item['review_id']
        st.rerun()  # Rerun to refresh the queue
    else:
        st.error(message)
    return success


def process_scheduled_responses():
    """
    Process scheduled responses that are due to be sent.
    This should be called periodically (e.g., every minute).
    """
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()

        # Get responses that are due to be sent
        current_time = datetime.now().isoformat()
        cursor.execute("""
        SELECT * FROM scheduled_responses
        WHERE status = 'scheduled' AND scheduled_send_time <= ?
        ORDER BY scheduled_send_time ASC
        """, (current_time,))

        due_responses = cursor.fetchall()

        for row in due_responses:
            try:
                # Send the message via ManyChat
                success = send_scheduled_response(dict(row))

                if success:
                    # Update status to sent
                    cursor.execute("""
                    UPDATE scheduled_responses
                    SET status = 'sent', sent_at = ?
                    WHERE schedule_id = ?
                    """, (datetime.now().isoformat(), row['schedule_id']))

                    # Update session state counter
                    st.session_state.auto_mode_processed_count += 1

                    logger.info(
                        f"Successfully sent scheduled response to {row['user_ig_username']}")
                else:
                    # Mark as failed
                    cursor.execute("""
                    UPDATE scheduled_responses
                    SET status = 'failed'
                    WHERE schedule_id = ?
                    """, (row['schedule_id'],))

                    logger.error(
                        f"Failed to send scheduled response to {row['user_ig_username']}")

            except Exception as e:
                logger.error(
                    f"Error processing scheduled response {row['schedule_id']}: {e}")
                # Mark as failed
                cursor.execute("""
                UPDATE scheduled_responses
                SET status = 'failed'
                WHERE schedule_id = ?
                """, (row['schedule_id'],))

        conn.commit()
        conn.close()

        return len(due_responses)

    except Exception as e:
        logger.error(
            f"Error processing scheduled responses: {e}", exc_info=True)
        return 0


def send_scheduled_response(scheduled_response):
    """
    Send a scheduled response via ManyChat.

    Args:
        scheduled_response: Dictionary containing the scheduled response data

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        if not update_manychat_fields:
            logger.error("ManyChat integration not available")
            return False

        user_ig = scheduled_response['user_ig_username']
        subscriber_id = scheduled_response['user_subscriber_id']
        response_text = scheduled_response['response_text']
        review_id = scheduled_response['review_id']
        manual_context = scheduled_response.get('manual_context', '')

        # Handle manual context if provided
        if manual_context and manual_context.strip():
            context_inserted = db_utils.insert_manual_context_message(
                user_ig_username=user_ig,
                subscriber_id=subscriber_id,
                manual_message_text=manual_context.strip(),
                user_message_timestamp_str=scheduled_response['user_response_time']
            )
            if context_inserted:
                logger.info(
                    f"Manual context saved for {user_ig} during auto-send")

        # Send message via ManyChat (same logic as manual send)
        message_chunks = split_response_into_messages(response_text)
        manychat_field_names = ["o1 Response",
                                "o1 Response 2", "o1 Response 3"]

        all_sends_successful = True
        first_chunk_sent_successfully = False

        for i, chunk in enumerate(message_chunks):
            if i < len(manychat_field_names):
                field_name = manychat_field_names[i]
                send_success = update_manychat_fields(
                    subscriber_id, {field_name: chunk})
                if send_success:
                    if i == 0:
                        first_chunk_sent_successfully = True
                    time.sleep(0.5)  # Brief delay between chunks
                else:
                    all_sends_successful = False
                    logger.error(
                        f"Failed to send auto-response part {i+1} to {user_ig}")
                    break
            else:
                logger.warning(
                    f"Auto-response part {i+1} not sent (exceeds ManyChat fields)")
                break

        if first_chunk_sent_successfully:
            update_manychat_fields(subscriber_id, {"response time": "action"})

            # Add to conversation history
            try:
                user_msg_timestamp = datetime.fromisoformat(
                    scheduled_response['user_response_time'].split('+')[0])
                ai_response_timestamp = (
                    user_msg_timestamp + timedelta(seconds=1)).isoformat()
            except (ValueError, KeyError):
                ai_response_timestamp = None

            # Add to learning log (mark as auto-sent)
            db_utils.add_to_learning_log(
                review_id=review_id,
                ig_username=user_ig,
                user_subscriber_id=subscriber_id,
                original_prompt_text="[AUTO MODE]",
                original_gemini_response=response_text,
                edited_response_text=response_text,
                user_notes=f"[AUTO MODE] {scheduled_response.get('user_notes', '')}".strip(
                ),
                is_good_example_for_few_shot=None
            )

            # NOW mark the review as sent so it gets removed from the queue
            db_utils.update_review_status(review_id, "sent", response_text)

            logger.info(f"Successfully sent auto-response to {user_ig}")
            return True
        else:
            logger.error(f"Failed to send auto-response to {user_ig}")
            return False

    except Exception as e:
        logger.error(f"Error sending scheduled response: {e}", exc_info=True)
        return False


def get_scheduled_responses_stats():
    """Get statistics about scheduled responses"""
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()

        # Get counts by status
        cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM scheduled_responses
        GROUP BY status
        """)
        status_counts = {row['status']: row['count']
                         for row in cursor.fetchall()}

        # Get pending count with time info
        cursor.execute("""
        SELECT COUNT(*) as pending_count,
               MIN(scheduled_send_time) as next_send_time
        FROM scheduled_responses
        WHERE status = 'scheduled' AND scheduled_send_time > ?
        """, (datetime.now().isoformat(),))

        pending_info = cursor.fetchone()

        conn.close()

        return {
            'scheduled': status_counts.get('scheduled', 0),
            'sent': status_counts.get('sent', 0),
            'failed': status_counts.get('failed', 0),
            'pending_count': pending_info['pending_count'] if pending_info else 0,
            'next_send_time': pending_info['next_send_time'] if pending_info else None
        }

    except Exception as e:
        logger.error(f"Error getting scheduled responses stats: {e}")
        return {
            'scheduled': 0,
            'sent': 0,
            'failed': 0,
            'pending_count': 0,
            'next_send_time': None
        }


def display_live_auto_mode_status():
    """Display real-time auto mode activity with clean updating status"""

    available, functions = get_auto_mode_functions()

    if not available:
        st.info("🔄 Setting up auto mode tracking system...")
        st.caption(
            "The live status tracker is being initialized. Please refresh in a moment.")
        if functions:  # Show error if we have one
            st.caption(f"Setup issue: {functions}")
        return

    # Get live data
    try:
        stats = functions['get_live_auto_mode_stats']()
        heartbeat = functions['get_auto_mode_heartbeat']()
        current_processing = functions['get_current_processing']()
    except Exception as e:
        st.error(f"Error loading live status: {e}")
        return

    # Header with refresh indicator
    col_header, col_refresh, col_live = st.columns([3, 1, 1])
    with col_header:
        st.subheader("🤖 Auto Mode Live Status")
    with col_refresh:
        if st.button("🔄 Refresh", key="live_status_refresh"):
            st.rerun()
    # Live-mode toggle – if enabled the dashboard auto-refreshes every 10 seconds
    with col_live:
        live_mode_enabled = st.checkbox("🟢 Live", key="live_auto_mode_toggle")

    # When live-mode is on, rerun the script every 10 seconds to fetch fresh stats
    # (simple polling approach – avoids extra dependencies)
    if live_mode_enabled:
        import time as _livetime
        _livetime.sleep(10)
        st.rerun()

    # Status indicators – added separate column for Recent Activity
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        general_active = is_auto_mode_active()
        vegan_active = is_vegan_auto_mode_active()

        if general_active and vegan_active:
            st.success("🤖🌱 BOTH MODES ACTIVE")
            st.caption("✅ All responses + vegans auto-processed")
        elif general_active:
            st.success("🤖 GENERAL AUTO")
            st.caption("✅ All responses auto-processed")
        elif vegan_active:
            st.success("🌱 VEGAN AUTO")
            st.caption("✅ Only fresh vegan leads auto-processed")
        else:
            st.info("⏸️ MANUAL MODE")
            st.caption("Responses require manual review")

    with col2:
        st.metric("Scheduled", stats.get('scheduled', 0))

    with col3:
        st.metric("Recent Activity", stats.get('recent_activity', 0))

    with col4:
        if current_processing:
            user = current_processing.get('user_ig_username', 'unknown')
            step = current_processing.get('step_number', 0)
            total_steps = current_processing.get('total_steps', 0)
            st.warning(f"📤 Sending to @{user}")
            st.caption(
                f"Step {step}/{total_steps}: {current_processing.get('step_description', '')}")
        else:
            st.info("⏳ Waiting for next cycle")
            if heartbeat:
                last_heartbeat = heartbeat.get('last_heartbeat')
                if last_heartbeat:
                    try:
                        heartbeat_time = datetime.fromisoformat(
                            last_heartbeat.split('+')[0])
                        seconds_ago = (datetime.now() -
                                       heartbeat_time).total_seconds()
                        st.caption(f"Last heartbeat: {int(seconds_ago)}s ago")
                    except:
                        st.caption("Heartbeat: Unknown")

    with col5:
        if stats.get('next_send_time'):
            try:
                next_time = datetime.fromisoformat(
                    stats['next_send_time'].split('+')[0])
                time_until = next_time - datetime.now()
                if time_until.total_seconds() > 0:
                    if time_until.total_seconds() < 3600:  # Less than 1 hour
                        time_str = f"{int(time_until.total_seconds() / 60)}min"
                    else:
                        time_str = f"{time_until.total_seconds() / 3600:.1f}h"
                    st.metric("Next Send", time_str)
                else:
                    st.metric("Next Send", "Due now")
            except:
                st.metric("Next Send", "Parse error")
        else:
            st.metric("Next Send", "None queued")


def display_auto_mode_activity_feed():
    """Show recent auto mode activity with timestamp and details"""

    available, functions = get_auto_mode_functions()

    if not available:
        st.info("📋 Activity feed will be available once tracking is initialized")
        return

    col_header, col_toggle = st.columns([3, 1])
    with col_header:
        st.subheader("📋 Recent Activity")
    with col_toggle:
        live_updates = st.checkbox(
            "🔄 Live Updates", value=False, key="activity_live_updates")

    # Get recent activity
    try:
        activities = functions['get_recent_auto_activities'](limit=15)
    except Exception as e:
        st.error(f"Error loading activity feed: {e}")
        return

    if not activities:
        st.info("No recent auto mode activity")
        return

    # Display activities
    for activity in activities:
        timestamp_str = activity.get('timestamp', '')
        user = activity.get('user_ig_username', '')
        action = activity.get('action_type', '')
        status = activity.get('status', 'info')
        message_preview = activity.get('message_preview', '')
        processing_time = activity.get('processing_time_ms', 0)
        auto_mode_type = activity.get('auto_mode_type', 'general')

        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.split('+')[0])
            time_display = timestamp.strftime("%H:%M:%S")
        except:
            time_display = "Unknown"

        # Status-specific styling
        if status == 'success':
            icon = "✅"
            color = "green"
        elif status == 'processing':
            icon = "⚡"
            color = "orange"
        elif status == 'failed':
            icon = "❌"
            color = "red"
        else:
            icon = "ℹ️"
            color = "blue"

        # Create activity row
        col_time, col_activity = st.columns([1, 4])

        with col_time:
            st.caption(time_display)
            if auto_mode_type == 'vegan':
                st.caption("🌱")

        with col_activity:
            if action == 'sent':
                if message_preview:
                    st.markdown(
                        f"{icon} **Response sent to @{user}**: _{message_preview}_")
                else:
                    st.markdown(f"{icon} **Response sent to @{user}**")
                if processing_time:
                    st.caption(f"Processing time: {processing_time}ms")

            elif action == 'sending':
                st.markdown(
                    f"{icon} **Sending to @{user}**: _{message_preview}_")

            elif action == 'scheduled':
                st.markdown(f"⏰ **Scheduled response for @{user}**")
                details = activity.get('action_details', {})
                if details and 'delay_minutes' in details:
                    st.caption(f"Sending in {details['delay_minutes']}min")

            elif action == 'new_message_detected':
                st.markdown(
                    f"🔄 **New message from @{user}** - reprocessing conversation")

            elif action == 'failed':
                st.markdown(f"{icon} **Failed to send to @{user}**")
                details = activity.get('action_details', {})
                if details and 'error' in details:
                    st.caption(f"Error: {details['error']}")

            else:
                st.markdown(f"{icon} **{action}** for @{user}")

    # Auto-refresh if enabled
    if live_updates:
        # Add a small delay and rerun
        import time
        time.sleep(10)
        st.rerun()


def display_current_processing_details():
    """Show detailed information about currently processing response"""

    available, functions = get_auto_mode_functions()

    if not available:
        return

    try:
        current = functions['get_current_processing']()
    except Exception:
        return

    if not current:
        return

    st.subheader(f"📤 Currently Processing: @{current['user_ig_username']}")

    # Progress indicator
    step = current.get('step_number', 0)
    total_steps = current.get('total_steps', 5)
    progress = step / total_steps if total_steps > 0 else 0

    st.progress(progress)
    st.caption(
        f"Step {step}/{total_steps}: {current.get('step_description', 'Unknown step')}")

    # Show message being sent if available
    if current.get('message_text') and step >= 4:  # Assuming step 4+ is sending
        with st.expander("📝 Message Being Sent"):
            st.write(current['message_text'])

    # Show timing info
    try:
        started_at = datetime.fromisoformat(
            current['started_at'].split('+')[0])
        processing_time = (datetime.now() - started_at).total_seconds()
        st.caption(f"⏱️ Processing time: {processing_time:.1f} seconds")
    except:
        pass


def display_enhanced_auto_stats():
    """Display comprehensive auto mode statistics"""

    available, functions = get_auto_mode_functions()

    if not available:
        st.info("📊 Enhanced statistics will be available once tracking is initialized")
        return

    try:
        stats = functions['get_live_auto_mode_stats']()
        heartbeat = functions['get_auto_mode_heartbeat']()
    except Exception as e:
        st.error(f"Error loading statistics: {e}")
        return

    st.subheader("📊 Today's Auto Mode Performance")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sent_today = stats.get('sent_today', 0)
        recent_activity = stats.get('recent_activity', 0)
        st.metric("Messages Sent", sent_today, delta=f"+{recent_activity}/hr")

    with col2:
        avg_time = stats.get('avg_processing_time_ms', 0)
        if avg_time > 0:
            if avg_time < 1000:
                time_display = f"{avg_time:.0f}ms"
            else:
                time_display = f"{avg_time/1000:.1f}s"
        else:
            time_display = "N/A"
        st.metric("Avg Processing Time", time_display)

    with col3:
        # Calculate success rate from recent activities
        activities = functions['get_recent_auto_activities'](limit=50)
        if activities:
            success_count = sum(
                1 for a in activities if a.get('status') == 'success')
            success_rate = (success_count / len(activities)) * 100
            st.metric("Recent Success Rate", f"{success_rate:.1f}%")
        else:
            st.metric("Recent Success Rate", "N/A")

    with col4:
        scheduled = stats.get('scheduled', 0)
        efficiency = "High" if scheduled < 5 else "Medium" if scheduled < 10 else "Low"
        st.metric("Queue Status", efficiency, delta=f"{scheduled} pending")

    # System health indicators
    if heartbeat:
        st.caption("💡 System Health")
        health_status = heartbeat.get('auto_sender_status', 'unknown')

        if health_status == 'running':
            st.success("🟢 Auto Sender: Running")
        elif health_status == 'error':
            st.error("🔴 Auto Sender: Error")
            if heartbeat.get('last_error'):
                st.caption(f"Last error: {heartbeat['last_error']}")
        else:
            st.warning("🟡 Auto Sender: Unknown status")

        cycle_count = heartbeat.get('cycle_count', 0)
        st.caption(f"Completed {cycle_count} processing cycles")


def display_response_review_queue(delete_callback: callable):
    """
    Displays the response review queue, allowing users to approve, edit, or discard responses.
    Auto Mode controls and review stats have been moved to other pages.
    """

    # Note: Auto Mode controls moved to Webhook page; no toggles or feeds here

    # Initialize session state for review queue management
    if 'current_review_user_ig' not in st.session_state:
        st.session_state.current_review_user_ig = None
    if 'last_action_review_id' not in st.session_state:
        st.session_state.last_action_review_id = None

    # Quick refresh control (hidden in production)
    if os.getenv("DEBUG_DASHBOARD") == "1":
        top_col1, top_col2 = st.columns([0.8, 0.2])
        with top_col2:
            if st.button("🔄 Refresh", key="refresh_reviews_top", use_container_width=True):
                try:
                    if hasattr(st, 'cache_data'):
                        st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()

    # Use cached version with short TTL for better UX
    with st.spinner("Loading review queue..."):
        all_pending_reviews = get_cached_pending_reviews(limit=50)

    # Hide debug raw rows expander in production unless DEBUG_DASHBOARD=1
    if os.getenv("DEBUG_DASHBOARD") == "1":
        with st.expander("🔎 Debug: Show raw pending_reviews rows (first 10)"):
            try:
                if os.getenv("DATABASE_URL"):
                    import psycopg2
                    from psycopg2.extras import RealDictCursor
                    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    cur.execute(
                        "SELECT * FROM pending_reviews ORDER BY created_timestamp DESC NULLS LAST, id DESC LIMIT 10")
                    rows = cur.fetchall() or []
                    conn.close()
                else:
                    conn = db_utils.get_db_connection()
                    c = conn.cursor()
                    c.execute(
                        "SELECT * FROM pending_reviews ORDER BY created_timestamp DESC LIMIT 10")
                    cols = [d[0] for d in c.description]
                    rows = [dict(zip(cols, r)) for r in c.fetchall() or []]
                    conn.close()
                if rows:
                    st.dataframe(rows, use_container_width=True)
                else:
                    st.caption("No rows found in pending_reviews.")
            except Exception as e:
                st.error(f"Debug fetch failed: {e}")

    action_was_taken_on_last_run = st.session_state.last_action_review_id is not None
    st.session_state.last_action_review_id = None

    if not all_pending_reviews:
        st.success("🎉 No responses currently pending review!")
        st.session_state.current_review_user_ig = None
        return

    # Add option to load more reviews if needed
    if len(all_pending_reviews) >= 50:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col2:
            if st.button("Load More Reviews", key="load_more_reviews"):
                # Clear cache to force reload with more items
                get_cached_pending_reviews.clear()
                st.rerun()
        with col3:
            if st.button("🔄 Refresh Cache", key="refresh_cache"):
                # Clear all caches to force fresh data
                get_cached_pending_reviews.clear()
                get_cached_user_data.clear()
                get_cached_conversation_history.clear()
                get_cached_user_bio_data.clear()
                st.success("Cache cleared! Refreshing...")
                st.rerun()
        with col1:
            st.info(
                f"Showing first 50 reviews. Click 'Load More' to see additional reviews.")

    # Group reviews by user_ig_username
    reviews_by_user = {}
    for review in all_pending_reviews:
        user_ig = review['user_ig_username']
        if user_ig not in reviews_by_user:
            reviews_by_user[user_ig] = []
        reviews_by_user[user_ig].append(review)

    sorted_users_with_reviews = sorted(list(reviews_by_user.keys()))

    if not sorted_users_with_reviews:
        st.success("🎉 No responses currently pending review (after grouping)!")
        st.session_state.current_review_user_ig = None
        return

    # Determine which user to display
    user_to_display_ig = st.session_state.current_review_user_ig

    if action_was_taken_on_last_run:
        if user_to_display_ig not in reviews_by_user or not reviews_by_user[user_to_display_ig]:
            if user_to_display_ig and user_to_display_ig in sorted_users_with_reviews:
                try:
                    idx = sorted_users_with_reviews.index(user_to_display_ig)
                    user_to_display_ig = sorted_users_with_reviews[(
                        idx + 1) % len(sorted_users_with_reviews)]
                except ValueError:
                    user_to_display_ig = sorted_users_with_reviews[
                        0] if sorted_users_with_reviews else None
            else:
                user_to_display_ig = sorted_users_with_reviews[0] if sorted_users_with_reviews else None

    elif not user_to_display_ig or user_to_display_ig not in sorted_users_with_reviews:
        user_to_display_ig = sorted_users_with_reviews[0] if sorted_users_with_reviews else None

    st.session_state.current_review_user_ig = user_to_display_ig

    if not user_to_display_ig:
        st.success("🎉 All reviews processed or queue is empty!")
        return

    current_user_reviews_to_display = reviews_by_user.get(
        user_to_display_ig, [])

    # UI: Header for current user and skip button
    try:
        user_idx = sorted_users_with_reviews.index(user_to_display_ig)
        st.subheader(
            f"Reviewing {len(current_user_reviews_to_display)} message(s) for: **{user_to_display_ig}**")
        st.caption(
            f"User {user_idx + 1} of {len(sorted_users_with_reviews)} with pending reviews.")
    except ValueError:
        st.error("Error determining current user display. Please refresh.")
        return

    # Placeholders for buttons
    col1, col2, col3 = st.columns([0.6, 0.2, 0.2])

    with col2:
        if len(sorted_users_with_reviews) > 1:
            if st.button("Skip to Next User", key=f"skip_{user_to_display_ig}", use_container_width=True):
                current_idx_for_skip = sorted_users_with_reviews.index(
                    st.session_state.current_review_user_ig)
                next_user_idx = (current_idx_for_skip +
                                 1) % len(sorted_users_with_reviews)
                st.session_state.current_review_user_ig = sorted_users_with_reviews[next_user_idx]
                st.rerun()

    with col3:
        if st.button("⚠️ Delete All For User", key=f"delete_all_{user_to_display_ig}", use_container_width=True, type="primary"):
            success, count = delete_callback(user_to_display_ig)
            if success:
                st.success(
                    f"Successfully deleted {count} review items for {user_to_display_ig}.")
                # Move to the next user after deletion
                if user_to_display_ig in sorted_users_with_reviews:
                    sorted_users_with_reviews.remove(user_to_display_ig)
                if sorted_users_with_reviews:
                    st.session_state.current_review_user_ig = sorted_users_with_reviews[0]
                else:
                    st.session_state.current_review_user_ig = None
                try:
                    if hasattr(st, 'cache_data'):
                        st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()
            else:
                st.error(
                    f"Failed to delete reviews for {user_to_display_ig}.")

    # Hide noisy banner; keep minimal UI
    if os.getenv("DEBUG_DASHBOARD") == "1":
        st.info(
            f"Displaying reviews for {st.session_state.current_review_user_ig}")

    if not current_user_reviews_to_display:
        st.warning(f"No pending reviews found for {user_to_display_ig}")
        if len(sorted_users_with_reviews) > 0:
            st.session_state.current_review_user_ig = sorted_users_with_reviews[(
                user_idx + 1) % len(sorted_users_with_reviews)] if sorted_users_with_reviews else None
        else:
            st.session_state.current_review_user_ig = None
        st.rerun()
        return

    # Display each review item (collapsed option)
    collapse_all_key = "collapse_user_reviews_into_one"
    if collapse_all_key not in st.session_state:
        st.session_state[collapse_all_key] = True
    st.checkbox("Collapse this user's pending messages into one box", key=collapse_all_key,
                help="When on, shows a single combined review for this user so you can reply once.")

    if st.session_state[collapse_all_key] and current_user_reviews_to_display:
        # Build a synthetic combined review item
        combined_texts = []
        combined_ts = None
        latest_prompt = ""
        latest_resp = ""
        latest_review = current_user_reviews_to_display[-1]
        for r in current_user_reviews_to_display:
            txt = (r.get('incoming_message_text') or '').strip()
            if txt:
                combined_texts.append(txt)
            ts = r.get('incoming_message_timestamp')
            if ts and (combined_ts is None or ts > combined_ts):
                combined_ts = ts
        # Combine with line breaks in chronological order
        combined_incoming = "\n".join(combined_texts)
        synthetic = dict(latest_review)
        synthetic['incoming_message_text'] = combined_incoming
        if combined_ts:
            synthetic['incoming_message_timestamp'] = combined_ts
        # Mark in UI only; DB remains unchanged
        display_review_item(synthetic)
    else:
        for review_item in current_user_reviews_to_display:
            display_review_item(review_item)


def display_review_item(review_item):
    """Display a single review item with all controls, now with defensive coding."""
    # Defensive coding: Use .get() to avoid KeyErrors if a review item is malformed
    review_id = review_item.get('review_id', 'N/A')
    user_ig = review_item.get('user_ig_username', 'Unknown User')
    subscriber_id = review_item.get('user_subscriber_id')  # Can be None/empty

    # Safely get message texts, providing an empty string as a fallback to prevent TypeErrors
    incoming_msg = review_item.get('incoming_message_text') or ''
    proposed_resp = review_item.get('proposed_response_text') or ''
    original_prompt = review_item.get('generated_prompt_text') or ''

    # Process media URLs in the incoming message for display
    try:
        processed_incoming_msg = process_conversation_for_media(incoming_msg)
        if processed_incoming_msg != incoming_msg:
            logger.info(
                f"Processed media in incoming message for {user_ig}: {processed_incoming_msg[:100]}...")
    except Exception as e:
        logger.error(f"Error processing media for {user_ig}: {e}")
        processed_incoming_msg = incoming_msg  # Fallback to original

    # The 'user_message_text' key is legacy. We now directly use 'incoming_message_text'.
    # This simplifies the logic and ensures the correct field is always used.
    user_message_text_for_display = processed_incoming_msg

    # 🆕 DEBUG: Log what we're actually displaying
    logger.info(f"Dashboard displaying for {user_ig}:")
    logger.info(f"  - Incoming message text: '{incoming_msg[:100]}...'")
    logger.info(f"  - Processed message: '{processed_incoming_msg[:100]}...'")
    logger.info(
        f"  - Legacy user_message_text: '{review_item.get('user_message_text', 'None')[:100] if review_item.get('user_message_text') else 'None'}...'")

    # Only initialize session state if it doesn't exist - preserve user edits
    if f'review_{review_id}_edit' not in st.session_state:
        st.session_state[f'review_{review_id}_edit'] = proposed_resp

    # Load conversation history using cached function for better performance
    conversation_history = []
    if subscriber_id:
        try:
            conversation_history = get_cached_conversation_history(
                subscriber_id, limit=20)
        except Exception as e:
            logging.warning(
                f"Could not load conversation history for {user_ig}: {e}")
            conversation_history = []

    # If no conversation history found by subscriber_id, try by ig_username
    if not conversation_history and user_ig:
        try:
            # Try to get conversation history by ig_username from the messages table (full normalization)
            conversation_history = get_conversation_history_by_username(
                user_ig, limit=200)
        except Exception as e:
            logging.warning(
                f"Could not load conversation history by username for {user_ig}: {e}")
            conversation_history = []

    # Normalize and de-duplicate conversation history to remove repeated entries
    def _dedupe_history(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        seen_keys = set()
        for msg in items or []:
            text = (msg.get('text') or msg.get('message') or '').strip()
            if not text:
                # Skip empty/whitespace-only messages
                continue
            sender = (msg.get('sender') or msg.get(
                'type') or '').strip().lower()
            timestamp_raw = (msg.get('timestamp') or '').strip()
            # Canonicalize timestamp a bit to avoid sub-second dupes
            timestamp_canon = timestamp_raw.split(
                '+')[0].split('.')[0] if timestamp_raw else ''
            key = (sender, text, timestamp_canon)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            cleaned.append(msg)
        return cleaned

    conversation_history = clean_and_dedupe_history(
        conversation_history, max_items=200)

    key_prefix = f"review_{review_id}_"

    # Header strip: make the identity visible at the very top
    st.subheader(f"Reviewing message for: {user_ig}")
    st.caption(
        "Use the editor below to approve or regenerate. Details follow underneath.")

    # --- Top section: User message, editor/actions, and regenerate guidance ---
    # Default to the current item's prompt type so it follows the active flow
    default_prompt_for_top = (review_item.get('prompt_type') or 'general_chat')
    selected_prompt_type_top = st.session_state.get(
        f"{key_prefix}prompt_selector", default_prompt_for_top)

    # Show the incoming message for quick reference
    st.markdown("**User Message:**")
    display_message_top = user_message_text_for_display
    st.text_area("User Message", value=display_message_top,
                 height=100, disabled=True, key=f"user_msg_{review_id}")

    # Editor
    st.markdown("**Current Proposed AI Response:**")
    edit_key_top = f'{key_prefix}edit'
    if edit_key_top not in st.session_state:
        st.session_state[edit_key_top] = proposed_resp
    edited_response_top = st.text_area(
        "Edit Shanbot's Response:", value=st.session_state[edit_key_top], height=150, key=edit_key_top)

    user_notes_top = st.text_input(
        "Why did you edit this response? (helps AI learn):", key=f"{key_prefix}notes",
        help="Optional: Explain why you made changes to help the AI understand your preferences")

    # Core actions (approve/send, discard, analyze bio)
    display_action_buttons(
        review_item, edited_response_top, user_notes_top,
        manual_context="", selected_prompt_type=selected_prompt_type_top,
        key_prefix=key_prefix,
    )

    # Regenerate at top with open guidance box
    st.markdown("**Regenerate**")
    regen_notes_key_top = f"{key_prefix}regen_notes_{review_id}"
    st.text_area(
        "How should the response be adjusted? (optional)",
        key=regen_notes_key_top,
        height=90,
        placeholder="E.g., confirm price question; keep to 1 sentence; propose call link",
    )
    if st.button("🔄 Regenerate", key=f"{key_prefix}regenerate_top", use_container_width=False,
                 help="Generate a new response using bio and conversation context"):
        extra_guidance_top = st.session_state.get(regen_notes_key_top, "")
        handle_regenerate(
            review_item, selected_prompt_type_top, key_prefix, extra_guidance_top)

    st.divider()

    # The expander now holds additional details (collapsed by default)
    with st.expander(f"Details • Review ID {review_id} • Prompt and context", expanded=False):
        # Display prompt type and regeneration status
        prompt_type = review_item.get('prompt_type', 'unknown')
        prompt_type_display = {
            'general_chat': '💬 General Chat (Lead + Onboarding)',
            'member_chat': '👥 Member Chat (Trial/Paying)',
            'monday_morning_text': '🌅 Monday Morning Check-in',
            'checkins': '💬 Check-ins',
            'facebook_ad_response': '🌱 Vegan Ads (Vegan Challenge)',
            'unknown': '❓ Unknown Prompt Type (Not Set)'
        }

        regeneration_count = review_item.get('regeneration_count', 0)

        col_info1, col_info2 = st.columns([2, 1])
        with col_info1:
            st.info(
                f"**Current Prompt Type:** {prompt_type_display.get(prompt_type, f'❓ {prompt_type}')}")
            if prompt_type == 'unknown':
                st.caption(
                    "💡 **Note:** This review was created before prompt types were tracked. You can change it below for regeneration.")
        with col_info2:
            if regeneration_count > 0:
                st.success(f"🔄 **Regenerated {regeneration_count}x**")
            else:
                st.caption("Original AI response")

        # Prompt type selector for regeneration
        st.write("**Change Prompt Type for Regeneration:**")
        prompt_type_options = {
            'facebook_ad_response': '🌱 Vegan Ads (Vegan Challenge)',
            'member_chat': '👥 Member Chat (Trial/Paying)',
            'monday_morning_text': '🌅 Monday Morning Check-in',
            'checkins': '💬 Check-ins',
            'general_chat': '💬 General Chat (Lead + Onboarding)'
        }

        default_prompt = prompt_type if prompt_type in prompt_type_options else 'general_chat'

        selected_prompt_type = st.selectbox(
            "Select prompt type for regeneration:",
            options=list(prompt_type_options.keys()),
            format_func=lambda x: prompt_type_options[x],
            index=list(prompt_type_options.keys()).index(default_prompt),
            key=f"{key_prefix}prompt_selector",
            help="Choose the prompt type to use when regenerating the response"
        )

        # Option to combine other pending messages for this user into one reply
        combine_toggle_key = f"{key_prefix}combine_pending_{review_id}"
        if combine_toggle_key not in st.session_state:
            st.session_state[combine_toggle_key] = True
        st.checkbox(
            "Combine other pending messages for this user into one reply",
            key=combine_toggle_key,
            help="When on, any other pending messages from this user will be included so a single response covers them all.")

        st.divider()

        # Ensure the current review's incoming message is shown in history
        try:
            incoming_ts = review_item.get(
                'incoming_message_timestamp') or get_melbourne_time_str()
            if user_message_text_for_display and user_message_text_for_display.strip():
                # Avoid duplicating identical last user entry
                last_entry = conversation_history[-1] if conversation_history else None
                last_text = (last_entry.get('text') or last_entry.get(
                    'message') or '').strip() if last_entry else ''
                last_sender = (last_entry.get('sender') or last_entry.get(
                    'type') or '').strip().lower() if last_entry else ''
                if not (last_sender in ['user', 'client'] and last_text == user_message_text_for_display.strip()):
                    conversation_history.append({
                        'timestamp': incoming_ts,
                        'type': 'user',
                        'sender': 'user',
                        'text': user_message_text_for_display.strip()
                    })
        except Exception as _e:
            pass

        # --- Rationale Section ---
        # Helper: build richer rationale
        def _generate_rationale_text():
            try:
                # Determine role (Lead/Member) from DB
                role = "Lead"
                flow = "General"
                ad_state = None
                ad_scenario = None
                try:
                    conn = db_utils.get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT client_status, journey_stage FROM users WHERE ig_username = ? LIMIT 1", (user_ig,))
                    row = cur.fetchone()
                    if row:
                        client_status = (row[0] or '').lower()
                        if any(k in client_status for k in ["active", "trial", "paying", "client"]):
                            role = "Member"
                        # Flow detection (ad/general)
                        cur.execute(
                            "SELECT is_in_ad_flow, ad_script_state, ad_scenario FROM users WHERE ig_username = ? LIMIT 1", (user_ig,))
                        row2 = cur.fetchone()
                        if row2:
                            is_in_ad_flow = bool(
                                row2[0]) if row2[0] is not None else False
                            if is_in_ad_flow:
                                flow = "Ad"
                                ad_state = (row2[1] or 'step1')
                                ad_scenario = row2[2] or 3
                            else:
                                flow = "Member" if role == "Member" else "General"
                    conn.close()
                except Exception:
                    pass

                # Build short, reviewer-only rationale prompt
                conv_preview = "\n".join(
                    [f"- {m.get('type','')[:8]} @ {m.get('timestamp','')}: {m.get('text','')[:140]}" for m in (
                        conversation_history[:6] if conversation_history else [])]
                )

                # Map ad step/scenario for clarity
                step_labels = {
                    'step1': 'Intro/Discover',
                    'step2': 'Goals/Current actions',
                    'step3': 'Call proposal',
                    'step4': 'Booking link / follow-up',
                    'completed': 'Completed'
                }
                scenario_map = {1: 'Vegan', 2: 'Vegetarian', 3: 'Plant-based'}
                step_label = step_labels.get(
                    str(ad_state or '').lower(), 'Intro/Discover') if flow == 'Ad' else 'N/A'
                scenario_label = scenario_map.get(int(
                    ad_scenario) if ad_scenario is not None else 3, 'Plant-based') if flow == 'Ad' else 'N/A'

                rationale_prompt = f"""
You are writing an internal reviewer note explaining why the AI's reply is appropriate. Be concise but specific.
Return 6 bullets in markdown. Do not include system or private instructions.

- Who: Role = {role}; Flow = {flow}; AdStep = {step_label}; AdScenario = {scenario_label}
- Latest user message (quote): "{incoming_msg[:220]}"
- What we replied (summary in 1 line): {proposed_resp[:220]}
- Why it's appropriate now: reference flow position and the user’s recent messages; mention the conversational goal (e.g., validate → insight → ask or move to call proposal if in ad step3)
- Evidence from recent context: cite 2-3 short quotes from below that justify the reply
- Risks/Alternatives: 1 short line (e.g., if low engagement, ask shorter question)

Recent context (last up to 6 messages):
{conv_preview}
"""

                text = call_gemini_with_retry_sync(
                    GEMINI_MODEL_PRO, rationale_prompt)
                return text
            except Exception as e:
                logger.error(f"Rationale generation failed: {e}")
                return None

        # Show rationale
        st.subheader("Why this reply?")
        existing_rationale = get_review_rationale_safe(review_id)
        if not existing_rationale:
            with st.spinner("Generating rationale..."):
                rationale = _generate_rationale_text()
                if rationale:
                    save_review_rationale_safe(review_id, rationale)
                    existing_rationale = rationale
        if existing_rationale:
            st.markdown(existing_rationale)
        else:
            st.caption("No rationale available.")

        if selected_prompt_type != prompt_type:
            st.warning(
                f"⚠️ Prompt type changed from {prompt_type_display.get(prompt_type, prompt_type)} to {prompt_type_options[selected_prompt_type]}")

        st.divider()

        # Manual context section
        if f"{key_prefix}show_manual_context" not in st.session_state:
            st.session_state[f"{key_prefix}show_manual_context"] = False

        if st.button("➕ Add Shannon's Missing Context", key=f"{key_prefix}toggle_manual_context_btn"):
            st.session_state[f"{key_prefix}show_manual_context"] = not st.session_state[
                f"{key_prefix}show_manual_context"]

        manual_context = ""
        if st.session_state[f"{key_prefix}show_manual_context"]:
            manual_context = st.text_area(
                "Shannon's Original Comment/Message (Context for History):",
                height=100,
                key=f"{key_prefix}manual_context_input",
                help="If the user's message is a reply to a comment or DM you sent manually, paste your original message here."
            )

        # Conversation History Section
        show_history = st.toggle(
            "View Conversation History (Last 20 Messages)",
            key=f"{key_prefix}history_toggle",
            value=False
        )

        if show_history and conversation_history:
            st.markdown("**💬 Conversation History:**")

            # Display newest first to match debug rows/IG view
            for i, msg in enumerate(conversation_history):
                # Determine if this is a user or AI message
                sender = _normalize_sender_label(
                    msg.get('sender') or msg.get('type') or 'unknown')
                raw_text = msg.get('text', '') or msg.get(
                    'message', '')  # Try both columns
                # Replace IG CDN media URLs with human-readable descriptions
                message_text = process_conversation_for_media(raw_text)
                timestamp = msg.get('timestamp', '')

                # Format timestamp for display
                try:
                    if timestamp:
                        from datetime import datetime
                        dt = datetime.fromisoformat(
                            timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                    else:
                        formatted_time = 'Unknown time'
                except:
                    formatted_time = timestamp or 'Unknown time'

                # Display message with appropriate styling
                if sender == 'user':
                    st.markdown(
                        f"**👤 User ({formatted_time}):** {message_text}")
                elif sender in ['ai']:
                    st.markdown(
                        f"**🤖 Shanbot ({formatted_time}):** {message_text}")
                else:
                    st.markdown(
                        f"**❓ {sender} ({formatted_time}):** {message_text}")

                # Add separator between messages
                if i < len(conversation_history) - 1:
                    st.divider()
        elif show_history and not conversation_history:
            st.caption(
                "No conversation history found or loaded for this user.")

            # Show last 10 raw DB rows for debug
            if st.toggle("🔧 Show Debug Rows", key=f"{key_prefix}toggle_debug_rows"):
                try:
                    conn = db_utils.get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT timestamp, message_type, message_text, type, text, sender FROM messages WHERE ig_username = ? ORDER BY timestamp DESC LIMIT 10",
                        (user_ig,),
                    )
                    rows = cur.fetchall()
                    conn.close()
                    st.json([
                        {
                            'timestamp': r[0],
                            'message_type': r[1],
                            'message_text': r[2],
                            'type': r[3],
                            'text': r[4],
                            'sender': r[5],
                        } for r in rows
                    ])
                except Exception as e:
                    st.caption(f"DB debug failed: {e}")

        # Always-available raw rows debug (useful even when some history shows)
        if show_history:
            if st.toggle("🔧 Show Raw DB Rows (last 10)", key=f"{key_prefix}toggle_debug_rows_always"):
                try:
                    conn = db_utils.get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT timestamp, message_type, message_text, type, text, sender FROM messages WHERE ig_username = ? ORDER BY timestamp DESC LIMIT 10",
                        (user_ig,),
                    )
                    rows = cur.fetchall()
                    conn.close()
                    st.json([
                        {
                            'timestamp': r[0],
                            'message_type': r[1],
                            'message_text': r[2],
                            'type': r[3],
                            'text': r[4],
                            'sender': r[5],
                        } for r in rows
                    ])
                except Exception as e:
                    st.caption(f"DB debug failed: {e}")

            # Backfill button for this user
            if st.button("🧹 Backfill messages from reviews", key=f"{key_prefix}backfill_btn"):
                with st.spinner("Backfilling from review items..."):
                    try:
                        inserted = db_utils.backfill_messages_from_pending_reviews(
                            user_ig, max_rows=200)
                        st.success(
                            f"Inserted {inserted} conversation rows from review items.")
                        # Clear caches so history reloads
                        try:
                            get_cached_conversation_history.clear()
                        except Exception:
                            pass
                        st.rerun()
                    except Exception as e:
                        st.error(f"Backfill failed: {e}")

            # Debug information to help understand why no history is found
            if st.toggle("🔧 Show Debug Info", key=f"{key_prefix}toggle_debug"):
                st.markdown("**Debug Information:**")
                st.json({
                    "user_ig": user_ig,
                    "subscriber_id": subscriber_id,
                    "subscriber_id_exists": bool(subscriber_id),
                    "conversation_history_length": len(conversation_history),
                    "review_item_keys": list(review_item.keys())
                })

        # Bio & Topics toggle
        show_bio_topics = st.toggle(
            "👤 View Lead Bio & Topics", key=f"{key_prefix}toggle_bio_topics")
        if show_bio_topics:
            display_user_bio_topics(user_ig)

        # Message display and editing (now using the safe variable)
        st.markdown("**User Message:**")

        # 🆕 ENSURE WE SHOW THE COMBINED MESSAGE
        # Always use incoming_message_text (the combined message) instead of any legacy fields
        display_message = user_message_text_for_display

        # If there's a mismatch, show both for debugging
        legacy_message = review_item.get('user_message_text', '')
        if legacy_message and legacy_message != display_message:
            st.warning(
                f"⚠️ Legacy field differs from combined message. Using combined message.")
            if st.toggle("🔧 Show Debug Info", key=f"{key_prefix}show_message_debug"):
                st.caption(f"**Combined message:** {display_message}")
                st.caption(f"**Legacy message:** {legacy_message}")

        st.text_area("User Message (details)", value=display_message,
                     height=100, disabled=True, key=f"user_msg_details_{review_id}")

        # Details expander avoids duplicate editors/actions; actions live at the top.
        st.caption(
            "Actions and regeneration are at the top. This section is for context only.")


@st.cache_data(ttl=600)  # Cache for 10 minutes - bio analysis is expensive
def get_cached_user_bio_data(user_ig: str) -> Dict:
    """Cache user bio and topics data to improve performance"""
    try:
        if 'conversations' in st.session_state.analytics_data and isinstance(st.session_state.analytics_data['conversations'], dict):
            for _, potential_user_container in st.session_state.analytics_data['conversations'].items():
                if isinstance(potential_user_container, dict) and 'metrics' in potential_user_container:
                    metrics_data = potential_user_container['metrics']
                    if isinstance(metrics_data, dict) and metrics_data.get('ig_username', '').lower() == user_ig.lower():
                        return potential_user_container
        return {}
    except Exception as e:
        return {}


def display_user_bio_topics(user_ig):
    """Display user bio and topics information with caching"""
    # Use cached bio data for better performance
    user_container_for_bio = get_cached_user_bio_data(user_ig)

    if user_container_for_bio and 'metrics' in user_container_for_bio:
        metrics_for_bio = user_container_for_bio['metrics']
        client_analysis_for_bio = metrics_for_bio.get('client_analysis', {})

        bio_topics_container = st.container(border=True)
        with bio_topics_container:
            st.markdown("**Instagram Analysis (from User Metrics):**")

            # Display Detected Interests
            detected_interests = client_analysis_for_bio.get("interests", [])
            if not detected_interests:
                detected_interests = metrics_for_bio.get("interests", [])

            if detected_interests:
                st.markdown("- **Detected Interests:**")
                for interest in detected_interests:
                    if interest and not str(interest).startswith('**'):
                        st.markdown(f"  - {interest}")
            else:
                st.markdown(
                    "  - _No detected interests found in client analysis._")

            # Display Recent Activities
            recent_activities = client_analysis_for_bio.get(
                "recent_activities", [])
            if not recent_activities:
                recent_activities = metrics_for_bio.get(
                    "recent_activities", [])

            if recent_activities:
                st.markdown("- **Recent Activities:**")
                for activity in recent_activities:
                    if activity and not str(activity).startswith('**'):
                        st.markdown(f"  - {activity}")
            else:
                st.markdown(
                    "  - _No recent activities found in client analysis._")

            if not detected_interests and not recent_activities:
                st.markdown(
                    "_No specific Instagram analysis details (interests, activities) found._")

            st.markdown(
                "**Suggested Conversation Topics (from User Metrics):**")
            # Import from shared_utils to avoid circular dependency
            try:
                from shared_utils import get_user_topics
                conversation_topics_list = get_user_topics(metrics_for_bio)
                if conversation_topics_list:
                    for topic in conversation_topics_list:
                        st.markdown(f"- {topic}")
                else:
                    st.markdown(
                        "_No specific conversation topics generated for this user yet._")
            except ImportError:
                st.markdown("_Could not load conversation topics function._")
    else:
        st.caption(f"No bio/topics data found for user: '{user_ig}'")


def display_action_buttons(review_item, edited_response, user_notes, manual_context, selected_prompt_type, key_prefix):
    """Display the action buttons for a review item"""
    # Check if Auto Mode is active using the new shared state function
    if is_auto_mode_active():
        # AUTO MODE: Show countdown timer and Send Now button
        col_countdown, col_manual = st.columns([2, 1])

        with col_countdown:
            # Always check database first to see if this review is already scheduled
            already_scheduled = False
            try:
                conn = db_utils.get_db_connection()
                cursor = conn.cursor()

                cursor.execute("""
                SELECT scheduled_send_time, calculated_delay_minutes
                FROM scheduled_responses
                WHERE review_id = ? AND status = 'scheduled'
                LIMIT 1
                """, (review_item['review_id'],))

                result = cursor.fetchone()
                conn.close()

                if result:
                    already_scheduled = True
                    # Use the actual scheduled time from database
                    scheduled_time = datetime.fromisoformat(
                        result['scheduled_send_time'].split('+')[0])
                    time_until = scheduled_time - datetime.now()

                    if time_until.total_seconds() > 0:
                        if time_until.total_seconds() < 3600:  # Less than 1 hour
                            time_str = f"{int(time_until.total_seconds() / 60)} minutes"
                        else:
                            time_str = f"{time_until.total_seconds() / 3600:.1f} hours"
                    else:
                        time_str = "sending now"

                    # Show the countdown with actual scheduled time
                    st.success(
                        f"✅ **Will auto-send in {time_str}**\n\n📅 Sending at: {scheduled_time.strftime('%I:%M %p')}")

            except Exception as e:
                logger.error(f"Error checking scheduled time: {e}")
                already_scheduled = False

            if not already_scheduled:
                # Calculate the delay that would be applied (for preview before scheduling)
                delay_minutes = calculate_response_delay(
                    review_item['incoming_message_timestamp'],
                    review_item['user_ig_username']
                )

                # Calculate when the message would be sent
                scheduled_time = datetime.now() + timedelta(minutes=delay_minutes)

                # Display countdown info
                if delay_minutes >= 60:
                    time_str = f"{delay_minutes/60:.1f} hours"
                else:
                    time_str = f"{delay_minutes} minutes"

                # Show the countdown in a colored container
                st.success(
                    f"✅ **Will auto-send in {time_str}**\n\n📅 Sending at: {scheduled_time.strftime('%I:%M %p')}")

            # Automatically schedule the response if not already scheduled
            if not already_scheduled:
                # Check if this specific review has been auto-scheduled before
                # Use database check instead of session state to prevent re-scheduling on page refresh
                schedule_key = f"auto_scheduled_{review_item['review_id']}"

                # Check database instead of session state to prevent duplicate scheduling
                try:
                    conn = db_utils.get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM scheduled_responses WHERE review_id = ?",
                                   (review_item['review_id'],))
                    already_in_db = cursor.fetchone()[0] > 0
                    conn.close()
                except Exception as e:
                    already_in_db = False
                    logger.error(
                        f"Error checking database for existing schedule: {e}")

                # Only schedule if not already in database AND not in session state
                if not already_in_db and schedule_key not in st.session_state:
                    try:
                        success, message, actual_delay = schedule_auto_response(
                            review_item, edited_response, user_notes, manual_context)

                        if success:
                            st.session_state[schedule_key] = True
                            st.toast(
                                f"✅ Auto-scheduled for {review_item['user_ig_username']}!", icon="⏰")
                            # Don't rerun here to avoid infinite loop
                        else:
                            st.error(f"Failed to auto-schedule: {message}")

                    except Exception as e:
                        st.error(f"Failed to auto-schedule: {str(e)}")
                        logger.error(
                            f"Auto-schedule error: {e}", exc_info=True)
                elif already_in_db:
                    # Mark as scheduled in session state to avoid repeated checks
                    st.session_state[schedule_key] = True
            else:
                # Already scheduled - show scheduled status
                st.caption("⏰ Already scheduled - will be sent automatically")

        with col_manual:
            if st.button("Approve & Send", key=f"{key_prefix}send_now", use_container_width=True,
                         help="Send immediately"):
                handle_approve_and_send(
                    review_item, edited_response, user_notes, manual_context, key_prefix)

        # Clean action row
        st.write("**Actions:**")
        col_actions1, col_actions2, col_actions3 = st.columns([1, 1, 1])

        with col_actions1:
            if st.button("Discard", key=f"{key_prefix}discard_auto", use_container_width=True):
                handle_discard(review_item, user_notes)

        with col_actions2:
            if st.button("🔍 Analyze Bio", key=f"{key_prefix}analyze_bio_auto", use_container_width=True, help="Run Instagram analysis to get bio info"):
                handle_analyze_bio(review_item['user_ig_username'])

        # Remove duplicate regenerate controls in details

    else:
        # MANUAL MODE: simplified layout
        col_actions1, col_actions2, col_actions3 = st.columns([1, 1, 1])

        with col_actions1:
            if st.button("Approve & Send", key=f"{key_prefix}send", type="primary", use_container_width=True):
                handle_approve_and_send(
                    review_item, edited_response, user_notes, manual_context, key_prefix)

        with col_actions2:
            if st.button("Discard", key=f"{key_prefix}discard", use_container_width=True):
                handle_discard(review_item, user_notes)

        with col_actions3:
            if st.button("🔍 Analyze Bio", key=f"{key_prefix}analyze_bio", use_container_width=True, help="Run Instagram analysis to get bio info"):
                handle_analyze_bio(review_item['user_ig_username'])

        # Remove duplicate regenerate controls in details


def handle_approve_and_send(review_item, edited_response, user_notes, manual_context, key_prefix):
    """Handle the approve and send action"""
    review_id = review_item['review_id']
    user_ig = review_item['user_ig_username']
    subscriber_id = review_item['user_subscriber_id']
    # Some legacy rows may not have generated_prompt_text. Fall back gracefully.
    original_prompt = (
        review_item.get('generated_prompt_text')
        or review_item.get('generated_prompt')
        or review_item.get('generated_prompt_text_v1')
        or ''
    )
    proposed_resp = review_item['proposed_response_text']

    # NEW: Automatic learning detection
    response_was_edited = edited_response.strip() != proposed_resp.strip()
    response_was_regenerated = review_item.get('regeneration_count', 0) > 0

    # Auto-generate notes if none provided
    auto_notes = ""
    if response_was_edited and not user_notes.strip():
        auto_notes = "User edited the response"
    elif response_was_regenerated and not response_was_edited and not user_notes.strip():
        auto_notes = "User accepted regenerated response"
    elif not response_was_edited and not response_was_regenerated and not user_notes.strip():
        auto_notes = "User sent original response as-is"

    final_notes = user_notes.strip() if user_notes.strip() else auto_notes

    # Auto-mark as good example if edited or regenerated (user chose it over original)
    auto_is_good_example = response_was_edited or response_was_regenerated

    # Handle manual context if provided
    if manual_context and manual_context.strip():
        context_inserted = db_utils.insert_manual_context_message(
            user_ig_username=user_ig,
            subscriber_id=subscriber_id,
            manual_message_text=manual_context.strip(),
            user_message_timestamp_str=review_item['incoming_message_timestamp']
        )
        if context_inserted:
            st.toast(
                f"Manually entered context saved for {user_ig}!", icon="📝")
        else:
            st.error(f"Failed to save manual context for {user_ig}.")

    # Send message via ManyChat
    message_chunks = split_response_into_messages(edited_response)
    manychat_field_names = ["o1 Response", "o1 Response 2", "o1 Response 3"]
    all_sends_successful = True
    first_chunk_sent_successfully = False

    for i, chunk in enumerate(message_chunks):
        if i < len(manychat_field_names):
            field_name = manychat_field_names[i]
            send_success = update_manychat_fields(
                subscriber_id, {field_name: chunk})
            if send_success:
                if i == 0:
                    first_chunk_sent_successfully = True
                import time
                time.sleep(0.5)
                st.success(f"✅ Sent part {i+1} to {user_ig}")
            else:
                all_sends_successful = False
                st.error(f"❌ Failed to send part {i+1} to {user_ig}")
                break
        else:
            st.warning(
                f"⚠️ Message part {i+1} not sent (exceeds ManyChat fields)")
            break

    if first_chunk_sent_successfully:
        # Update status immediately since message was sent successfully
        db_utils.update_review_status(review_id, "sent", edited_response)

        # Trigger the response in ManyChat
        trigger_success = update_manychat_fields(
            subscriber_id, {"response time": "action"})
        if trigger_success:
            st.success(f"🚀 Message sent successfully to {user_ig}!")
        else:
            st.warning(
                "⚠️ Message sent but failed to trigger response in ManyChat")
            st.success(
                f"✅ Message sent successfully to {user_ig} (trigger issue)")

        # Note: AI message persistence handled once below (centralized backend)
    else:
        st.error("❌ Failed to send any message parts to ManyChat")

    # Persist the triggering USER message as a conversation row (idempotent)
    try:
        incoming_text = (review_item.get(
            'incoming_message_text') or '').strip()
        incoming_ts = review_item.get('incoming_message_timestamp')
        if incoming_text:
            if add_message_to_history_pg:
                add_message_to_history_pg(
                    ig_username=user_ig,
                    message_type='user',
                    message_text=incoming_text,
                    message_timestamp=incoming_ts,
                )
            else:
                db_utils.add_message_to_history(
                    user_ig, 'user', incoming_text, incoming_ts
                )
    except Exception:
        pass

    # Calculate AI response timestamp - IMPROVED to prevent collisions
    try:
        user_msg_timestamp = datetime.fromisoformat(
            review_item['incoming_message_timestamp'].split('+')[0])

        # Add realistic response delay (30-90 seconds) instead of just 1 second
        import random
        delay_seconds = random.randint(30, 90)
        ai_response_timestamp = (
            user_msg_timestamp + timedelta(seconds=delay_seconds)).isoformat()
    except (ValueError, KeyError):
        ai_response_timestamp = None

    # Add the AI message to conversation history with the calculated timestamp
    if edited_response and first_chunk_sent_successfully:
        # Only add to conversation history if the message was actually sent
        write_ok = False
        try:
            # Prefer centralized backend which routes to Postgres/SQLite
            from app.db_backend import add_message_to_history as backend_add_message
            write_ok = bool(backend_add_message(
                ig_username=user_ig,
                message_type="ai",
                message_text=edited_response,
                message_timestamp=ai_response_timestamp,
            ))
        except Exception:
            # Fallback directly to local SQLite helper
            try:
                db_utils.add_message_to_history(
                    ig_username=user_ig,
                    message_type="ai",
                    message_text=edited_response,
                    message_timestamp=ai_response_timestamp,
                )
                write_ok = True
            except Exception as e:
                logger.warning(f"Failed to write AI message to history: {e}")

        if write_ok:
            logger.info(
                f"AI response for {user_ig} added to history with calculated timestamp: {ai_response_timestamp}")
            # NOTE: We no longer update the messages table here since responses should only be added
            # to conversation history when actually sent, not when queued for review
            logger.info(
                f"[Dashboard] Successfully added AI response to conversation history for {user_ig}")
        else:
            logger.error(
                f"❌ Failed to persist AI response to conversation history for {user_ig}")
    elif edited_response and not first_chunk_sent_successfully:
        logger.warning(
            f"Response for {user_ig} was not sent successfully, skipping conversation history update")

    # Add to learning log (mark as auto-sent) - wrapped in try-except to ensure session state clearing happens
    try:
        # Check if user is a paying client for member chat detection
        is_paying_client = False
        try:
            conn = db_utils.get_db_connection()
            cursor = conn.cursor()

            # Try to find user by ig_username
            cursor.execute("""
                SELECT subscriber_id, first_name, last_name, client_status, journey_stage, 
                       metrics_json, last_message_timestamp
                FROM users 
                WHERE ig_username = ?
            """, (user_ig,))

            user_row = cursor.fetchone()
            conn.close()

            if user_row:
                # Parse journey_stage to check if paying client
                journey_stage_json = user_row[4]  # journey_stage
                if journey_stage_json:
                    try:
                        journey_stage = json.loads(journey_stage_json)
                        if isinstance(journey_stage, dict):
                            is_paying_client = journey_stage.get(
                                'is_paying_client', False)
                            trial_start_date_exists = journey_stage.get(
                                'trial_start_date') is not None
                            if trial_start_date_exists:
                                is_paying_client = True
                    except json.JSONDecodeError:
                        pass

                # Also check client_status field
                client_status = user_row[3] or ''  # client_status
                if client_status.lower() in ["active client", "trial", "paying client"]:
                    is_paying_client = True
        except Exception as e:
            logger.warning(f"Error checking client status for {user_ig}: {e}")
            is_paying_client = False

        # Automatically detect conversation type (member, vegan, or general)
        if is_paying_client:
            conversation_type = 'member'
        elif is_user_in_vegan_flow(user_ig):
            conversation_type = 'vegan'
        else:
            conversation_type = 'general'

        db_utils.add_to_learning_log(
            review_id=review_id,
            user_ig_username=user_ig,
            user_subscriber_id=subscriber_id,
            original_prompt_text=original_prompt,
            original_gemini_response=proposed_resp,
            edited_response_text=edited_response,
            user_notes=final_notes,
            is_good_example_for_few_shot=None,
            conversation_type=conversation_type
        )
        logger.info(
            f"Successfully logged learning feedback for review ID {review_id}")
    except Exception as e:
        logger.error(
            f"Failed to add to learning log for review ID {review_id}: {e}")
        # Continue execution even if learning log fails - don't break the send process

    st.session_state.last_action_review_id = review_id

    # Show learning status
    if response_was_edited:
        st.success(
            f"✅ Response sent to {user_ig} and added to learning log (edited response)!")
    elif response_was_regenerated:
        st.success(
            f"✅ Response sent to {user_ig} and added to learning log (regenerated response used)!")
    else:
        st.success(
            f"✅ Response sent to {user_ig} and logged (original response used)!")

    # Clear caches and refresh so user list updates immediately
    try:
        if hasattr(st, 'cache_data'):
            st.cache_data.clear()
    except Exception:
        pass
    # Force page refresh - the review will disappear because its status is now "sent"
    st.rerun()

    if not all_sends_successful:
        st.error(
            f"Failed to send message to {user_ig}. Please check ManyChat logs and try again.")
    # The 'else: st.error("ManyChat integration not available")' part is redundant here
    # as update_manychat_fields already handles API key not configured.


def handle_discard(review_item, user_notes):
    """Handle the discard action"""
    db_utils.update_review_status(review_item['review_id'], "discarded")
    db_utils.add_to_learning_log(
        review_id=review_item['review_id'],
        user_ig_username=review_item['user_ig_username'],
        user_subscriber_id=review_item['user_subscriber_id'],
        original_prompt_text=(
            review_item.get('generated_prompt_text')
            or review_item.get('generated_prompt')
            or review_item.get('generated_prompt_text_v1')
            or ''
        ),
        original_gemini_response=review_item['proposed_response_text'],
        edited_response_text="[DISCARDED]",
        user_notes=f"[DISCARDED by user] {user_notes}".strip(),
        is_good_example_for_few_shot=0
    )

    st.session_state.last_action_review_id = review_item['review_id']
    st.warning(
        f"Response for review {review_item['review_id']} for {review_item['user_ig_username']} discarded. Refreshing...")
    try:
        if hasattr(st, 'cache_data'):
            st.cache_data.clear()
    except Exception:
        pass
    st.rerun()


def handle_analyze_bio(user_ig):
    """Handle bio analysis trigger with improved debugging"""
    success, message = trigger_instagram_analysis_for_user(user_ig)

    if success:
        st.success(message)
    else:
        st.error(message)

    # Add debug option
    st.subheader("🔧 Debug Options")

    if st.button(f"🔍 Debug Analysis for {user_ig}", key=f"debug_{user_ig}"):
        with st.spinner("Running debug analysis..."):
            debug_output = test_instagram_analysis_debug(user_ig)

            with st.expander("🔍 Debug Output", expanded=True):
                st.code(debug_output, language="text")

    # Direct analysis option
    if st.button(f"🎯 Direct Analysis (Bypass Filters)", key=f"direct_{user_ig}"):
        with st.spinner("Starting direct analysis (this may take a few minutes)..."):
            try:
                import subprocess
                import os

                cmd = [
                    "python",
                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot\anaylize_followers.py",
                    "--direct-user", user_ig,
                    "--debug"
                ]

                # Run in new console for visibility
                subprocess.Popen(
                    cmd,
                    cwd=r"C:\Users\Shannon\OneDrive\Desktop\shanbot",
                    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                        subprocess, 'CREATE_NEW_CONSOLE') else 0
                )

                st.success(f"🎯 Direct analysis started for {user_ig}!")
                st.info(
                    "📺 Check the new console window for detailed progress and debugging info")
                st.info(
                    "🔧 The browser will stay open for manual debugging if needed")

            except Exception as e:
                st.error(f"Failed to start direct analysis: {str(e)}")


def handle_regenerate(review_item, selected_prompt_type, key_prefix="", extra_guidance: str = ""):
    """Handle the regenerate action"""
    review_id = review_item['review_id']
    user_ig = review_item['user_ig_username']
    incoming_msg = review_item['incoming_message_text']
    original_prompt = (
        review_item.get('generated_prompt_text')
        or review_item.get('generated_prompt')
        or review_item.get('generated_prompt_text_v1')
        or ''
    )
    subscriber_id = review_item.get('user_subscriber_id', '')

    logger.info(
        f"🔄 Starting regeneration for review_id {review_id}, user {user_ig}, prompt_type {selected_prompt_type}")

    # Load conversation history from database
    conversation_history = []
    if subscriber_id:
        try:
            conversation_history = get_cached_conversation_history(
                subscriber_id, limit=20)
        except Exception as e:
            logger.warning(
                f"Could not load conversation history by subscriber_id for {user_ig}: {e}")

    # If no conversation history found by subscriber_id, try by ig_username
    if not conversation_history and user_ig:
        try:
            conversation_history = get_conversation_history_by_username(
                user_ig, limit=20)
        except Exception as e:
            logger.warning(
                f"Could not load conversation history by username for {user_ig}: {e}")

    # If combine is enabled, pull other pending reviews for this user and merge their incoming texts
    try:
        combine_key = f"{key_prefix}combine_pending_{review_id}"
        combine_enabled = st.session_state.get(combine_key, True)
    except Exception:
        combine_enabled = True

    if combine_enabled:
        try:
            conn = db_utils.get_db_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT incoming_message_text, incoming_message_timestamp
                FROM pending_reviews
                WHERE user_ig_username = ? AND review_id != ? AND status IN ('pending_review','auto_scheduled')
                ORDER BY incoming_message_timestamp ASC
                """,
                (user_ig, review_id),
            )
            rows = cur.fetchall() or []
            conn.close()
            extra_msgs = []
            for row in rows:
                msg_text = (row[0] or '').strip()
                ts = (row[1] or '').strip()
                if msg_text:
                    extra_msgs.append({
                        'text': msg_text,
                        'timestamp': ts,
                        'type': 'user',
                        'sender': 'user'
                    })
            if extra_msgs:
                conversation_history = (
                    conversation_history or []) + extra_msgs
        except Exception as e:
            logger.warning(
                f"Could not merge other pending messages for {user_ig}: {e}")

    logger.info(
        f"📚 Loaded {len(conversation_history)} conversation history items for {user_ig}")

    # Sanitize any test-style user messages that embed AI text (e.g., "Shannon:")
    try:
        conversation_history = _sanitize_embedded_ai_text_in_user_messages(
            conversation_history, user_ig)
    except Exception as e:
        logger.warning(f"History sanitize failed for {user_ig}: {e}")

    # If user is in ad flow, force the Ads prompt to avoid wrong template usage
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT is_in_ad_flow FROM users WHERE ig_username = ? LIMIT 1", (user_ig,))
        row = cur.fetchone()
        conn.close()
        if row and (row[0] == 1 or row[0] is True):
            selected_prompt_type = 'facebook_ad_response'
            logger.info(
                f"🔒 Forcing prompt_type=facebook_ad_response for {user_ig} (in ad flow)")
        else:
            # Heuristic: if their first inbound asks for details, use Ads prompt
            text_lc = (incoming_msg or '').lower()
            detail_triggers = [
                'details', 'more info', 'tell me more', 'how does it work',
                "what's included", 'whats included', 'what is the challenge',
                'what do i get', 'explain', 'info', 'what is it', 'challenge details'
            ]
            if selected_prompt_type != 'facebook_ad_response' and any(t in text_lc for t in detail_triggers):
                selected_prompt_type = 'facebook_ad_response'
                logger.info(
                    f"🎯 Using Ads prompt for {user_ig} based on detail trigger in first inbound")
    except Exception as e:
        logger.warning(
            f"Could not enforce/select ad prompt for {user_ig}: {e}")

    regenerate_key = f"regenerate_status_{review_id}"
    if regenerate_key not in st.session_state:
        st.session_state[regenerate_key] = None

    with st.spinner(f"Regenerating response for {user_ig}..."):
        try:
            # Show debug info if requested
            if st.toggle("🔧 Show Regeneration Debug", key=f"{key_prefix}regenerate_debug"):
                st.markdown("**Regeneration Debug Info:**")
                st.json({
                    "user_ig": user_ig,
                    "subscriber_id": subscriber_id,
                    "prompt_type_used": selected_prompt_type,
                    "conversation_history_count": len(conversation_history),
                    "incoming_message": incoming_msg[:100] + "..." if len(incoming_msg) > 100 else incoming_msg,
                    "original_prompt_length": len(original_prompt)
                })

            logger.info(
                f"🤖 Calling regenerate_with_enhanced_context for {user_ig}")
            prev_proposed = review_item.get('proposed_response_text', '')

            enhanced_response = regenerate_with_enhanced_context(
                user_ig,
                incoming_msg,
                conversation_history,
                original_prompt,
                selected_prompt_type,
                extra_guidance=extra_guidance,
                previous_ai_response=prev_proposed
            )

            # Apply duplicate-question guard and call/link gating on regenerated text
            try:
                enhanced_response = postprocess_regenerated_response(
                    enhanced_response,
                    conversation_history,
                    selected_prompt_type
                )
            except Exception as e:
                logger.warning(f"Postprocess failed for {user_ig}: {e}")

            # Guard: if model output is meta commentary or echoes the guidance, re-prompt once with strict rules
            try:
                if _is_meta_commentary(enhanced_response) or _seems_like_guidance_echo(enhanced_response, extra_guidance):
                    strict_block = (
                        "OUTPUT RULES (Strict):\n"
                        "- Return ONLY the final message to send to the user.\n"
                        "- Do NOT explain, justify, or comment on what to say.\n"
                        "- No quotes, no headings, no meta text. Instagram DM tone.\n"
                        "- Do NOT copy or quote the overrides/guidance; use them only to shape the reply.\n"
                    )
                    enhanced_response_retry = regenerate_with_enhanced_context(
                        user_ig,
                        incoming_msg,
                        conversation_history,
                        original_prompt,
                        selected_prompt_type,
                        extra_guidance=((extra_guidance or "") +
                                        "\n\n" + strict_block).strip(),
                        previous_ai_response=prev_proposed
                    )
                    enhanced_response_retry = postprocess_regenerated_response(
                        enhanced_response_retry, conversation_history, selected_prompt_type
                    )
                    if enhanced_response_retry and not _is_meta_commentary(enhanced_response_retry):
                        enhanced_response = enhanced_response_retry
            except Exception:
                pass

            logger.info(
                f"🎯 Generated response for {user_ig}: {enhanced_response[:100] if enhanced_response else 'None'}...")

            if enhanced_response and enhanced_response.strip() and not _is_meta_commentary(enhanced_response):
                logger.info(f"💾 Updating database for review_id {review_id}")
                update_success = db_utils.update_review_proposed_response(
                    review_id, enhanced_response)

                if update_success:
                    # Persist Shannon's guidance for future runs
                    try:
                        if extra_guidance and extra_guidance.strip():
                            save_prompt_guidance(user_ig, selected_prompt_type,
                                                 extra_guidance.strip(), 1.0)
                    except Exception:
                        pass

                    # Log into learning table as a regeneration triple
                    try:
                        db_utils.add_to_learning_log(
                            review_id=review_id,
                            user_ig_username=user_ig,
                            user_subscriber_id=review_item.get(
                                'user_subscriber_id', ''),
                            original_prompt_text=f"Incoming:\n{incoming_msg}\n\nGuidance:\n{(extra_guidance or '').strip()}",
                            original_gemini_response=prev_proposed or '',
                            edited_response_text=enhanced_response,
                            user_notes="regenerated",
                            conversation_type=selected_prompt_type,
                        )
                    except Exception as _e:
                        logger.warning(f"Learning log (regen) failed: {_e}")

                    # CLEAR THE SESSION STATE so it reloads fresh from database on page refresh
                    if f'review_{review_id}_edit' in st.session_state:
                        del st.session_state[f'review_{review_id}_edit']
                    logger.info(
                        f"✅ Successfully cleared session state for review_id {review_id}")

                    st.session_state[regenerate_key] = (
                        True, "New contextual response generated successfully!")
                    st.success(
                        "✅ New contextual response generated! The page will refresh to show the updated response.")
                    st.toast(
                        f"🔄 Regenerated response for {user_ig} with bio context!", icon="✨")
                    # Clear caches to ensure fresh data on next render
                    try:
                        get_cached_pending_reviews.clear()
                    except Exception:
                        pass
                    try:
                        get_cached_user_data.clear()
                    except Exception:
                        pass
                    try:
                        get_cached_conversation_history.clear()
                    except Exception:
                        pass
                    try:
                        get_cached_user_bio_data.clear()
                    except Exception:
                        pass
                    st.rerun()
                else:
                    logger.error(
                        f"❌ Failed to update database for review_id {review_id}")
                    st.session_state[regenerate_key] = (
                        False, "Failed to update response in database")
                    st.error(
                        "❌ Failed to save the new response. Please try again.")
            else:
                logger.warning(f"⚠️ Empty response generated for {user_ig}")
                st.session_state[regenerate_key] = (
                    False, "AI generated empty response")
                st.error("❌ AI generated an empty response. Please try again.")

        except Exception as e:
            logger.error(
                f"💥 Error in handle_regenerate for {user_ig}: {e}", exc_info=True)
            st.session_state[regenerate_key] = (False, f"Error: {str(e)}")
            st.error(f"❌ Error regenerating response: {str(e)}")


def _sanitize_embedded_ai_text_in_user_messages(history: list, ig_username: str) -> list:
    """Remove embedded AI text accidentally stored inside user messages (e.g., test data like 'Shannon: ...').
    Keeps only the user's own content portion.
    """
    cleaned: list = []
    for entry in history or []:
        try:
            e = dict(entry)
            sender = (e.get('sender') or e.get('type') or '').strip().lower()
            text = (e.get('text') or e.get('message') or '').strip()
            # If user message contains an inline 'Shannon:' or common prefixes, strip everything from that marker onwards
            if sender in ('user', 'incoming', 'client', 'lead', 'human') and text:
                markers = ['\nShannon:', ' Shannon:', 'Shannon:',
                           ' Shanbot:', ' AI:', ' Assistant:']
                cut_idx = min([text.find(m)
                              for m in markers if m in text] or [-1])
                if cut_idx != -1:
                    user_only = text[:cut_idx].strip()
                    if user_only:
                        e['text'] = user_only
                    else:
                        # If nothing remains, keep original but flag minimal
                        e['text'] = text.split(
                            'Lead :', 1)[-1].strip() if 'Lead :' in text else text
            cleaned.append(e)
        except Exception:
            cleaned.append(entry)
    return cleaned


def postprocess_regenerated_response(text: str, conv_history: list, prompt_type: str) -> str:
    """Apply duplicate-question guard and call/link gating to the regenerated text.
    - Removes repeated questions based on recent AI questions
    - Gates Calendly link until an affirmative user response is detected (for ad flow)
    - Enforces max two questions before proposing a call in ad flow
    """
    if not text:
        return text
    try:
        processed = _apply_duplicate_question_guard(text, conv_history)
        if prompt_type == 'facebook_ad_response':
            processed = _apply_two_question_limit(processed, conv_history)
            processed = _apply_call_link_gating(processed, conv_history)
        return processed
    except Exception:
        return text


def _apply_duplicate_question_guard(response_text: str, conv_history: list) -> str:
    """Rewrite response if it repeats recent AI questions (simple, local heuristic)."""
    # Extract recent AI questions from history
    recent_qs: list[str] = []
    try:
        for entry in reversed(conv_history or []):
            if (entry.get('type') or entry.get('sender') or '').lower() == 'ai':
                txt = (entry.get('text') or '').strip()
                if '?' in txt:
                    for part in txt.split('?'):
                        part = part.strip()
                        if part:
                            recent_qs.append(part.lower())
                if len(recent_qs) >= 5:
                    break
        recent_qs = recent_qs[:5]
    except Exception:
        recent_qs = []

    if not recent_qs:
        return response_text

    # If response ends with a question that matches a recent one, drop it
    segments: list[str] = []
    buff = ''
    for ch in response_text:
        buff += ch
        if ch in '.!?':
            segments.append(buff)
            buff = ''
    if buff:
        segments.append(buff)

    cleaned: list[str] = []
    dropped = False
    for seg in segments:
        stripped = seg.strip()
        if stripped.endswith('?'):
            core = stripped[:-1].strip().lower()
            if core in recent_qs:
                dropped = True
                continue
        cleaned.append(seg)

    return (' '.join(s.strip() for s in cleaned).strip()) or response_text


def _apply_call_link_gating(response_text: str, conv_history: list) -> str:
    """Prevent sharing Calendly link unless last user message is affirmative.
    Does not alter non-link responses.
    """
    text_lower = response_text.lower()
    if 'calendly.com' not in text_lower:
        return response_text

    # Detect recent affirmative from user
    affirmative_words = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay',
                         'keen', 'ready', 'sounds good', "let's do it", "let's do this"]
    user_last_affirmative = False
    try:
        for entry in reversed(conv_history or []):
            sender = (entry.get('type') or entry.get('sender') or '').lower()
            if sender == 'ai':
                # stop at last AI turn; we only care about the latest user turn
                break
            if sender == 'user':
                msg = (entry.get('text') or '').lower()
                if any(w in msg for w in affirmative_words):
                    user_last_affirmative = True
                break
    except Exception:
        user_last_affirmative = False

    if user_last_affirmative:
        return response_text

    # Replace with call proposal without link
    fallback = (
        "Thanks for sharing that. Given what you’ve told me, the best next step is a quick call so I can tailor this properly. Would you be open to that?"
    )
    return fallback


def _apply_two_question_limit(response_text: str, conv_history: list) -> str:
    """If ad flow and AI has already asked two or more questions in recent history,
    rewrite current response to a call proposal (no additional questions).
    """
    try:
        # Collect recent AI texts (tail window)
        tail = [((m.get('text') or m.get('message') or '')) for m in (
            conv_history or []) if (m.get('type') or m.get('sender') or '').lower() == 'ai']
        tail_text = tail[-12:]
        asked = 0
        for t in tail_text:
            if not isinstance(t, str):
                continue
            asked += t.count('?')
            if asked >= 2:
                break
        if asked < 2:
            return response_text

        # If current response itself contains a question, suppress it and propose the call
        if '?' in (response_text or ''):
            return ("Thanks for sharing that. Based on what you’ve told me, best next step is a quick call so I can tailor this properly. Keen to book a call?")
        return response_text
    except Exception:
        return response_text


def _is_meta_commentary(text: str) -> bool:
    """Detect if model output is commentary about what to say rather than the message itself."""
    if not text:
        return True
    t = text.strip().lower()
    # Heuristics: phrases indicating planning/commentary
    bad_markers = [
        "we've already given", "we have already given", "let's just say",
        "we should say", "i will reply", "the conversation is finished",
        "we already sent", "i would say", "suggestion:", "response suggestion",
        "here's what to say", "you could say",
    ]
    if any(m in t for m in bad_markers):
        return True
    # If contains headings/bullets without real sentence cadence
    if t.startswith("suggestion") or t.startswith("note:"):
        return True
    # Very short meta like "repeat the same" or "say the same"
    if len(t) <= 40 and ("say the same" in t or "same reply" in t):
        return True
    return False


def _seems_like_guidance_echo(text: str, guidance: str) -> bool:
    """Heuristically detect if the model output is echoing the guidance/overrides.
    - True when output contains large substrings of the guidance
    - True when it includes obvious meta markers we used in prompts
    """
    try:
        if not text:
            return False
        t = (text or "").strip().lower()
        g = (guidance or "").strip().lower()
        # Meta markers used in our prompts
        meta_markers = [
            "session overrides (absolute priority",
            "learned preferences",
            "compliance reminder",
            "output rules (strict)",
            "final reply:",
        ]
        if any(m in t for m in meta_markers):
            return True
        if not g:
            return False
        # If a significant slice of the guidance appears verbatim in output
        if len(g) >= 24:
            sample = g[:24]
            if sample and sample in t:
                return True
        # Token overlap heuristic
        try:
            g_tokens = {w for w in g.split() if len(w) > 3}
            t_tokens = {w for w in t.split() if len(w) > 3}
            if g_tokens:
                overlap = len(g_tokens & t_tokens) / max(1, len(g_tokens))
                if overlap > 0.65:
                    return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def handle_generate_offer(review_item):
    """Handle the generate offer action"""
    review_id = review_item['review_id']
    user_ig = review_item['user_ig_username']
    conversation_history = review_item.get('conversation_history', [])

    logger.info(
        f"🎯 Starting offer generation for review_id {review_id}, user {user_ig}")

    offer_key = f"offer_status_{review_id}"
    if offer_key not in st.session_state:
        st.session_state[offer_key] = None

    with st.spinner(f"Analyzing conversation context for {user_ig}..."):
        try:
            logger.info(f"🧠 Calling generate_offer_hook for {user_ig}")
            offer_response = generate_offer_hook(user_ig, conversation_history)

            logger.info(
                f"🎯 Generated offer for {user_ig}: {offer_response[:100] if offer_response else 'None'}...")

            if offer_response and offer_response.strip():
                # Check if AI determined offer is inappropriate
                if offer_response.startswith("INAPPROPRIATE_CONTEXT"):
                    reason = offer_response.replace(
                        "INAPPROPRIATE_CONTEXT - ", "")
                    logger.info(
                        f"⚠️ Offer deemed inappropriate for {user_ig}: {reason}")
                    st.session_state[offer_key] = (
                        False, f"Offer not appropriate: {reason}")
                    st.warning(
                        f"🤔 **Offer Not Recommended**\n\n{reason}\n\nThe conversation context suggests a direct offer might be tone-deaf. Consider continuing the supportive conversation instead.")
                    st.info(
                        "💡 **Tip:** You can still manually write a supportive response or continue building rapport before making an offer later.")
                else:
                    # Valid offer generated
                    logger.info(
                        f"💾 Updating database for review_id {review_id}")
                    update_success = db_utils.update_review_proposed_response(
                        review_id, offer_response)

                    if update_success:
                        # CLEAR THE SESSION STATE so it reloads fresh from database on page refresh
                        if f'review_{review_id}_edit' in st.session_state:
                            del st.session_state[f'review_{review_id}_edit']
                        logger.info(
                            f"✅ Successfully cleared session state for review_id {review_id}")

                        st.session_state[offer_key] = (
                            True, "Contextually appropriate response generated successfully!")

                        # Check if it's a call proposal vs a supportive message
                        if "call" in offer_response.lower() or "chat" in offer_response.lower():
                            st.success(
                                "✅ Call proposal generated! The page will refresh to show the offer.")
                            st.toast(
                                f"🎯 Generated personalized call offer for {user_ig}!", icon="🎉")
                        else:
                            st.success(
                                "✅ Supportive response generated! The page will refresh to show the message.")
                            st.toast(
                                f"💙 Generated contextually appropriate response for {user_ig}!", icon="🤗")
                        st.rerun()
                    else:
                        logger.error(
                            f"❌ Failed to update database for review_id {review_id}")
                        st.session_state[offer_key] = (
                            False, "Failed to update response in database")
                        st.error(
                            "❌ Failed to save the response. Please try again.")
            else:
                logger.warning(
                    f"⚠️ Empty offer response generated for {user_ig}")
                st.session_state[offer_key] = (
                    False, "AI generated empty response")
                st.error("❌ AI generated an empty response. Please try again.")

        except Exception as e:
            logger.error(
                f"💥 Error in handle_generate_offer for {user_ig}: {e}", exc_info=True)
            st.session_state[offer_key] = (False, f"Error: {str(e)}")
            st.error(f"❌ Error generating offer: {str(e)}")


def regenerate_with_enhanced_context(user_ig_username: str, incoming_message: str, conversation_history: list, original_prompt: str, prompt_type: str = 'general_chat', extra_guidance: str = "", previous_ai_response: str = "") -> str:
    """Regenerate response using enhanced context and specific prompt templates."""
    try:
        logger.info(
            f"🔄 Regenerating response for {user_ig_username} with prompt_type: {prompt_type}")

        # Get user data from database (but don't overwrite the conversation_history parameter)
        _, metrics_dict_from_db, subscriber_id = get_user_data(
            user_ig_username)

        # Extract basic user info from metrics_dict
        current_stage = metrics_dict_from_db.get(
            'journey_stage', 'Initial Inquiry')
        trial_status = metrics_dict_from_db.get(
            'client_status', 'Not a Client')
        first_name = metrics_dict_from_db.get('first_name', '')
        last_name = metrics_dict_from_db.get('last_name', '')
        calculated_full_name = f"{first_name} {last_name}".strip(
        ) or user_ig_username

        # Add the current incoming message to the conversation history for context
        enhanced_conversation_history = conversation_history.copy()
        if incoming_message and incoming_message.strip():
            # Only append if it's not already the last user message in history
            try:
                last_msg = enhanced_conversation_history[-1] if enhanced_conversation_history else None
                last_is_same = False
                if last_msg and (last_msg.get('type') or last_msg.get('sender')) == 'user':
                    last_text = (last_msg.get('text')
                                 or last_msg.get('message') or '').strip()
                    last_is_same = (last_text == incoming_message.strip())
                if not last_is_same:
                    enhanced_conversation_history.append({
                        "timestamp": get_melbourne_time_str(),
                        "type": "user",
                        "text": incoming_message
                    })
            except Exception:
                # If any issue, fall back to appending
                enhanced_conversation_history.append({
                    "timestamp": get_melbourne_time_str(),
                    "type": "user",
                    "text": incoming_message
                })

        # Combine consecutive tail user messages into a single block so we generate ONE reply
        try:
            def _combine_tail_user_messages(history_list: list) -> list:
                if not history_list:
                    return history_list
                # Walk from end to find consecutive user messages
                idx = len(history_list) - 1
                collected_texts = []
                count = 0
                while idx >= 0:
                    entry = history_list[idx]
                    msg_type = (entry.get('type') or entry.get(
                        'sender') or '').lower()
                    if msg_type == 'user':
                        text = (entry.get('text') or entry.get(
                            'message') or '').strip()
                        if text:
                            collected_texts.append(text)
                            count += 1
                            idx -= 1
                            continue
                    # Stop when we hit a non-user or empty
                    break

                if count <= 1:
                    return history_list  # nothing to combine

                # Remove the last `count` user entries
                kept = history_list[:len(history_list) - count]
                # Combine in chronological order
                combined = " \n".join(reversed(collected_texts))
                kept.append({
                    "timestamp": get_melbourne_time_str(),
                    "type": "user",
                    "text": combined
                })
                return kept

            enhanced_conversation_history = _combine_tail_user_messages(
                enhanced_conversation_history)
        except Exception:
            pass

        # Normalize and dedupe history before formatting for the prompt
        try:
            enhanced_conversation_history = clean_and_dedupe_history(
                enhanced_conversation_history, max_items=40
            )
        except Exception:
            # If cleaner not available, proceed with original list
            pass

        # Format conversation history (now includes the combined user message block)
        formatted_history_for_prompt_str = format_conversation_history(
            enhanced_conversation_history)

        # Get few-shot examples based on prompt type
        few_shot_examples = get_few_shot_examples_for_prompt_type(prompt_type)

        # Pull learned guidance and prepend it (highest priority), then any ad-hoc extra_guidance
        learned_guidance_list: list[str] = []
        try:
            learned_guidance_list = get_prompt_guidance(
                user_ig_username, prompt_type, limit=5) or []
        except Exception:
            learned_guidance_list = []
        learned_block = (
            "\n".join([g for g in learned_guidance_list if g.strip()]) or "").strip()

        # Build prompt based on prompt type
        if prompt_type == 'facebook_ad_response':
            # Use the vegan challenge ad response template
            # Pull the current script state and scenario from DB so we don't reset to step1
            script_state_from_db = metrics_dict_from_db.get(
                'ad_script_state', 'step1')
            scenario_from_db = metrics_dict_from_db.get('ad_scenario', 3)
            scenario_map = {1: 'ad_vegan_challenge',
                            2: 'ad_vegetarian_challenge', 3: 'ad_plant_based_challenge'}
            scenario_str = scenario_map.get(
                scenario_from_db, 'ad_plant_based_challenge')

            # Heuristic: detect current ad step from recent conversation to avoid restarting at step1
            def _detect_ad_step(history_items: list, latest_user: str) -> str:
                try:
                    # Look at last ~12 messages
                    tail = history_items[-12:] if history_items else []
                    texts = [((m.get('text') or m.get('message') or '').lower())
                             for m in tail]
                    ai_texts = [((m.get('text') or '').lower()) for m in tail if (
                        m.get('type') or m.get('sender')) == 'ai']
                    user_texts = [((m.get('text') or '').lower()) for m in tail if (
                        m.get('type') or m.get('sender')) == 'user']
                    latest_u = (latest_user or '').lower()

                    # If Calendly link already sent → step7 (link)
                    if any('calendly.com' in t for t in ai_texts):
                        return 'step7'
                    # If user indicates readiness/booking → step6 (confirm)
                    booking_cues = ['book in', 'booked', 'i\'ll book', 'i will book',
                                    'when does it begin', 'time works', 'yep works', 'sounds good', 'yes that works']
                    if any(cue in latest_u for cue in booking_cues):
                        return 'step6'
                    # If AI proposed a call previously and user now confirms → step6
                    ai_offered_call = any(
                        ('quick call' in t or 'have a call' in t or 'phone call' in t) for t in ai_texts)
                    confirmation_cues = ['yes', 'yes please', 'yes plz', 'yeah', 'yep', 'sure',
                                         'ok', 'okay', 'keen', 'ready', "let's do it", "let's do this", 'sounds good']
                    if ai_offered_call and any(cue in latest_u for cue in confirmation_cues):
                        return 'step6'
                    # If AI proposed a call previously → step5 (offer calendar next)
                    if ai_offered_call:
                        return 'step5'
                    # If a total of two questions already asked by AI → step3 (propose call)
                    # Count individual question marks across recent AI messages (not just messages with a question)
                    question_count = 0
                    try:
                        question_count = sum(
                            (t.count('?') if isinstance(t, str) else 0) for t in ai_texts)
                    except Exception:
                        question_count = sum(
                            1 for t in ai_texts if '?' in (t or ''))
                    if question_count >= 2:
                        return 'step3'
                except Exception:
                    pass
                return script_state_from_db or 'step1'

            detected_step = _detect_ad_step(
                enhanced_conversation_history, incoming_message)
            # Prefer the more advanced step between DB and detected (simple precedence order)
            step_rank = {'step1': 1, 'step2': 2, 'step3': 3, 'step4': 4,
                         'step5': 5, 'step6': 6, 'step7': 7, 'completed': 8}
            try:
                chosen_state = detected_step if step_rank.get(detected_step, 0) >= step_rank.get(
                    script_state_from_db, 0) else script_state_from_db
            except Exception:
                chosen_state = script_state_from_db

            prompt_data = {
                "current_melbourne_time_str": get_melbourne_time_str(),
                "ig_username": user_ig_username,
                "script_state": chosen_state,
                "ad_scenario": scenario_str,
                "full_conversation": formatted_history_for_prompt_str
            }
            enhanced_prompt_str = prompts.COMBINED_AD_RESPONSE_PROMPT_TEMPLATE.format_map(
                prompt_data)

            # Inject high-quality few-shot examples from approved edits (learning log) to guide regeneration
            try:
                vegan_examples = db_utils.get_vegan_few_shot_examples(limit=5)
            except Exception:
                vegan_examples = []

            if vegan_examples:
                try:
                    # Build a plain-text examples block (no markdown) to respect formatting rules
                    lines: list[str] = [
                        "EXAMPLE CONVERSATIONS (Learning from approved edits):"
                    ]
                    for ex in vegan_examples:
                        user_line = (ex.get("input") or "").strip()
                        shan_line = (ex.get("output") or "").strip()
                        if user_line and shan_line:
                            lines.append(f"User: {user_line}")
                            lines.append(f"Shannon: {shan_line}")
                            lines.append("")
                    examples_block = "\n".join(lines).strip()
                    if examples_block:
                        enhanced_prompt_str = examples_block + "\n\n" + enhanced_prompt_str
                except Exception:
                    pass

            # Prepend high-priority guidance if provided
            if extra_guidance and extra_guidance.strip():
                enhanced_prompt_str = (
                    "SESSION OVERRIDES (ABSOLUTE PRIORITY - MUST FOLLOW EXACTLY):\n"
                    "- These overrides outrank and replace any conflicting rules, templates, or examples.\n"
                    "- If there is a conflict, follow these overrides.\n\n"
                    f"{extra_guidance.strip()}\n\n" + enhanced_prompt_str
                )
            if learned_block:
                enhanced_prompt_str = (
                    "LEARNED PREFERENCES (High Priority - subordinate to Session Overrides):\n"
                    f"{learned_block}\n\n" + enhanced_prompt_str
                )

        elif prompt_type == 'member_chat':
            # Use member conversation template
            prompt_data = {
                "current_melbourne_time_str": get_melbourne_time_str(),
                "ig_username": user_ig_username,
                "first_name": calculated_full_name.split()[0] if calculated_full_name else user_ig_username,
                "full_conversation": formatted_history_for_prompt_str,
                "fitness_goals": metrics_dict_from_db.get('client_goals', ''),
                "dietary_requirements": metrics_dict_from_db.get('dietary_requirements', ''),
                "current_program": metrics_dict_from_db.get('current_program', ''),
                "few_shot_examples": few_shot_examples
            }
            enhanced_prompt_str = prompts.MEMBER_CONVERSATION_PROMPT_TEMPLATE.format_map(
                prompt_data)
            if extra_guidance and extra_guidance.strip():
                enhanced_prompt_str = (
                    "SESSION OVERRIDES (ABSOLUTE PRIORITY - MUST FOLLOW EXACTLY):\n"
                    "- These overrides outrank and replace any conflicting rules, templates, or examples.\n"
                    "- If there is a conflict, follow these overrides.\n\n"
                    f"{extra_guidance.strip()}\n\n" + enhanced_prompt_str
                )
            if learned_block:
                enhanced_prompt_str = (
                    "LEARNED PREFERENCES (High Priority - subordinate to Session Overrides):\n"
                    f"{learned_block}\n\n" + enhanced_prompt_str
                )

        elif prompt_type == 'monday_morning_text':
            # Use Monday morning check-in template
            prompt_data = {
                "current_melbourne_time_str": get_melbourne_time_str(),
                "ig_username": user_ig_username,
                "first_name": calculated_full_name.split()[0] if calculated_full_name else user_ig_username,
                "full_conversation": formatted_history_for_prompt_str,
                "few_shot_examples": few_shot_examples
            }
            enhanced_prompt_str = prompts.MONDAY_MORNING_TEXT_PROMPT_TEMPLATE.format_map(
                prompt_data)
            if extra_guidance and extra_guidance.strip():
                enhanced_prompt_str = (
                    "SESSION OVERRIDES (ABSOLUTE PRIORITY - MUST FOLLOW EXACTLY):\n"
                    "- These overrides outrank and replace any conflicting rules, templates, or examples.\n"
                    "- If there is a conflict, follow these overrides.\n\n"
                    f"{extra_guidance.strip()}\n\n" + enhanced_prompt_str
                )
            if learned_block:
                enhanced_prompt_str = (
                    "LEARNED PREFERENCES (High Priority - subordinate to Session Overrides):\n"
                    f"{learned_block}\n\n" + enhanced_prompt_str
                )

        elif prompt_type == 'checkins':
            # Use general check-ins template
            prompt_data = {
                "current_melbourne_time_str": get_melbourne_time_str(),
                "ig_username": user_ig_username,
                "first_name": calculated_full_name.split()[0] if calculated_full_name else user_ig_username,
                "full_conversation": formatted_history_for_prompt_str,
                "few_shot_examples": few_shot_examples
            }
            enhanced_prompt_str = prompts.CHECKINS_PROMPT_TEMPLATE.format_map(
                prompt_data)
            if extra_guidance and extra_guidance.strip():
                enhanced_prompt_str = (
                    "SESSION OVERRIDES (ABSOLUTE PRIORITY - MUST FOLLOW EXACTLY):\n"
                    "- These overrides outrank and replace any conflicting rules, templates, or examples.\n"
                    "- If there is a conflict, follow these overrides.\n\n"
                    f"{extra_guidance.strip()}\n\n" + enhanced_prompt_str
                )
            if learned_block:
                enhanced_prompt_str = (
                    "LEARNED PREFERENCES (High Priority - subordinate to Session Overrides):\n"
                    f"{learned_block}\n\n" + enhanced_prompt_str
                )

        else:  # general_chat (default)
            # Use the general chat and onboarding template
            prompt_data = {
                "current_melbourne_time_str": get_melbourne_time_str(),
                "ig_username": user_ig_username,
                "bio_context": metrics_dict_from_db.get('bio_context', ''),
                "weekly_workout_summary": metrics_dict_from_db.get('weekly_workout_summary', ''),
                "meal_plan_summary": metrics_dict_from_db.get('meal_plan_summary', ''),
                "current_stage": current_stage,
                "trial_status": trial_status,
                "full_conversation": formatted_history_for_prompt_str,
                "few_shot_examples": few_shot_examples
            }
            enhanced_prompt_str = prompts.COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE.format_map(
                prompt_data)
            if extra_guidance and extra_guidance.strip():
                enhanced_prompt_str = (
                    "SESSION OVERRIDES (ABSOLUTE PRIORITY - MUST FOLLOW EXACTLY):\n"
                    "- These overrides outrank and replace any conflicting rules, templates, or examples.\n"
                    "- If there is a conflict, follow these overrides.\n\n"
                    f"{extra_guidance.strip()}\n\n" + enhanced_prompt_str
                )
            if learned_block:
                enhanced_prompt_str = (
                    "LEARNED PREFERENCES (High Priority - subordinate to Session Overrides):\n"
                    f"{learned_block}\n\n" + enhanced_prompt_str
                )

        # Add globally enforced output rules up-front for every prompt type
        try:
            strict_output_rules = (
                "OUTPUT RULES (Strict):\n"
                "- Return ONLY the final message to send in Instagram DM tone.\n"
                "- Do NOT copy or quote the overrides/guidance.\n"
                "- No headings, bullets, or meta commentary.\n"
                "- Keep it concise (1-3 short sentences) unless proposing a call.\n"
                "- If proposing a call, follow the ad-step logic; no Calendly link unless the last user turn is clearly affirmative.\n"
            )
            enhanced_prompt_str = strict_output_rules + "\n\n" + enhanced_prompt_str
        except Exception:
            pass

        # Global compliance tail: reinforce overrides and avoid repeating previous AI output
        try:
            tail_blocks: list[str] = []
            if extra_guidance and extra_guidance.strip():
                tail_blocks.append(
                    "COMPLIANCE REMINDER:\n"
                    "- You must follow the SESSION OVERRIDES exactly.\n"
                    "- If any instruction conflicts with any template or example, the overrides win.\n"
                )
            if previous_ai_response and previous_ai_response.strip():
                tail_blocks.append(
                    "PREVIOUS AI RESPONSE (do not repeat or paraphrase):\n"
                    f"{previous_ai_response.strip()}\n\n"
                    "Rewrite with materially different wording that satisfies the SESSION OVERRIDES."
                )
            if tail_blocks:
                enhanced_prompt_str = enhanced_prompt_str + \
                    "\n\n" + "\n\n".join(tail_blocks)
        except Exception:
            pass

        # Call Gemini with the appropriate prompt
        generated_response = call_gemini_with_retry_sync(
            GEMINI_MODEL_PRO, enhanced_prompt_str)

        if not generated_response:
            logger.warning(
                f"Gemini returned an empty response for {user_ig_username} during regeneration. Prompt type: {prompt_type}")
            return "Sorry, I had a bit of a brain fade there. Can you tell me what you were looking for again?"

        # Final safeguard: if model still echoes guidance, strip it by re-asking succinctly
        try:
            if _seems_like_guidance_echo(generated_response, extra_guidance):
                repair_prompt = (
                    "Rewrite the following into the final Instagram DM reply.\n"
                    "Rules: Do NOT include any meta text or repeat the guidance; output only the message.\n\n"
                    f"GUIDANCE: {extra_guidance or ''}\n\n"
                    f"CANDIDATE_REPLY: {generated_response}\n\n"
                    "FINAL REPLY:"
                )
                repaired = call_gemini_with_retry_sync(
                    GEMINI_MODEL_FLASH, repair_prompt)
                if repaired and not _seems_like_guidance_echo(repaired, extra_guidance) and not _is_meta_commentary(repaired):
                    generated_response = repaired
        except Exception:
            pass

        try:
            if learned_guidance_list:
                mark_guidance_used(
                    user_ig_username, prompt_type, learned_guidance_list)
        except Exception:
            pass

        return generated_response

    except Exception as e:
        logger.error(
            f"Error in regenerate_with_enhanced_context for {user_ig_username}: {e}", exc_info=True)
        return f"Sorry, I'm having trouble generating a response right now. Error: {str(e)}"


def get_few_shot_examples_for_prompt_type(prompt_type: str) -> str:
    """Get few-shot examples for the specific prompt type."""
    # This is a placeholder - in the full implementation, you would load
    # specific few-shot examples for each prompt type from a database or file
    if prompt_type == 'facebook_ad_response':
        return """
**Example Vegan Ad Response:**
User: "Can you tell me about the vegan challenge?"
Shannon: "Hey! Awesome to hear from you. I'd love to tell you more. As the ad mentioned, I'm personally guiding a small, dedicated group of 6 vegans through my weight training and nutrition system. The program generally helps vegans lose 2-3kgs, plus tone up. The challenge is all about - movement, plant based nutrition and motivation. What would you be aiming to achieve in the 28 days? 😊
"""
    elif prompt_type == 'member_chat':
        return """
**Example Member Chat:**
Member: "Done!!!"
Shannon: "Hell yeah!"
"""
    elif prompt_type == 'checkin_monday':
        return """
**Example Monday Check-in:**
Shannon: "Goooooood Morning! Ready for the week?"
"""
    elif prompt_type == 'checkin_wednesday':
        return """
**Example Wednesday Check-in:**
Shannon: "Heya! Hows your week going?"
"""
    else:  # general_chat
        return """
**Example General Chat:**
User: "Hey Shannon!"
Shannon: "Hey! How's your day going?"
"""


# Cache for 30 minutes - Instagram analysis is expensive
@st.cache_data(ttl=1800)
def trigger_instagram_analysis_for_user(ig_username: str) -> tuple[bool, str]:
    """
    Trigger Instagram analysis for a specific user by calling anaylize_followers.py
    Cached to avoid repeated expensive analysis calls
    """
    import subprocess
    import tempfile
    import os
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Step 1: Validate username
        if not ig_username or not ig_username.strip():
            return False, "❌ No username provided for analysis"

        clean_username = ig_username.strip()
        logger.info(f"Starting Instagram analysis for: {clean_username}")

        # Step 2: Clear any existing progress file to ensure fresh analysis
        progress_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\analysis_progress.json"
        if os.path.exists(progress_file):
            try:
                os.remove(progress_file)
                logger.info(f"Cleared existing progress file: {progress_file}")
            except Exception as e:
                logger.warning(f"Could not clear progress file: {e}")

        # Step 3: Create a more persistent temporary file with better naming
        temp_dir = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\temp"
        os.makedirs(temp_dir, exist_ok=True)

        temp_file_path = os.path.join(
            temp_dir, f"analysis_{clean_username}.txt")

        # Write username to file
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(clean_username)

        logger.info(
            f"Created analysis file for {clean_username}: {temp_file_path}")

        # Step 4: Resolve analyzer script path with fallbacks
        # Prefer repo-relative path; fall back to historical absolute if present
        repo_root = os.getcwd()
        analyzer_candidates = [
            os.path.join(repo_root, "anaylize_followers.py"),
            os.path.join(repo_root, "analyze_followers.py"),
            r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\anaylize_followers.py",
        ]
        analyzer_script_path = next(
            (p for p in analyzer_candidates if os.path.exists(p)), None)

        # If running on Render or the script isn't available, queue a lightweight DB update instead
        if analyzer_script_path is None or os.name != 'nt':
            try:
                # Mark analysis as queued in users table so a local job can pick it up later
                conn = db_utils.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio_analysis_status TEXT")
                    conn.commit()
                except Exception:
                    pass
                cur.execute("UPDATE users SET bio_analysis_status = ? WHERE ig_username = ?",
                            ("queued", clean_username))
                conn.commit()
                conn.close()
                return True, "✅ Bio analysis queued. Run the local analyzer to process the queue."
            except Exception as e:
                logger.error(f"Queue fallback failed: {e}")
                return False, "❌ Analyzer script not available in this environment. Please run locally."

        # Step 5: Prepare command with explicit arguments for single user analysis
        cmd = [
            "python",
            analyzer_script_path,
            "--followers-list", temp_file_path,
            "--force",  # Force re-analysis even if user exists
            "--debug"   # Enable debug mode for better logging
        ]

        logger.info(f"Running Instagram analysis command: {' '.join(cmd)}")

        # Step 6: For single user analysis, run in visible mode with output capture
        try:
            # First, try to run with output capture for debugging
            result = subprocess.run(
                cmd,
                cwd=os.path.dirname(analyzer_script_path),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                encoding='utf-8'
            )

            # Log the output for debugging
            if result.stdout:
                logger.info(f"Analysis output: {result.stdout[:500]}...")
            if result.stderr:
                logger.error(f"Analysis errors: {result.stderr[:500]}...")

            if result.returncode == 0:
                # Clean up temp file on success
                try:
                    os.remove(temp_file_path)
                except:
                    pass
                return True, f"✅ Instagram analysis completed for {clean_username}"
            else:
                return False, f"❌ Analysis failed with code {result.returncode}. Check logs for details."

        except subprocess.TimeoutExpired:
            # If it times out, run in background mode
            logger.info(
                "Analysis taking longer than expected, running in background...")

            subprocess.Popen(
                cmd,
                cwd=os.path.dirname(analyzer_script_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                    subprocess, 'CREATE_NEW_CONSOLE') else 0
            )

            return True, f"✅ Instagram analysis started in background for {clean_username}. Check console window."

    except Exception as e:
        logger.error(
            f"Error triggering Instagram analysis for {ig_username}: {e}", exc_info=True)
        return False, f"❌ Error triggering analysis: {str(e)}"


def handle_simple_auto_response(review_item, edited_response, user_notes, manual_context):
    """
    NEW SIMPLIFIED AUTO RESPONSE HANDLER
    This calculates the delay ONCE and schedules it properly without recalculation issues.
    """
    try:
        from simple_auto_responder import add_auto_response, calculate_response_delay_minutes

        review_id = review_item['review_id']
        user_ig = review_item['user_ig_username']
        subscriber_id = review_item.get('user_subscriber_id', '')
        incoming_msg = review_item['incoming_message_text']
        incoming_timestamp = review_item['incoming_message_timestamp']

        logger.info(
            f"🚀 Simple Auto Response for {user_ig} (Review ID: {review_id})")

        # Check if already processed
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM pending_reviews WHERE review_id = ?", (review_id,))
        current_status = cursor.fetchone()

        if current_status and current_status[0] in ['auto_scheduled', 'sent', 'discarded']:
            st.warning(
                f"This response is already {current_status[0]} and cannot be re-scheduled.")
            conn.close()
            return False

        # Calculate delay ONCE based on user's response time
        delay_minutes = calculate_response_delay_minutes(
            incoming_timestamp, user_ig)

        # Add to simple auto responder queue
        success = add_auto_response(
            review_id=review_id,
            user_ig=user_ig,
            subscriber_id=subscriber_id,
            message_text=edited_response,
            incoming_msg=incoming_msg,
            incoming_timestamp=incoming_timestamp,
            delay_minutes=delay_minutes
        )

        if success:
            # Update review status
            db_utils.update_review_status(
                review_id, 'auto_scheduled', edited_response)

            # Calculate when it will send
            from datetime import datetime, timedelta
            send_time = datetime.now() + timedelta(minutes=delay_minutes)

            st.success(f"✅ Auto response scheduled for {user_ig}!")
            st.info(
                f"⏰ Will respond in {delay_minutes} minutes (at {send_time.strftime('%H:%M:%S')})")
            st.info(
                f"💡 Matching their response time - they took {delay_minutes} minutes to respond")

            # Remove from visible queue
            st.session_state.last_action_review_id = review_id
            st.rerun()
            return True
        else:
            st.error("❌ Failed to schedule auto response")
            return False

        conn.close()

    except Exception as e:
        logger.error(f"Error in simple auto response: {e}", exc_info=True)
        st.error(f"Error scheduling auto response: {str(e)}")
        return False


def test_instagram_analysis_debug(ig_username: str) -> str:
    """
    Debug version of Instagram analysis - runs synchronously with full output capture
    Use this to debug why the analysis might not be working
    """
    import subprocess
    import os
    import logging

    logger = logging.getLogger(__name__)

    try:
        clean_username = ig_username.strip()
        logger.info(
            f"🔍 DEBUG: Testing Instagram analysis for: {clean_username}")

        # Create debug temp file
        temp_dir = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\temp"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"debug_{clean_username}.txt")

        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(clean_username)

        # Run analysis with full debugging
        cmd = [
            "python",
            r"C:\Users\Shannon\OneDrive\Desktop\shanbot\anaylize_followers.py",
            "--followers-list", temp_file_path,
            "--force",
            "--debug",
            "--dry-run"  # Just show what would be processed
        ]

        logger.info(f"🔍 DEBUG: Running command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=r"C:\Users\Shannon\OneDrive\Desktop\shanbot",
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8'
        )

        debug_output = f"""
🔍 DEBUG RESULTS for {clean_username}:

📝 COMMAND: {' '.join(cmd)}

✅ STDOUT:
{result.stdout}

❌ STDERR:
{result.stderr}

📊 RETURN CODE: {result.returncode}

📁 TEMP FILE: {temp_file_path}
📄 TEMP FILE CONTENTS: {open(temp_file_path, 'r').read() if os.path.exists(temp_file_path) else 'File not found'}
        """

        logger.info(debug_output)

        # Clean up
        try:
            os.remove(temp_file_path)
        except:
            pass

        return debug_output

    except Exception as e:
        error_msg = f"❌ DEBUG ERROR: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


# --- New Function: Generate Offer Hook ---
def generate_offer_hook(user_ig: str, conversation_history: list) -> str:
    """
    Generates a call proposal or a message indicating inappropriate context.
    """
    logger.info(f"Attempting to generate Smart Offer for {user_ig}")

    # Format the conversation history for the AI prompt
    formatted_history = format_conversation_history(conversation_history)

    # --- Step 1: Check for inappropriate context (surgery, injury, crisis) ---
    context_check_prompt = f"""Analyze the following conversation history for keywords indicating the user is recovering from surgery, dealing with an injury, or going through a personal crisis (e.g., severe mental health struggles, major life event like job loss or bereavement).

Conversation History:
{formatted_history}

Is the context inappropriate for proposing a fitness consultation call (e.g., user is injured, post-surgery, or in crisis)?
If YES, explain why in a brief sentence. Start with "INAPPROPRIATE_CONTEXT - ".
If NO, respond with "APPROPRIATE_CONTEXT".
"""
    try:
        context_response = call_gemini_with_retry_sync(
            GEMINI_MODEL_FLASH,  # Use a faster model for context check
            context_check_prompt
        )
        if context_response and context_response.strip().startswith("INAPPROPRIATE_CONTEXT"):
            logger.info(
                f"Offer context deemed inappropriate for {user_ig}: {context_response.strip()}")
            return context_response.strip()
    except Exception as e:
        logger.error(
            f"Error during offer context check for {user_ig}: {e}", exc_info=True)
        # Fallback to general offer generation if context check fails
        pass

    # --- Step 2: Generate Call Proposal (if context is appropriate or check failed) ---
    offer_prompt = f"""
As Shannon, a friendly and knowledgeable Australian fitness coach, you're in the middle of a DM conversation. Your goal is to naturally transition from the chat into a call proposal based on the user's specific goals and struggles.

**Full Conversation History (for context of user's goals/struggles):**
{formatted_history}

**Your Task:**
Generate a response that feels like a direct and natural continuation of the user's LAST message, while also proposing a call to discuss their specific situation in detail.

**Rules for the Call Proposal:**
- Your reply MUST flow naturally from the user's last message. Don't just ignore what they said and jump to the call offer.
- Directly reference the prospect's specific goals or struggles mentioned in the conversation history.
- Keep it casual, friendly, and authentically Australian.
- Use the "Validate -> Provide Insight -> Ask" strategy.
- Reference specific details they've shared as the reason for the call.
- Frame the call as the logical next step based on their situation.
- End with a question asking if they're open to a call.

**Example Style:**
If the user just said "I'm struggling to find time to cook healthy meals", a good reply would be: "Thank you for sharing that. It's the classic plant-based trap; you're definitely not alone in this! We help you move from simply 'eating vegetarian' to strategically fueling your body. Given the details you've mentioned about your busy schedule and meal prep struggles, the absolute best way for me to see how I can truly help is to have a quick, no-pressure call. This goes way beyond what we can cover in text. Would you be open to that?"

Generate ONLY the call proposal message. Do not include any other text or formatting.
"""

    try:
        offer_hook_response = call_gemini_with_retry_sync(
            GEMINI_MODEL_PRO,  # Use the PRO model for offer generation
            offer_prompt
        )
        if offer_hook_response and offer_hook_response.strip():
            logger.info(
                f"Generated offer hook for {user_ig}: {offer_hook_response.strip()[:100]}...")
            return offer_hook_response.strip()
        else:
            logger.warning(f"Gemini returned empty offer hook for {user_ig}")
            return "AI generated an empty response for the offer hook."
    except Exception as e:
        logger.error(
            f"Error generating offer hook for {user_ig}: {e}", exc_info=True)
        return f"Error generating offer: {str(e)}"

# --- End New Function ---


def is_user_fresh_vegan(ig_username: str) -> bool:
    """
    Check if a user is marked as a fresh vegan contact in the conversation_strategy_log table.

    Args:
        ig_username: Instagram username to check

    Returns:
        bool: True if user is a fresh vegan contact, False otherwise
    """
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()

        # Check if user is marked as fresh vegan and still eligible (not trial/paying member)
        cursor.execute("""
            SELECT is_fresh_vegan 
            FROM conversation_strategy_log 
            WHERE username = ? AND is_fresh_vegan = 1
            LIMIT 1
        """, (ig_username,))

        result = cursor.fetchone()
        conn.close()

        return bool(result)

    except Exception as e:
        logger.error(
            f"Error checking fresh vegan status for {ig_username}: {e}", exc_info=True)
        return False


def should_auto_process_review(review_item: dict) -> bool:
    """
    Determine if a review should be auto-processed based on auto mode settings.

    Args:
        review_item: Review item dictionary containing user info

    Returns:
        bool: True if should auto-process, False if requires manual review
    """
    try:
        user_ig = review_item.get('user_ig_username', '')

        # Check general auto mode
        if is_auto_mode_active():
            logger.info(
                f"General auto mode active - auto-processing {user_ig}")
            return True

        # Check vegan auto mode
        if is_vegan_auto_mode_active():
            is_vegan = is_user_fresh_vegan(user_ig)
            if is_vegan:
                logger.info(
                    f"Vegan auto mode active - auto-processing fresh vegan {user_ig}")
                return True
            else:
                logger.info(
                    f"Vegan auto mode active but {user_ig} is not a fresh vegan - manual review required")
                return False

        # No auto mode active
        logger.info(f"No auto mode active - {user_ig} requires manual review")
        return False

    except Exception as e:
        logger.error(
            f"Error determining auto-process status for review: {e}", exc_info=True)
        return False


def handle_save_vegan_example(review_item, edited_response, user_notes):
    """Handle saving a response as a vegan few-shot example"""
    try:
        review_id = review_item['review_id']
        user_ig = review_item['user_ig_username']
        subscriber_id = review_item['user_subscriber_id']
        original_prompt = (
            review_item.get('generated_prompt_text')
            or review_item.get('generated_prompt')
            or review_item.get('generated_prompt_text_v1')
            or ''
        )
        original_response = review_item['proposed_response_text']

        # Save as vegan example
        success = db_utils.add_to_learning_log(
            review_id=review_id,
            user_ig_username=user_ig,
            user_subscriber_id=subscriber_id,
            original_prompt_text=original_prompt,
            original_gemini_response=original_response,
            edited_response_text=edited_response,
            user_notes=f"Saved as vegan example. {user_notes}".strip(),
            is_good_example_for_few_shot=True,
            conversation_type='vegan'
        )

        if success:
            st.success(f"✅ Saved as vegan few-shot example for {user_ig}!")
            st.toast("🌱 Vegan example saved!", icon="✅")
        else:
            st.error(f"❌ Failed to save vegan example for {user_ig}")

    except Exception as e:
        st.error(f"Error saving vegan example: {str(e)}")
        logger.error(f"Error saving vegan example: {e}", exc_info=True)


def save_few_shot_example(prompt_type: str, user_message: str, shannon_response: str, user_ig: str):
    """Save a few-shot example for the specified prompt type."""
    try:
        # Ensure table exists first
        ensure_few_shot_examples_table()

        conn = db_utils.get_db_connection()
        cursor = conn.cursor()

        # Insert the example
        cursor.execute("""
            INSERT INTO few_shot_examples (prompt_type, user_message, shannon_response, user_ig)
            VALUES (?, ?, ?, ?)
        """, (prompt_type, user_message, shannon_response, user_ig))

        conn.commit()
        conn.close()

        logger.info(
            f"✅ Saved few-shot example for {prompt_type} from user {user_ig}")
        return True, "Example saved successfully!"

    except Exception as e:
        logger.error(f"Error saving few-shot example: {e}")
        return False, f"Error saving example: {str(e)}"


def get_few_shot_examples_for_prompt_type(prompt_type: str) -> str:
    """Get few-shot examples for the specific prompt type from database."""
    try:
        # Ensure table exists first
        ensure_few_shot_examples_table()

        conn = db_utils.get_db_connection()
        cursor = conn.cursor()

        # Get recent examples for this prompt type, ordered by quality and usage
        cursor.execute("""
            SELECT user_message, shannon_response, user_ig, quality_score
            FROM few_shot_examples 
            WHERE prompt_type = ?
            ORDER BY quality_score DESC, usage_count DESC, created_timestamp DESC
            LIMIT 3
        """, (prompt_type,))

        examples = cursor.fetchall()
        conn.close()

        if not examples:
            # Return default examples if none found in database
            return get_default_few_shot_examples(prompt_type)

        # Format examples for prompt
        formatted_examples = []
        for user_msg, shannon_resp, user_ig, quality in examples:
            formatted_examples.append(f"""
**Example {prompt_type.replace('_', ' ').title()} (Quality: {quality}/10):**
User: "{user_msg}"
Shannon: "{shannon_resp}"
""")

        return "\n".join(formatted_examples)

    except Exception as e:
        logger.error(f"Error getting few-shot examples for {prompt_type}: {e}")
        return get_default_few_shot_examples(prompt_type)


def get_default_few_shot_examples(prompt_type: str) -> str:
    """Get default few-shot examples when none are in database."""
    if prompt_type == 'facebook_ad_response':
        return """
**Example Vegan Ad Response (Overview + Goal):**
User: "Can you tell me about the vegan challenge?"
Shannon: "Hey! Awesome that you're keen to know more. It's an online program to help you build strength, get leaner and feel amazing on a plant based diet. You get a personalized workout plan, a full vegan nutrition guide and weekly check ins for accountability. What's your main goal right now?"

**Example Vegan Ad Response (Perimenopause flow to call):**
User: "Can you tell me more about your ad?"
Shannon: "Awesome! The challenge is all about helping vegans dominate their fitness journey through focused nutrition and effective training. To see if it’s the right fit for you, what are you hoping to achieve with a fitness challenge?"
User: "I’ve been trying to lose weight the past couple of years but not having much luck with it 🙃… I think it may be because of perimenopause 😢"
Shannon: "Thanks for sharing that, I completely get it; it’s super common and very solvable with the right plan. The good news is our program is designed to help here with simple structure that actually fits real life. Have you noticed it affecting anything in particular like energy or cravings?"
User: "I’m pretty good energy wise and have a good mindset… no other symptoms yet just weight gain… occasionally I feel like a sweet treat but I try to choose healthier options."
Shannon: "Makes total sense. Given what you’ve told me about the weight gain, the best way for me to help is to have a quick call so I can tailor this properly. Would you be open to booking a call this week?"
User: "Ok 👍"
Shannon: "Awesome! Here’s the link: https://calendly.com/shannonrhysbirch/15min Grab any 15‑minute slot that works and let me know once you’ve booked so I can double check on my end."

**Example Vegan Ad Response (Gluten free + price handling):**
User: "Hello, I've just seen your story on IG....and I'll be interested...how does it work?! And of course I am vegan😉"
Shannon: "That's awesome! The challenge is an online program that includes a complete vegan meal plan, a structured workout program and ongoing support from me. To make sure it's the perfect fit, what's your main goal right now?"
User: "I'm trying to lose weight and gain strength. I just joined a gym; here’s my plan… (shares workouts). Also I am gluten free."
Shannon: "That's fantastic! Love the structure you’ve got. We’ll tailor your vegan nutrition to support those sessions and gluten free is no problem at all. I'd love to chat more and map this properly. Open to a quick call this week?"
User: "Yes, but how much is the program?"
Shannon: "Great question. I've got a few options and the best fit depends on you. Quickest way is a short call so I can match the right one for your goals and budget. Keen if I send the calendar link?"
User: "Yes ok"
Shannon: "Awesome! Here’s the link: https://calendly.com/shannonrhysbirch/15min Grab any 15‑minute slot that works and let me know once you’ve booked so I can double check on my end."

**Example Vegan Ad Response (Back pain, IVF, early vegan, call flow):**
User: "Hey. How will that work. I really struggle with my weight loss. Hope you could help 💜"
Shannon: "Hey, totally hear you. Weight loss can be tough especially getting started. What are you doing for exercise right now?"
User: "I have been very lazy lately. I used to workout five days a week till I hurt my back. IVF too. I can start straightaway. I'm 95kg and 5'8."
Shannon: "Completely understandable after all that. We’ll meet you where you’re at and build it back smart. How long have you been vegan and what changes did you make so far?"
User: "Vegetarian lifelong, vegan a few weeks. Added tofu, switched to almond/soy milk, more fruits and nuts."
Shannon: "That’s a great start. The program gives you a simple vegan structure that fits life and supports healthy weight loss without overwhelm. Given everything you’ve shared, best next step is a quick call so I can tailor it properly. Open to booking one this week?"
User: "Yes sure. Which day?"
Shannon: "Awesome! Here’s my calendar: https://calendly.com/shannonrhysbirch/15min Grab any 15‑minute slot and tell me once you’ve booked so I can double check."
"""
    elif prompt_type == 'member_chat':
        return """
**Example Member Chat:**
Member: "Done!!!"
Shannon: "Hell yeah!"
"""
    elif prompt_type == 'monday_morning_text':
        return """
**Example Monday Morning Check-in:**
Shannon: "Goooooood Morning! Ready for the week?"
"""
    elif prompt_type == 'checkins':
        return """
**Example Check-ins:**
Shannon: "Heya! Hows your week going?"
"""
    else:  # general_chat
        return """
**Example General Chat:**
User: "Hey Shannon!"
Shannon: "Hey! How's your day going?"
"""


def handle_save_example(review_item, edited_response, prompt_type):
    """Handle saving the current response as a few-shot example."""
    user_ig = review_item['user_ig_username']
    incoming_message = review_item['incoming_message_text']

    success, message = save_few_shot_example(
        prompt_type,
        incoming_message,
        edited_response,
        user_ig
    )

    if success:
        st.success(f"✅ {message}")
        st.toast(f"Saved example for {prompt_type}!", icon="💾")
    else:
        st.error(f"❌ {message}")


def display_few_shot_management(review_item, edited_response, selected_prompt_type, key_prefix):
    """Display few-shot example management interface."""
    st.write("**💾 Few-Shot Example Management:**")

    col_save, col_view, col_quality = st.columns([1, 1, 1])

    with col_save:
        if st.button("💾 Save as Example", key=f"{key_prefix}save_example", use_container_width=True):
            handle_save_example(
                review_item, edited_response, selected_prompt_type)

    with col_view:
        if st.button("👁️ View Examples", key=f"{key_prefix}view_examples", use_container_width=True):
            examples = get_few_shot_examples_for_prompt_type(
                selected_prompt_type)
            st.text_area("Current Examples:", examples, height=200,
                         key=f"{key_prefix}examples_display")

    with col_quality:
        quality_score = st.slider(
            "Quality Score", 1, 10, 5, key=f"{key_prefix}quality_score")
        if st.button("📊 Rate Example", key=f"{key_prefix}rate_example", use_container_width=True):
            # Update quality score in database
            try:
                conn = db_utils.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE few_shot_examples 
                    SET quality_score = ?
                    WHERE prompt_type = ? AND user_ig = ? AND shannon_response = ?
                    ORDER BY created_timestamp DESC
                    LIMIT 1
                """, (quality_score, selected_prompt_type, review_item['user_ig_username'], edited_response))
                conn.commit()
                conn.close()
                st.success(f"✅ Rated example as {quality_score}/10")
            except Exception as e:
                st.error(f"❌ Error rating example: {str(e)}")


def ensure_few_shot_examples_table():
    """Ensure the few_shot_examples table exists."""
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()

        # Create few_shot_examples table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS few_shot_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_type TEXT NOT NULL,
                user_message TEXT NOT NULL,
                shannon_response TEXT NOT NULL,
                user_ig TEXT NOT NULL,
                created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                quality_score INTEGER DEFAULT 5,
                usage_count INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()
        logger.info("✅ Few-shot examples table ensured")
        return True
    except Exception as e:
        logger.error(f"Error ensuring few_shot_examples table: {e}")
        return False
