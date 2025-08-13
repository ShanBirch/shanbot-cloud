import random
import time
import logging
import os
from datetime import datetime, timedelta, timezone
import google.generativeai as genai

# Set up logging for utilities
logger = logging.getLogger(__name__)

# Define constants for Gemini (can be moved to a config file later)
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_FALLBACK_MODEL = "gemini-1.5-flash"
MAX_API_RETRIES = 5
BASE_RETRY_DELAY = 5
ACTIVE_WINDOW = 3600  # 1 hour in seconds (Moved from analytics_dashboard)

# --- Timestamp and Timezone Utilities (from analytics_dashboard.py) ---


def ensure_timezone(dt):
    """Ensure a datetime object has timezone information (defaults to UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # logger.debug("Timestamp had no timezone, assuming UTC.")
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_timestamp(timestamp_str):
    """Parse timestamp string (ISO format with optional Z) to timezone-aware datetime (UTC)."""
    if not timestamp_str or not isinstance(timestamp_str, str):
        # logger.warning(f"Invalid timestamp input type or empty: {timestamp_str}")
        return None
    try:
        # Handle potential floating point seconds from older formats if needed
        # This primarily handles ISO 8601 format, common in JSON
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return ensure_timezone(dt)  # Ensure it's timezone-aware
    except ValueError:
        # Add other parsing attempts if needed, e.g., specific formats
        # logger.warning(f"Could not parse timestamp: {timestamp_str}", exc_info=True)
        try:  # Attempt parsing format seen in should_follow_up debug
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
            return ensure_timezone(dt)
        except ValueError:
            logger.error(f"Failed to parse timestamp string: {timestamp_str}")
            return None
    except TypeError as e:
        logger.error(f"TypeError parsing timestamp '{timestamp_str}': {e}")
        return None


def is_user_active(last_active_time):
    """Check if a user is active based on their last active time within ACTIVE_WINDOW."""
    if not last_active_time:
        return False

    now_utc = datetime.now(timezone.utc)
    last_active_dt = parse_timestamp(last_active_time)

    if not last_active_dt:
        # logger.warning(f"Could not determine user activity due to unparseable last_active_time: {last_active_time}")
        return False

    time_diff = now_utc - last_active_dt
    is_active = time_diff.total_seconds() < ACTIVE_WINDOW
    # logger.debug(f"User activity check: last_active={last_active_dt}, now={now_utc}, diff_seconds={time_diff.total_seconds()}, active={is_active}")
    return is_active

# --- Follow-up Logic Utilities (from analytics_dashboard.py) ---


def should_follow_up(conversation_data):
    """Determine if we should follow up based on conversation state (basic 2-day rule)."""
    # Consider replacing this with get_smart_follow_up_timing for more nuanced logic
    conv_metrics = conversation_data.get('metrics', {})
    last_message_time = conv_metrics.get(
        'last_message_time')  # Check this key usage
    if not last_message_time:
        logger.warning(
            "'last_message_time' not found in metrics for should_follow_up check.")
        return False

    last_dt = parse_timestamp(last_message_time)
    if not last_dt:
        logger.warning(
            f"Could not parse last_message_time '{last_message_time}' for should_follow_up check.")
        return False

    now_utc = datetime.now(timezone.utc)
    time_diff = now_utc - last_dt

    # Debug logging
    # logger.debug(f"DEBUG - ID: {conversation_data.get('id', 'unknown')}, Last Message: {last_dt}, Diff: {time_diff}, Follow-up needed (>=2 days): {time_diff.days >= 2}")

    # If no message for 2 days, suggest follow-up
    return time_diff.days >= 2


def analyze_engagement_level(metrics):
    """Analyze the engagement level of a conversation based on various factors."""
    # This version comes from analytics_dashboard.py
    score = 0
    factors = []

    # Use precise keys from analytics data if available
    # Prefer specific count if available
    user_messages = metrics.get("user_messages", 0)

    if user_messages >= 5:  # Use threshold from original function
        score += 3
        factors.append("High user message count (>=5)")
    elif user_messages >= 3:
        score += 2
        factors.append("Moderate user message count (3-4)")
    elif user_messages >= 1:
        score += 1
        factors.append("Low user message count (1-2)")

    # Example: Add more factors based on available metrics
    # if metrics.get("user_responses_to_questions", 0) > 0:
    #     score += 2
    #     factors.append("Responded to questions")
    # if metrics.get("fitness_topic_user_initiated", False):
    #     score += 3
    #     factors.append("User initiated fitness talk")
    # elif metrics.get("fitness_topic_mentioned", False): # Check generic mention too
    #     score += 1
    #     factors.append("Responded to/Mentioned fitness topic")

    # Determine level based on score
    if score >= 5:  # Adjusted threshold based on current simple scoring
        engagement_level = "HIGH"
    elif score >= 3:
        engagement_level = "MEDIUM"
    else:
        engagement_level = "LOW"

    logger.debug(
        f"Engagement Analysis: Score={score}, Level={engagement_level}, Factors={factors}")
    return {
        "score": score,
        "level": engagement_level,
        "factors": factors
    }


def get_smart_follow_up_timing(conversation_data):
    """Determine optimal follow-up timing based on engagement (basic version)."""
    # This is a simplified placeholder. The original had more complex logic involving
    # last_seen_timestamp, specific days_after_end, window_hours, etc.
    # This needs to be reconciled with the logic in the 'Scheduled Follow-ups' tab

    # Allow passing metrics directly or full data
    metrics = conversation_data.get("metrics", conversation_data)
    if not metrics:
        logger.warning("No metrics found for smart follow-up timing.")
        return False, None, "No metrics"

    # Analyze engagement
    engagement = analyze_engagement_level(metrics)
    engagement_level = engagement.get('level', 'LOW')

    # Basic timing rules based on engagement
    if engagement_level == "HIGH":
        days_to_wait = 2
        reason = "High engagement"
    elif engagement_level == "MEDIUM":
        days_to_wait = 4  # Adjusted example
        reason = "Medium engagement"
    else:  # LOW
        days_to_wait = 7  # Adjusted example
        reason = "Low engagement"

    # Determine if follow-up is needed based on last interaction time
    # Need a reliable timestamp for last interaction (e.g., last_message_timestamp)
    last_interaction_time = metrics.get("last_message_timestamp")
    if not last_interaction_time:
        logger.warning(
            "Missing 'last_message_timestamp' for smart follow-up timing.")
        return False, None, "Missing last interaction time"

    last_dt = parse_timestamp(last_interaction_time)
    if not last_dt:
        logger.warning(
            f"Could not parse last_interaction_time '{last_interaction_time}'")
        return False, None, "Invalid last interaction time"

    now_utc = datetime.now(timezone.utc)
    time_diff = now_utc - last_dt

    should_follow = time_diff.days >= days_to_wait
    calculated_follow_up_time = last_dt + timedelta(days=days_to_wait)

    logger.debug(
        f"Smart Timing: Level={engagement_level}, Wait={days_to_wait}d, LastActive={last_dt}, FollowUpDue={should_follow}, DueDate={calculated_follow_up_time}")

    # Return: Should follow up (bool), Estimated due date (datetime), Reason (str)
    return should_follow, calculated_follow_up_time, reason


def generate_follow_up_message(conversation_data):
    """Generate a casual, friendly follow-up message based on previous conversations."""
    # This is the basic version from analytics_dashboard.py
    conv_metrics = conversation_data.get('metrics', {})
    conv_metadata = conversation_data.get('metadata', {})
    user_name = conversation_data.get(
        'ig_username') or conv_metadata.get('user_name', 'there')

    # Basic template
    follow_up_message = f"Hey {user_name}! How's it going? Just checking in to see how you're doing."

    # TODO: Enhance with more context if available from conv_metadata or metrics
    # Example from original:
    # if 'topic_interests' in conv_metadata:
    #     interests = conv_metadata.get('topic_interests', [])
    #     if 'meal_plan' in interests:
    #         follow_up_message = f"Hey {user_name}! How's your meal plan going? Keeping it clean? 🥗 Still crushing it?"
    #     elif 'workout' in interests:
    #         follow_up_message = f"Hey {user_name}! How's your training going this week? Getting those gains? 💪"

    logger.debug(
        f"Generated basic follow-up for {user_name}: '{follow_up_message}'")
    return follow_up_message


# --- Gemini API Utilities (from followup_service.py) ---

def get_retry_delay(attempt):
    """Calculate exponential backoff delay with jitter."""
    exponential_delay = BASE_RETRY_DELAY * (2 ** attempt)
    jitter = random.uniform(0, 0.3 * exponential_delay)
    return exponential_delay + jitter


def call_gemini_with_retries(prompt, primary_model=GEMINI_MODEL, fallback_model=GEMINI_FALLBACK_MODEL, purpose="general"):
    """Make Gemini API calls with smart retries and fallbacks"""
    # Ensure API key is configured (consider moving configuration elsewhere)
    try:
        # Attempt to get API key from common sources if not already configured
        if not getattr(genai, 'api_key', None):
            # Check environment variable
            api_key = os.environ.get("GEMINI_API_KEY")
            # if not api_key and 'st' in globals(): # Check Streamlit secrets if available
            #    api_key = st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                # Fallback - THIS IS NOT RECOMMENDED FOR PRODUCTION
                # Replace with your actual key or secure method
                api_key = "AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y"
                logger.warning(
                    "Using hardcoded Gemini API key fallback. Configure securely.")

            if api_key:
                genai.configure(api_key=api_key)
            else:
                logger.error("Gemini API key not found.")
                return None  # Cannot proceed without API key

    except Exception as e:
        logger.error(f"Gemini API key configuration error: {e}")
        return None

    for attempt in range(MAX_API_RETRIES):
        try:
            model_name = primary_model if attempt < 2 else fallback_model
            logger.info(
                f"Using model {model_name} for {purpose} (attempt {attempt+1})")

            model = genai.GenerativeModel(model_name=model_name)
            # Add safety settings if needed
            # safety_settings = {...}
            # , safety_settings=safety_settings)
            response = model.generate_content(prompt)
            result = response.text.strip()

            logger.info(
                f"Successfully generated content for {purpose} (attempt {attempt+1})")
            return result

        except Exception as e:
            error_msg = str(e)
            logger.warning(
                f"Error on attempt {attempt+1}/{MAX_API_RETRIES} for {purpose}: {error_msg}")

            is_quota_error = "quota" in error_msg.lower(
            ) or "429" in error_msg or "limit" in error_msg.lower()

            if attempt < MAX_API_RETRIES - 1:
                delay = get_retry_delay(
                    attempt) if is_quota_error else BASE_RETRY_DELAY
                logger.info(
                    f"{'Quota' if is_quota_error else 'Non-quota'} error detected, waiting {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                logger.error(
                    f"All {MAX_API_RETRIES} retry attempts failed for {purpose}. Last error: {error_msg}")

    return None  # Return None if all retries fail
