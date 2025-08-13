import json
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta
import logging
import streamlit as st
# Keep Gemini import here as generate_ai_follow_up_message uses it
import google.generativeai as genai

# Import utilities from the new utils module
from .dashboard_utils import (
    call_gemini_with_retries,
    get_retry_delay,
    analyze_engagement_level,
    generate_follow_up_message  # Basic fallback message generator
)

# Set up logging
logger = logging.getLogger(__name__)

# Global variables - consider managing these via a config or state management later
SCHEDULED_FOLLOWUPS_FILE = "scheduled_followups.json"
SCHEDULED_FOLLOWUPS = {}  # In-memory cache
AUTO_FOLLOWUP_ENABLED = True  # Placeholder, manage state properly later

# Define constants for Gemini if not in utils
# Constants moved to dashboard_utils.py
# GEMINI_MODEL = "gemini-2.0-flash"
# GEMINI_FALLBACK_MODEL = "gemini-1.5-flash"
# MAX_API_RETRIES = 5
# BASE_RETRY_DELAY = 5

# --- Utility Functions (Moved from analytics_dashboard.py or duplicated temporarily) ---
# TODO: Move these to dashboard_utils.py and import them
# Functions get_retry_delay, call_gemini_with_retries, analyze_engagement_level,
# and generate_follow_up_message have been moved to dashboard_utils.py

# --- Core Follow-up Functions (Moved from analytics_dashboard.py) ---


def generate_ai_follow_up_message(conversation_data):
    """Generate a personalized follow-up message using Gemini AI."""
    try:
        # Get client name/username safely
        client_ig_username = conversation_data.get("ig_username")
        client_analysis = conversation_data.get("client_analysis", {})
        profile_bio = client_analysis.get("profile_bio", {})
        client_name = profile_bio.get("PERSON NAME") or profile_bio.get(
            "person_name") or client_ig_username or "there"

        history = conversation_data.get("conversation_history", [])
        history_text = "\n".join([f"{'Coach' if msg.get('type') == 'ai' else 'Client'}: {msg.get('text', '')}" for msg in history]
                                 ) if history else "No previous conversation history available."

        profile_info_text = "Client Profile Information:\n"
        interests = profile_bio.get(
            "INTERESTS") or profile_bio.get("interests") or []
        lifestyle = profile_bio.get(
            "LIFESTYLE") or profile_bio.get("lifestyle")
        personality = profile_bio.get("PERSONALITY TRAITS") or profile_bio.get(
            "personality_traits") or []
        if interests:
            profile_info_text += f"- Interests: {', '.join(interests)}\n"
        if lifestyle and lifestyle not in ["Unknown", ""]:
            profile_info_text += f"- Lifestyle: {lifestyle}\n"
        if personality:
            profile_info_text += f"- Personality Traits: {', '.join(personality)}\n"
        if profile_info_text == "Client Profile Information:\n":
            profile_info_text = "No detailed profile information available."

        prompt = f"""
        You are Shannon, a Fitness Coach engaging with followers on Instagram. Your goal is rapport and re-engagement.
        Create a follow-up message for {client_name} (IG: {client_ig_username}).

        Instructions:
        1. Review conversation history AND client profile.
        2. Formulate a simple, relevant follow-up question (5-25 words) based on BOTH.
        3. Reference past topics or profile interests/lifestyle. Acknowledge time passed.
        4. Dont include emojis
        5. Be personal, engaging. Reference specifics or introduce relevant new topics (e.g., giant lop bunnies if discussed bunnies, wave surfers if discussed surfing, Arny vs Cbum if bodybuilding, high-protein vegan dish if veganism).
        6. Start with a greeting like "Heya hows your week been? Been dancing?". Don't use "yeah right".
        7. Final output is ONLY the message text.
        8. IMPORTANT: DO NOT include the person's name or username. Use generic greetings like "Hey".

        Client Profile Information:
        {profile_info_text}

        Recent Conversation History:
        {history_text}

        Generate the follow-up message now:
        """

        # Use the imported utility function
        follow_up_message = call_gemini_with_retries(
            prompt=prompt, purpose="follow-up message")

        if not follow_up_message or len(follow_up_message.split()) > 30:
            logger.warning(
                f"AI message too long or empty for {client_ig_username}. Falling back. AI: '{follow_up_message}'")
            # Fallback to basic using imported function
            return generate_follow_up_message(conversation_data)

        logger.info(
            f"Generated AI follow-up for {client_ig_username}: '{follow_up_message}'")
        return follow_up_message

    except Exception as e:
        logger.error(
            f"Error generating AI follow-up for {conversation_data.get('ig_username', 'unknown')}: {e}", exc_info=True)
        # Fallback to regular follow-up message if generation fails
        return generate_follow_up_message(conversation_data)


def save_scheduled_followups():
    """Save scheduled follow-ups cache to the JSON file."""
    global SCHEDULED_FOLLOWUPS
    try:
        # Define path relative to this script's location or use an absolute path
        # For now, assume it's in the same directory as this script
        # Consider passing the path or using a config value
        # file_path = os.path.join(os.path.dirname(__file__), SCHEDULED_FOLLOWUPS_FILE)
        # Assumes it's in the current working directory of the process
        file_path = SCHEDULED_FOLLOWUPS_FILE

        serializable_followups = {}
        for username, messages in SCHEDULED_FOLLOWUPS.items():
            serializable_followups[username] = []
            for msg in messages:
                serializable_msg = msg.copy()
                for key in ["scheduled_time", "created_at", "sent_at", "last_attempt_at"]:
                    if key in serializable_msg and isinstance(serializable_msg[key], datetime):
                        serializable_msg[key] = serializable_msg[key].isoformat(
                        )
                serializable_followups[username].append(serializable_msg)

        with open(file_path, "w") as f:
            json.dump(serializable_followups, f, indent=2)
        logger.info(
            f"Saved {sum(len(msgs) for msgs in SCHEDULED_FOLLOWUPS.values())} scheduled followups to {file_path}")
    except Exception as e:
        logger.error(
            f"Error saving scheduled follow-ups to {SCHEDULED_FOLLOWUPS_FILE}: {e}", exc_info=True)


def load_scheduled_followups():
    """Load scheduled follow-ups from JSON file into cache."""
    global SCHEDULED_FOLLOWUPS
    # file_path = os.path.join(os.path.dirname(__file__), SCHEDULED_FOLLOWUPS_FILE)
    file_path = SCHEDULED_FOLLOWUPS_FILE  # Assumes current working directory
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                serialized_followups = json.load(f)

            loaded_followups = {}
            for username, messages in serialized_followups.items():
                loaded_followups[username] = []
                for msg in messages:
                    # Attempt to parse timestamps, handle potential errors
                    for key in ["scheduled_time", "created_at", "sent_at", "last_attempt_at"]:
                        if key in msg and isinstance(msg[key], str):
                            try:
                                # Ensure timezone awareness (assume UTC if not specified)
                                dt = datetime.fromisoformat(
                                    msg[key].replace('Z', '+00:00'))
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                msg[key] = dt
                            except ValueError:
                                logger.warning(
                                    f"Could not parse timestamp '{msg[key]}' for key '{key}' in user '{username}'. Keeping as string.")
                    loaded_followups[username].append(msg)
            SCHEDULED_FOLLOWUPS = loaded_followups
            logger.info(
                f"Loaded {sum(len(msgs) for msgs in SCHEDULED_FOLLOWUPS.values())} scheduled followups from {file_path}")
        else:
            SCHEDULED_FOLLOWUPS = {}
            logger.info(
                f"Scheduled follow-ups file not found ({file_path}). Initializing empty.")
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding JSON from {file_path}: {e}. Initializing empty.", exc_info=True)
        SCHEDULED_FOLLOWUPS = {}
    except Exception as e:
        logger.error(
            f"Error loading scheduled follow-ups from {file_path}: {e}. Initializing empty.", exc_info=True)
        SCHEDULED_FOLLOWUPS = {}


def schedule_automatic_followup(username, message, scheduled_time):
    """Schedule a follow-up message."""
    global SCHEDULED_FOLLOWUPS
    load_scheduled_followups()  # Ensure cache is loaded before adding

    if not isinstance(scheduled_time, datetime):
        logger.error(
            f"Invalid scheduled_time type for {username}: {type(scheduled_time)}")
        return False  # Or raise error

    # Ensure timezone
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    # Add a unique ID to each scheduled message for easier deletion/management
    followup_id = f"{username}_{int(time.time())}_{random.randint(1000,9999)}"

    SCHEDULED_FOLLOWUPS[username].append({
        "id": followup_id,
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": datetime.now(timezone.utc),
        "status": "scheduled"  # statuses: scheduled, sending, sent, failed, cancelled
    })
    logger.info(
        f"Scheduled followup for {username} at {scheduled_time} with ID {followup_id}")
    save_scheduled_followups()
    return True


def delete_scheduled_followup(username, followup_id):
    """Delete a specific scheduled follow-up by its ID."""
    global SCHEDULED_FOLLOWUPS
    load_scheduled_followups()  # Ensure cache is up-to-date

    if username in SCHEDULED_FOLLOWUPS:
        initial_length = len(SCHEDULED_FOLLOWUPS[username])
        # Filter out the message with the matching ID
        SCHEDULED_FOLLOWUPS[username] = [
            msg for msg in SCHEDULED_FOLLOWUPS[username] if msg.get("id") != followup_id
        ]

        if len(SCHEDULED_FOLLOWUPS[username]) < initial_length:
            logger.info(
                f"Deleted scheduled followup with ID {followup_id} for user {username}")
            save_scheduled_followups()
            return True
        else:
            logger.warning(
                f"Followup ID {followup_id} not found for user {username}")
            return False
    else:
        logger.warning(
            f"No scheduled followups found for user {username} to delete ID {followup_id}")
        return False


def process_scheduled_followups(max_to_send=10):
    """Check for due scheduled follow-ups and attempt to send them."""
    global SCHEDULED_FOLLOWUPS
    load_scheduled_followups()
    current_time = datetime.now(timezone.utc)
    messages_sent = 0
    messages_failed = 0
    messages_processed = 0

    messages_to_send = []
    usernames_processed_this_run = set()

    # Identify messages due to be sent
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        # Process only one message per user per run to avoid flooding
        if username in usernames_processed_this_run:
            continue

        for i, msg_data in enumerate(messages):
            # Check status and time
            if msg_data.get("status") == "scheduled":
                scheduled_time = msg_data.get("scheduled_time")
                # Ensure scheduled_time is a datetime object before comparing
                if isinstance(scheduled_time, datetime) and scheduled_time <= current_time:
                    messages_to_send.append(
                        {"username": username, "index": i, "data": msg_data})
                    usernames_processed_this_run.add(username)
                    break  # Move to next user after finding one due message

    logger.info(
        f"Found {len(messages_to_send)} scheduled messages due. Processing up to {max_to_send}.")

    # --- Placeholder for Selenium/Instagram Interaction ---
    # In a real scenario, you'd setup the driver ONCE here if possible
    # This requires access to the existing `followup_manager.py` or similar selenium control module
    # driver = get_selenium_driver() # Function to get/initialize Selenium driver
    # if not driver:
    #    logger.error("Selenium driver not available for sending followups.")
    #    # Mark all due messages as failed or handle error
    #    return {"sent": 0, "failed": len(messages_to_send), "processed": 0}
    # --------------------------------------------------

    # Process the identified messages up to the limit
    for item in messages_to_send[:max_to_send]:
        username = item["username"]
        index = item["index"]
        msg_data = item["data"]

        # Mark as sending to prevent reprocessing if script restarts
        SCHEDULED_FOLLOWUPS[username][index]["status"] = "sending"
        SCHEDULED_FOLLOWUPS[username][index]["last_attempt_at"] = datetime.now(
            timezone.utc)
        save_scheduled_followups()  # Save intermediate state

        try:
            logger.info(
                f"Attempting to send scheduled message ID {msg_data.get('id')} to {username}")

            # --- Replace with actual sending logic using your existing followup_manager ---
            # This assumes you have a function `send_instagram_message` in your actual followup_manager
            # import followup_manager # Or however you access it
            # driver = followup_manager.get_driver() # Get the initialized driver
            # if driver:
            #     result = followup_manager.send_follow_up_message(driver, username, msg_data["message"])
            # else:
            #     result = {"success": False, "error": "Selenium driver not ready"}

            # Mock result for now:
            time.sleep(random.uniform(1, 3))  # Simulate network delay
            # Simulate potential failure
            success = random.choice([True, True, False])
            result = {"success": success,
                      "error": "Simulated network error" if not success else None}
            # -----------------------------------------

            if result.get("success", False):
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "sent"
                SCHEDULED_FOLLOWUPS[username][index]["sent_at"] = datetime.now(
                    timezone.utc)
                messages_sent += 1
                log_followup_success(username, msg_data["message"], msg_data.get(
                    'id', 'N/A'))  # Pass ID if available
                logger.info(
                    f"Successfully sent scheduled message ID {msg_data.get('id')} to {username}")
            else:
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
                SCHEDULED_FOLLOWUPS[username][index]["error"] = result.get(
                    "error", "Unknown error")
                messages_failed += 1
                log_followup_failure(username, result.get(
                    "error", "Unknown error"), msg_data.get('id', 'N/A'))  # Pass ID
                logger.error(
                    f"Failed to send scheduled message ID {msg_data.get('id')} to {username}: {result.get('error')}")

        except Exception as e:
            SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
            SCHEDULED_FOLLOWUPS[username][index]["error"] = str(e)
            messages_failed += 1
            log_followup_failure(username, str(
                e), msg_data.get('id', 'N/A'))  # Pass ID
            # Log full traceback
            logger.exception(
                f"Exception sending scheduled message ID {msg_data.get('id')} to {username}")

        messages_processed += 1
        save_scheduled_followups()  # Save status after each attempt

    # --- Placeholder for closing driver if managed here ---
    # if driver:
    #     close_driver(driver)

    logger.info(
        f"Scheduled followup processing complete. Processed: {messages_processed}, Sent: {messages_sent}, Failed: {messages_failed}")
    return {"sent": messages_sent, "failed": messages_failed, "processed": messages_processed}


def log_followup_success(username, message, followup_id="N/A"):
    """Log a successful follow-up message (placeholder)."""
    # In a real app, this would update the main analytics data or a separate log
    logger.info(
        f"SUCCESSFUL_FOLLOWUP Logged: User='{username}', ID='{followup_id}', Message='{message[:50]}...'")
    # TODO: Integrate with actual analytics saving (e.g., call analytics.log_event(...))


def log_followup_failure(username, error, followup_id="N/A"):
    """Log a failed follow-up message (placeholder)."""
    # In a real app, this would update the main analytics data or a separate log
    logger.error(
        f"FAILED_FOLLOWUP Logged: User='{username}', ID='{followup_id}', Error='{error}'")
    # TODO: Integrate with actual analytics saving


def toggle_auto_followup(enabled, username=None):
    """Enable or disable automatic follow-up (basic global toggle)."""
    global AUTO_FOLLOWUP_ENABLED
    # TODO: Implement proper state management (e.g., using Streamlit session state or config file)
    if username is None:
        AUTO_FOLLOWUP_ENABLED = enabled
        logger.info(f"Automatic follow-up globally set to: {enabled}")
        return True
    else:
        # Per-user toggle not implemented in this basic version
        logger.warning("Per-user auto-followup toggle not implemented.")
        return False

# --- UI Components (Placeholders - to be moved/integrated into Streamlit pages) ---


def display_scheduled_followups_ui():
    """Placeholder function for Streamlit UI to display/manage scheduled followups."""
    st.subheader("Current Scheduled Follow-ups")
    load_scheduled_followups()  # Make sure we have the latest data

    if not SCHEDULED_FOLLOWUPS:
        st.info("No follow-ups currently scheduled.")
        return

    num_scheduled = 0
    # Create a list of users with scheduled/failed messages for tabs
    users_with_messages = sorted([
        username for username, msgs in SCHEDULED_FOLLOWUPS.items() if msgs
    ])

    if not users_with_messages:
        st.info("No follow-ups currently scheduled.")
        return

    user_tabs = st.tabs(users_with_messages)

    for i, username in enumerate(users_with_messages):
        with user_tabs[i]:
            st.write(f"Follow-ups for: **{username}**")
            # Ensure messages are sorted, e.g., by scheduled time
            user_followups = sorted(SCHEDULED_FOLLOWUPS[username], key=lambda x: x.get(
                'scheduled_time', datetime.max.replace(tzinfo=timezone.utc)))

            num_scheduled += len(
                [msg for msg in user_followups if msg.get('status') == 'scheduled'])

            # Display each message with details and delete button
            for msg_data in user_followups:
                # Generate temp ID if missing
                followup_id = msg_data.get(
                    "id", f"N/A_{random.randint(1000,9999)}")
                status = msg_data.get("status", "unknown")
                scheduled_time = msg_data.get("scheduled_time", "N/A")
                created_at = msg_data.get("created_at", "N/A")
                message_preview = msg_data.get("message", "")[:60] + "..."

                # Format times nicely
                scheduled_time_str = scheduled_time.strftime(
                    "%Y-%m-%d %H:%M") if isinstance(scheduled_time, datetime) else str(scheduled_time)
                created_at_str = created_at.strftime(
                    "%Y-%m-%d %H:%M") if isinstance(created_at, datetime) else str(created_at)

                # Use columns for better layout
                cols = st.columns([3, 1.5, 1.5, 1])

                with cols[0]:
                    st.text_area(f"Msg (ID: {followup_id})", value=message_preview,
                                 height=50, disabled=True, key=f"msg_preview_{followup_id}")
                with cols[1]:
                    st.markdown(f"**Status:** {status.capitalize()}")
                    st.caption(f"Sched: {scheduled_time_str}")
                with cols[2]:
                    if msg_data.get("sent_at"):
                        sent_at_str = msg_data["sent_at"].strftime(
                            "%Y-%m-%d %H:%M") if isinstance(msg_data["sent_at"], datetime) else str(msg_data["sent_at"])
                        st.caption(f"Sent: {sent_at_str}")
                    elif msg_data.get("last_attempt_at"):
                        last_attempt_str = msg_data["last_attempt_at"].strftime("%Y-%m-%d %H:%M") if isinstance(
                            msg_data["last_attempt_at"], datetime) else str(msg_data["last_attempt_at"])
                        st.caption(f"Attempt: {last_attempt_str}")
                    else:
                        st.caption(f"Created: {created_at_str}")

                    if msg_data.get("error"):
                        # Show snippet of error
                        st.error(f"{msg_data['error'][:50]}...")

                with cols[3]:
                    # Only show delete for 'scheduled' or 'failed' statuses
                    if status in ["scheduled", "failed"]:
                        if st.button("Delete", key=f"delete_{followup_id}", help="Remove this scheduled follow-up"):
                            if delete_scheduled_followup(username, followup_id):
                                st.success(f"Deleted follow-up {followup_id}")
                                time.sleep(0.5)  # Brief pause before rerun
                                st.rerun()
                            else:
                                st.error(
                                    f"Failed to delete follow-up {followup_id}")

                # Separator between messages
                st.markdown("---", unsafe_allow_html=True)

    # Display summary counts if needed
    # st.sidebar.metric("Total Scheduled", num_scheduled)


# --- Initialization ---
# Load followups when the module is imported for immediate use
# load_scheduled_followups()
# Or manage state externally and load when needed
