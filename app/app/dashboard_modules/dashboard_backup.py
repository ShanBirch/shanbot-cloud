import streamlit as st
import json
import logging
import os
from pathlib import Path
import datetime
import google.generativeai as genai
import random
import google.oauth2.service_account
import googleapiclient.discovery
import time

# Import the new SQLite utility functions
from dashboard_sqlite_utils import (
    load_conversations_from_sqlite,
    save_metrics_to_sqlite,
    get_pending_reviews,
    update_review_status,
    add_to_learning_log,
    add_message_to_history,
    get_review_accuracy_stats,
    insert_manual_context_message
)

# Import the actual ManyChat update function
try:
    from webhook_handlers import update_manychat_fields
except ImportError:
    try:
        # Try from the parent directory
        import sys
        import os
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        sys.path.insert(0, parent_dir)
        from webhook0605 import update_manychat_fields
    except ImportError:
        st.error("Could not import update_manychat_fields function")
        update_manychat_fields = None

# Import the message splitting function
from webhook_handlers import split_response_into_messages

# Use direct imports since files are in the same directory
# Assuming overview.py is in the same dir
from overview import display_overview
# Assuming client_journey.py is in the same dir
from client_journey import display_client_journey
# Assuming user_profiles.py is in the same dir
from user_profiles import display_user_profiles, display_user_profile, get_usernames
from scheduled_followups import (
    display_scheduled_followups,
    display_bulk_review_and_send,
    bulk_generate_followups,
    get_user_category,
    get_topic_for_category,
    verify_trial_signup,
    check_sheet_for_signups,
    get_user_sheet_details as get_checkin_data
)

# Path for action_items JSON file - keep this as it's separate for now
ACTION_ITEMS_JSON_FILE = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.json"
# Path for Google Sheets credentials (remains the same)
SHEETS_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(__file__), "sheets_credentials.json")  # Corrected path if sheets_credentials.json is in dashboard_modules

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets configuration (remains the same)
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"


def check_and_update_signups(data: dict) -> dict:
    """Check for new signups and update user stages accordingly."""
    data_updated = False  # This flag might be less relevant if saves happen per user

    # The 'data' dict now primarily comes from SQLite via load_analytics_data
    # and 'conversations' is the key holding the SQLite loaded data.
    if 'conversations' not in data:
        logger.error(
            "'conversations' key missing from data in check_and_update_signups. Cannot proceed.")
        return data, False

    for username, user_container in data.get('conversations', {}).items():
        # User data is now directly under username, not nested in 'metrics' in the same way as JSON
        # metrics is the direct user data dict from SQLite load
        metrics = user_container.get('metrics', {})
        if not metrics:
            logger.warning(
                f"No metrics found for user {username} in check_and_update_signups")
            continue

        ig_username = metrics.get('ig_username')

        # Journey stage logic might need to be adapted if journey_stage is a dict
        current_journey_stage = metrics.get('journey_stage', {})
        if not isinstance(current_journey_stage, dict):
            current_journey_stage = {}  # Default to dict if not already

        # Skip if already in trial or paying stage
        if current_journey_stage.get('is_paying_client') or current_journey_stage.get('trial_start_date'):
            continue

        # Check if user has signed up
        # verify_trial_signup likely needs to check Google Sheets
        if ig_username and verify_trial_signup(ig_username):
            logger.info(
                f"Found signup for {ig_username}, updating to Trial Week 1")
            # Update journey_stage directly
            current_journey_stage['trial_start_date'] = datetime.datetime.now(
            ).isoformat()  # Example: set trial start
            # Update current stage
            current_journey_stage['current_stage'] = 'Trial Week 1'
            # Assign back to metrics
            metrics['journey_stage'] = current_journey_stage

            # Save this specific user's updated metrics to SQLite
            if save_metrics_to_sqlite(ig_username, metrics):
                logger.info(
                    f"Successfully saved updated journey_stage for {ig_username} to SQLite.")
                data_updated = True  # Indicate that at least one user was updated
            else:
                logger.error(
                    f"Failed to save updated journey_stage for {ig_username} to SQLite.")

    return data, data_updated


def load_analytics_data():
    """Load analytics data: conversations from SQLite, action_items from JSON."""
    logger.info("Starting to load analytics data...")
    data = {}
    analytics_file_path_for_actions = ACTION_ITEMS_JSON_FILE  # For action_items

    # 1. Load conversations from SQLite
    try:
        conversations_from_sqlite = load_conversations_from_sqlite()
        # This is already in the desired format
        data['conversations'] = conversations_from_sqlite
        logger.info(
            f"Successfully loaded {len(conversations_from_sqlite)} conversations from SQLite.")
        if conversations_from_sqlite:
            sample_user = next(iter(conversations_from_sqlite))
            logger.info(
                f"Sample SQLite user data structure for '{sample_user}': {json.dumps(conversations_from_sqlite[sample_user].get('metrics', {}), indent=2, default=str)}")

    except Exception as e:
        logger.error(
            f"Error loading conversations from SQLite: {e}", exc_info=True)
        st.error(f"Error loading conversation data from SQLite: {e}")
        data['conversations'] = {}  # Ensure it's an empty dict on error

    # 2. Load action_items from JSON file
    try:
        if os.path.exists(analytics_file_path_for_actions):
            with open(analytics_file_path_for_actions, 'r', encoding='utf-8') as f:
                json_data_content = json.load(f)
                data['action_items'] = json_data_content.get(
                    'action_items', [])
            logger.info(
                f"Successfully loaded {len(data.get('action_items',[]))} action items from JSON: {analytics_file_path_for_actions}")
        else:
            logger.warning(
                f"Action items JSON file not found at {analytics_file_path_for_actions}. Initializing with empty list.")
            data['action_items'] = []
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding JSON from {analytics_file_path_for_actions}: {e}")
        st.error(f"Error loading action items from JSON: {e}")
        data['action_items'] = []
    except Exception as e:
        logger.error(
            f"Unexpected error loading action items from {analytics_file_path_for_actions}: {e}", exc_info=True)
        data['action_items'] = []

    # For compatibility, the dashboard might expect analytics_file path for saving JSON later.
    # It might be better to handle JSON saving separately if only action_items go there.
    return data, analytics_file_path_for_actions  # Return path for JSON for now


# Configure Gemini (remains the same)
GEMINI_API_KEY = "AIzaSyCrYZwENVEhfo0IF6puWyQaYlFW1VRWY-k"
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(
            'gemini-2.0-flash')  # Or your preferred model
        logger.info("Gemini configured successfully.")
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}")
        gemini_model = None
        st.error("Failed to configure Gemini AI. Some features might not work.")
else:
    logger.warning(
        "Gemini API Key not found or is a placeholder. AI features will be disabled.")
    gemini_model = None
    st.info("Gemini API Key not configured. AI features disabled.")

# Add a session state for message queue (remains the same)
if 'message_queue' not in st.session_state:
    st.session_state.message_queue = []

# Add session state for last signup check (remains the same)
if 'last_signup_check' not in st.session_state:
    st.session_state.last_signup_check = None


def get_response_category_color(num_responses):
    """Return color and emoji indicator based on number of responses"""
    if num_responses >= 20:
        return "🟢"  # Green circle for high responders
    elif num_responses >= 11:
        return "🟡"  # Yellow circle for medium responders
    elif num_responses >= 1:
        return "🟠"  # Orange circle for low responders
    else:
        return "🔴"  # Red circle for no response


def generate_follow_up_message(conversation_history, topic):
    """Generate a follow-up message using Gemini"""
    if not gemini_model:
        st.error("Gemini model not available. Cannot generate message.")
        return "[Gemini not available]"
    try:
        # Format conversation history
        formatted_history = ""
        for msg in conversation_history:  # conversation_history should be a list of dicts
            sender = "User" if msg.get('type') == 'user' else "Shannon"
            formatted_history += f"{sender}: {msg.get('text', '')}\n"

        prompt = f"""
        Previous conversation history:
        {formatted_history}

        Current conversation topic to discuss:
        {topic}

        Create a casual, friendly opener message to restart the conversation about this topic.
        Keep it simple and engaging, like this example:
        Topic: Discuss their favorite plant-based protein sources
        Message: "yo dam im running dry on protein sources for a veggie diet, whats your diet looking like? any high protein secrets for me? :)"

        Rules:
        - Don't use their Instagram username
        - Keep it casual and conversational
        - Make it feel natural and not scripted
        - Include a question to encourage response
        - Keep it short (1-2 sentences max)
        - Don't reference previous conversations directly

        Generate ONLY the message, no other text:
        """

        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Error generating message: {e}")
        logger.error(f"Gemini message generation error: {e}", exc_info=True)
        return None


def get_stage_topics(stage_number):
    """Get conversation topics for a specific stage"""
    stage_topics = {
        1: ["Topic 1 - Discuss their favorite plant-based protein sources for muscle growth and any creative vegetarian recipes they've discovered recently."],
        2: ["Topic 2 - Explore their approach to tracking progress with clients, specifically what metrics they prioritize beyond just weight loss and how they use fitness apps."],
        3: ["Topic 3 - Talk about their experience adapting resistance training techniques for clients with different fitness levels and what common mistakes they see people make."],
        4: ["Topic 4 - Share tips on incorporating high-protein vegetarian meals into a busy schedule and how they advise clients to make healthy eating more convenient in Melbourne."],
        5: ["Topic 5 - Enquire about leads fitness journey - offer 1 month trial"],
        6: ["Trial Week 1 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 1 - Wednesday Night: Heya! Hows your week going?"],
        7: ["Trial Week 2 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 2 - Wednesday Night: Heya! Hows your week going?"],
        8: ["Trial Week 3 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 3 - Wednesday Night: Heya! Hows your week going?"],
        9: ["Trial Week 4 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 4 - Wednesday Night: Heya! Hows your week going?"],
        10: ["Paying Client - Monday Morning: Goooooood Morning! Ready for the week?",
             "Paying Client - Wednesday Night: Heya! Hows your week going?"]
    }
    return stage_topics.get(stage_number, [])


def get_stage_metrics(data):
    """Calculate metrics for each stage of the client journey from loaded data."""
    try:
        # 'data' is the overall dict; 'conversations' holds the user data loaded from SQLite
        conversations_data = data.get('conversations', {})
        if not conversations_data:
            logger.warning(
                "No conversations data available to calculate stage metrics.")
            return {
                'total_users': 0, 'engaged_users': 0, 'analyzed_profiles': 0,
                'total_messages': 0, 'response_rate': 0, 'avg_messages': 0,
                'avg_posts_per_profile': 0
            }

        metrics_summary = {
            'total_users': len(conversations_data),
            'engaged_users': 0,
            'analyzed_profiles': 0,
            'total_messages': 0,
            'response_rate': 0,
            'avg_messages': 0
        }

        analyzed_user_count = 0
        total_analyzed_posts_sum = 0

        for username, user_container in conversations_data.items():
            # User data is now directly under username (user_container)
            # This is the dict loaded from users table
            user_metrics_data = user_container.get('metrics', {})
            if not user_metrics_data:
                logger.warning(
                    f"No metrics found for user {username} when calculating stage metrics.")
                continue

            # client_analysis is expected to be a dict within user_metrics_data
            client_analysis_data = user_metrics_data.get('client_analysis', {})
            if not isinstance(client_analysis_data, dict):
                client_analysis_data = {}

            # Count analyzed profiles
            if client_analysis_data and client_analysis_data.get('posts_analyzed', 0) > 0:
                analyzed_user_count += 1
                total_analyzed_posts_sum += client_analysis_data.get(
                    'posts_analyzed', 0)

            # Count engaged users (those with responses)
            # 'user_messages' and 'total_messages' are now calculated during SQLite load
            if user_metrics_data.get('user_messages', 0) > 0:
                metrics_summary['engaged_users'] += 1
            metrics_summary['total_messages'] += user_metrics_data.get(
                'total_messages', 0)

        # Calculate averages
        if metrics_summary['engaged_users'] > 0:
            metrics_summary['avg_messages'] = metrics_summary['total_messages'] / \
                metrics_summary['engaged_users']
        if metrics_summary['total_users'] > 0:  # Avoid division by zero if no users
            metrics_summary['response_rate'] = (
                metrics_summary['engaged_users'] / metrics_summary['total_users']) * 100

        metrics_summary['analyzed_profiles'] = analyzed_user_count
        metrics_summary['avg_posts_per_profile'] = total_analyzed_posts_sum / \
            analyzed_user_count if analyzed_user_count > 0 else 0

        logger.info(f"Calculated stage metrics: {metrics_summary}")
        return metrics_summary
    except Exception as e:
        logger.error(f"Error calculating stage metrics: {e}", exc_info=True)
        return {'total_users': 0, 'engaged_users': 0, 'analyzed_profiles': 0, 'total_messages': 0, 'response_rate': 0, 'avg_messages': 0, 'avg_posts_per_profile': 0}


def get_response_level_wait_time(num_responses):
    """Return wait time in days based on response level"""
    if num_responses >= 20:  # High responder (green)
        return 2  # 48 hours
    elif num_responses >= 11:  # Medium responder (yellow)
        return 5  # 5 days
    else:  # Low responder (orange/red)
        return 7  # 7 days


def get_users_ready_for_followup(analytics_data: dict):
    """Determine which users are ready for follow-up based on their response level."""
    ready_for_followup = {
        'high_responders': [],
        'medium_responders': [],
        'low_responders': [],
        'total_count': 0
    }
    current_time = datetime.datetime.now()

    # 'analytics_data' contains 'conversations' from SQLite
    conversations_data = analytics_data.get('conversations', {})
    if not isinstance(conversations_data, dict):
        st.error(
            "Conversations data is not a dictionary. Cannot determine users for followup.")
        logger.error("'conversations' key in analytics_data is not a dict.")
        return ready_for_followup

    for username, user_container in conversations_data.items():
        metrics = user_container.get('metrics', {})
        if not metrics:
            logger.warning(
                f"No metrics found for user {username} in get_users_ready_for_followup")
            continue

        # last_interaction_timestamp should be loaded from SQLite
        last_interaction_ts_str = metrics.get('last_interaction_timestamp')
        last_message_time = None
        if last_interaction_ts_str:
            try:
                last_message_time = datetime.datetime.fromisoformat(
                    last_interaction_ts_str.split('+')[0])
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Could not parse last_interaction_timestamp '{last_interaction_ts_str}' for {username}: {e}")
                pass

        if not last_message_time:
            # Fallback to checking conversation_history if last_interaction_timestamp is missing/invalid
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                try:
                    # Assuming history is sorted, last entry is the latest
                    last_msg_in_history = conversation_history[-1]
                    last_message_time = datetime.datetime.fromisoformat(
                        last_msg_in_history.get('timestamp', '').split('+')[0])
                except (IndexError, ValueError, AttributeError) as e:
                    logger.warning(
                        f"Error parsing timestamp from conversation_history for {username}: {e}")

        if not last_message_time:
            # logger.info(f"No valid last message time found for {username}. Skipping for followup.")
            continue  # Cannot determine readiness without a last message/interaction time

        # 'user_messages' is now directly in metrics from SQLite load
        num_responses = metrics.get('user_messages', 0)
        wait_days = get_response_level_wait_time(num_responses)
        time_since_last_message = current_time - last_message_time

        if time_since_last_message.days >= wait_days:
            user_info = {
                'username': username,
                'days_since_last_message': time_since_last_message.days,
                'response_count': num_responses,
                'last_message_time': last_message_time
            }
            if num_responses >= 20:
                ready_for_followup['high_responders'].append(user_info)
            elif num_responses >= 11:
                ready_for_followup['medium_responders'].append(user_info)
            else:
                ready_for_followup['low_responders'].append(user_info)
            ready_for_followup['total_count'] += 1

    logger.info(
        f"Users ready for followup: High={len(ready_for_followup['high_responders'])}, Med={len(ready_for_followup['medium_responders'])}, Low={len(ready_for_followup['low_responders'])}")
    return ready_for_followup


def get_user_topics(user_data_metrics):
    """Get conversation topics from user's metrics data (loaded from SQLite)."""
    try:
        # conversation_topics_json should be a string loaded from SQLite, parse it
        topics_json_str = user_data_metrics.get('conversation_topics_json')
        if topics_json_str:
            topics = json.loads(topics_json_str)
            if isinstance(topics, list):
                # Filter out any empty or None topics
                return [topic for topic in topics if topic and not str(topic).startswith('**')]
        logger.warning(
            f"No valid conversation_topics_json found for user {user_data_metrics.get('ig_username')}")
        return []
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding conversation_topics_json for user {user_data_metrics.get('ig_username')}: {e}")
        return []
    except Exception as e:
        logger.error(
            f"Unexpected error in get_user_topics for {user_data_metrics.get('ig_username')}: {e}", exc_info=True)
        return []


def queue_message_for_followup(username, message, topic):
    """Add a message to the follow-up queue"""
    st.session_state.message_queue.append({
        'username': username,
        'message': message,
        'topic': topic,
        'queued_time': datetime.datetime.now().isoformat()
    })


def save_followup_queue():
    """Save the follow-up queue to a file for the follow-up manager"""
    # ACTION_ITEMS_JSON_FILE is used for loading action_items, not for followup_queue.json.
    # Determine a new path or use a dedicated one if followup_queue.json is different.
    followup_queue_dir = os.path.dirname(
        ACTION_ITEMS_JSON_FILE)  # Assuming same directory for now
    queue_file = os.path.join(followup_queue_dir, "followup_queue.json")
    try:
        with open(queue_file, 'w') as f:
            json.dump({
                'messages': st.session_state.message_queue,
                'created_at': datetime.datetime.now().isoformat()
            }, f, indent=2)
        logger.info(f"Followup queue saved to {queue_file}")
        return True
    except Exception as e:
        st.error(f"Error saving follow-up queue: {e}")
        logger.error(f"Error saving followup_queue.json: {e}", exc_info=True)
        return False


def display_user_followup(user_followup_info, all_analytics_data):
    """Display user follow-up information with message generation and sending capabilities."""
    username = user_followup_info['username']

    # Get user_data by checking the 'conversations' part of all_analytics_data
    user_container = all_analytics_data.get('conversations', {}).get(username)
    if not user_container or 'metrics' not in user_container:
        st.error(
            f"Could not find data for user '{username}' to display followup.")
        logger.error(
            f"Data or metrics missing for user {username} in display_user_followup.")
        return

    # This is the dict of the user's data from SQLite
    metrics = user_container['metrics']

    with st.expander(f"{username} - {user_followup_info['days_since_last_message']} days since last message"):
        # Create columns for layout
        info_col, history_col = st.columns([1, 1])

        with info_col:
            # Basic Information
            st.write("### User Information")
            st.write(
                f"**Response count:** {user_followup_info['response_count']}")
            st.write(
                f"**Last message:** {user_followup_info['last_message_time'].strftime('%Y-%m-%d %H:%M')}")

            # Get user's conversation topics from metrics
            available_topics = get_user_topics(metrics)

            if not available_topics:
                st.warning("No conversation topics available for this user")
                current_topic = "General catch-up"  # Default topic
            else:
                # Get user's category and appropriate topic
                # get_user_category needs to handle new metrics structure
                user_category = get_user_category(metrics)
                current_topic = get_topic_for_category(
                    user_category, metrics)  # Same for get_topic_for_category

                # Show current topic
                st.write("### Current Topic")
                st.info(current_topic)

                if st.button(f"Generate Message", key=f"gen_{username}"):
                    if not gemini_model:
                        st.error(
                            "Gemini model not available for message generation.")
                        return
                    with st.spinner("Generating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic)
                    if message:
                        # Store generated message in user_followup_info (which is part of a list, not session state directly)
                        user_followup_info['generated_message'] = message
                        user_followup_info['selected_topic'] = current_topic
                        st.success("Message generated!")
                        st.rerun()  # Rerun to show the text_area
                    else:
                        st.error("Failed to generate message.")

        with history_col:
            # Conversation History
            st.write("### Conversation History")
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                st.write("Last 5 messages:")
                history_container = st.container()
                with history_container:
                    for msg in conversation_history[-5:]:
                        sender = "User" if msg.get(
                            'type') == 'user' else "Shannon"
                        st.write(f"**{sender}:** {msg.get('text', '')}")
            else:
                st.info("No conversation history available")

        # Message editing section - full width below columns
        st.write("### Follow-up Message")
        if 'generated_message' in user_followup_info:
            # Create a text area for editing the message
            edited_message = st.text_area(
                "Edit message if needed:",
                value=user_followup_info['generated_message'],
                key=f"edit_{username}",
                height=100
            )

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                # Add a regenerate button
                if st.button("Regenerate", key=f"regen_{username}"):
                    if not gemini_model:
                        st.error(
                            "Gemini model not available for message regeneration.")
                        return
                    with st.spinner("Regenerating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic)
                        if message:
                            user_followup_info['generated_message'] = message
                            user_followup_info['selected_topic'] = current_topic
                        st.success("Message regenerated!")
                        st.rerun()
                else:
                    st.error("Failed to regenerate message")

            with col2:
                # Add queue message button
                if st.button("Queue Message", key=f"queue_{username}"):
                    queue_message_for_followup(
                        username, edited_message, current_topic)
                    st.success(f"Message queued for {username}")
                    st.rerun()  # Rerun to reflect queue update

            # Update the stored message if edited
            if edited_message != user_followup_info['generated_message']:
                user_followup_info['generated_message'] = edited_message
                # No need for success message or rerun here, just update the dict for next interaction
        else:
            st.warning("Click 'Generate Message' to create a message")


def display_scheduled_followups_tab(analytics_data_dict):
    """Display the scheduled follow-ups section. Renamed to avoid conflict."""
    st.header("📅 Scheduled Follow-ups")

    # Get users ready for follow-up
    followup_data_list = get_users_ready_for_followup(analytics_data_dict)

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Ready for Follow-up",
                  followup_data_list['total_count'])

    with col2:
        high_count = len(followup_data_list['high_responders'])
        st.metric("High Responders Ready (48h)", high_count)

    with col3:
        medium_count = len(followup_data_list['medium_responders'])
        st.metric("Medium Responders Ready (5d)", medium_count)

    with col4:
        low_count = len(followup_data_list['low_responders'])
        st.metric("Low Responders Ready (7d)", low_count)

    # Display queued messages if any exist
    if st.session_state.message_queue:
        st.subheader("📬 Queued Messages")
        st.write(
            f"{len(st.session_state.message_queue)} messages queued for sending")

        # Show queued messages in an expander
        with st.expander("View Queued Messages"):
            for msg_item in st.session_state.message_queue:
                st.write(f"**To:** {msg_item['username']}")
                st.write(f"**Topic:** {msg_item['topic']}")
                st.write(f"**Message:** {msg_item['message']}")
                st.write("---")

        # Add send button
        if st.button("🚀 Send All Queued Messages", type="primary"):
            if save_followup_queue():
                st.success(
                    "Messages queued for sending! Follow-up manager will process these messages.")
                # Clear the queue after successful save
                st.session_state.message_queue = []
                st.rerun()
            else:
                st.error("Failed to queue messages for sending")

    # Create tabs for different response levels
    high_tab, medium_tab, low_tab = st.tabs([
        "🟢 High Responders",
        "🟡 Medium Responders",
        "🟠 Low Responders"
    ])

    # Display users with their generated messages
    with high_tab:
        if followup_data_list['high_responders']:
            for user_info_item in followup_data_list['high_responders']:
                # Pass full data dict
                display_user_followup(user_info_item, analytics_data_dict)
        else:
            st.info("No high responders ready for follow-up")

    with medium_tab:
        if followup_data_list['medium_responders']:
            for user_info_item in followup_data_list['medium_responders']:
                display_user_followup(user_info_item, analytics_data_dict)
        else:
            st.info("No medium responders ready for follow-up")

    with low_tab:
        if followup_data_list['low_responders']:
            for user_info_item in followup_data_list['low_responders']:
                display_user_followup(user_info_item, analytics_data_dict)
        else:
            st.info("No low responders ready for follow-up")


def display_overview_tab(analytics_data_dict):
    """Display the overview page. Renamed to avoid conflict."""
    st.header("📊 Overview")

    # Add signup check button and last check time
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔍 Check New Signups", type="primary"):
            with st.spinner("Checking for new signups..."):
                # check_sheet_for_signups might need to be adapted if it saves data directly
                # For now, assume it modifies analytics_data_dict in place if needed, or relies on save_analytics_data
                updated_data, signups_found = check_sheet_for_signups(
                    analytics_data_dict)
                if signups_found:
                    # Save the entire updated data structure if check_sheet_for_signups modifies it broadly
                    # or if specific user metrics were updated and saved individually inside check_sheet_for_signups
                    st.success(
                        "Found and processed new trial signups! Data updated in SQLite where applicable.")
                    st.session_state.analytics_data = updated_data  # Update session state
                    st.rerun()
                else:
                    st.info("No new signups found or no changes made.")
                st.session_state.last_signup_check = datetime.datetime.now()

    with col2:
        if st.session_state.last_signup_check:
            st.info(
                f"Last signup check: {st.session_state.last_signup_check.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("No recent signup checks")

    # Display metrics and other overview content
    metrics_summary = get_stage_metrics(analytics_data_dict)

    # Create columns for metrics display
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Users", metrics_summary['total_users'])
        st.metric("Engaged Users", metrics_summary['engaged_users'])

    with col2:
        st.metric("Total Messages", metrics_summary['total_messages'])
        st.metric("Avg Messages per User",
                  f"{metrics_summary['avg_messages']:.1f}")

    with col3:
        st.metric("Response Rate", f"{metrics_summary['response_rate']:.1f}%")
        st.metric("Analyzed Profiles", metrics_summary['analyzed_profiles'])


def save_analytics_data(data_to_save: dict, json_file_path_for_actions: str) -> bool:
    """Save user metrics to SQLite and action_items to JSON."""
    overall_success = True
    # 1. Save 'conversations' data (user metrics) to SQLite
    if 'conversations' in data_to_save:
        for ig_username, user_container in data_to_save['conversations'].items():
            metrics = user_container.get('metrics')
            if metrics:
                if not save_metrics_to_sqlite(ig_username, metrics):
                    logger.error(
                        f"Failed to save metrics to SQLite for user: {ig_username}")
                    overall_success = False  # Mark failure but continue trying others
            else:
                logger.warning(
                    f"No metrics found for user {ig_username} during save_analytics_data.")
    else:
        logger.warning("No 'conversations' key in data_to_save for SQLite.")

    # 2. Save 'action_items' to JSON file
    if 'action_items' in data_to_save:
        try:
            logger.info(
                f"Saving action_items to JSON: {json_file_path_for_actions}")
            json_dir = os.path.dirname(json_file_path_for_actions)
            if not os.path.exists(json_dir):
                os.makedirs(json_dir)
                logger.info(f"Created directory for JSON file: {json_dir}")
            content_for_json = {'action_items': data_to_save['action_items']}
            with open(json_file_path_for_actions, 'w', encoding='utf-8') as f:
                json.dump(content_for_json, f, indent=2)
            logger.info(
                f"Successfully saved action_items to {json_file_path_for_actions}")
        except Exception as e:
            logger.error(
                f"Error saving action_items to JSON {json_file_path_for_actions}: {e}", exc_info=True)
            overall_success = False
    else:
        logger.warning("No 'action_items' key in data_to_save for JSON.")

    return overall_success


def bulk_update_leads_journey_stage(data: dict) -> tuple[dict, int]:
    """
    Update journey stages for leads (pre-trial/non-paying) based on conversation analysis.
    Assumes 'data' contains 'conversations' loaded from SQLite.
    Saves changes per user to SQLite directly.
    """
    try:
        updated_count = 0
        conversations = data.get('conversations', {})
        logger.info(
            f"Starting bulk update for {len(conversations)} leads' journey stages.")
        current_time = datetime.datetime.now()

        for username, user_container in conversations.items():
            metrics = user_container.get('metrics', {})
            if not metrics:
                logger.warning(
                    f"No metrics for {username} in bulk_update_leads_journey_stage.")
                continue

            journey_stage = metrics.get('journey_stage', {})
            if not isinstance(journey_stage, dict):
                journey_stage = {}  # Ensure it's a dict

            # Skip if they're already a paying client or in trial
            if journey_stage.get('is_paying_client') or journey_stage.get('trial_start_date'):
                continue

            user_updated_this_run = False
            try:
                # Ensure journey_stage structure exists
                if 'current_stage' not in journey_stage:
                    journey_stage['current_stage'] = 'Topic 1'
                if 'topic_progress' not in journey_stage:
                    journey_stage['topic_progress'] = {}
                if 'last_topic_interaction' not in journey_stage:
                    journey_stage['last_topic_interaction'] = {}

                # Define topics (simplified for this example)
                # In a real scenario, these topics might come from get_user_topics or a config
                lead_topics_map = {
                    1: "Topic 1", 2: "Topic 2", 3: "Topic 3", 4: "Topic 4", 5: "Topic 5 - Trial Offer"
                }
                # Get actual topics if available from user's profile_bio_text or conversation_topics_json
                actual_user_topics = get_user_topics(
                    metrics)  # Pass the full metrics dict

                conversation_history = metrics.get('conversation_history', [])
                if conversation_history:
                    # Loop through actual topics (up to 4 for pre-trial offer)
                    for i, topic_text in enumerate(actual_user_topics[:4], 1):
                        topic_key = f'topic{i}_completed'
                        last_response_key = f'topic{i}_last_response'

                        if journey_stage['topic_progress'].get(topic_key):
                            continue  # Already completed this topic

                        # Find messages from Shannon containing this topic
                        shannon_topic_messages = [
                            msg for msg in conversation_history
                            if msg.get('type') != 'user' and topic_text.lower() in msg.get('text', '').lower()
                        ]

                        if shannon_topic_messages:
                            last_shannon_topic_msg_ts_str = shannon_topic_messages[-1].get(
                                'timestamp')
                            if not last_shannon_topic_msg_ts_str:
                                continue
                            last_shannon_topic_msg_ts = datetime.datetime.fromisoformat(
                                last_shannon_topic_msg_ts_str.split('+')[0])

                            # Find user responses after Shannon mentioned the topic
                            user_responses_after_topic = [
                                msg for msg in conversation_history
                                if msg.get('type') == 'user' and
                                datetime.datetime.fromisoformat(
                                    msg.get('timestamp', '').split('+')[0]) > last_shannon_topic_msg_ts
                            ]

                            if user_responses_after_topic:
                                last_user_response_ts_str = user_responses_after_topic[-1].get(
                                    'timestamp')
                                last_user_response_ts = datetime.datetime.fromisoformat(
                                    last_user_response_ts_str.split('+')[0])
                                journey_stage['last_topic_interaction'][last_response_key] = last_user_response_ts.isoformat(
                                )

                                if (current_time - last_user_response_ts).total_seconds() > 24 * 3600:
                                    journey_stage['topic_progress'][topic_key] = True
                                    user_updated_this_run = True
                                    if journey_stage['current_stage'] == lead_topics_map.get(i):
                                        next_topic_num = i + 1
                                        journey_stage['current_stage'] = lead_topics_map.get(
                                            next_topic_num, 'Topic 5 - Trial Offer')
                            else:  # No user response after Shannon mentioned topic
                                # e.g. 2 days no response
                                if (current_time - last_shannon_topic_msg_ts).total_seconds() > 48 * 3600:
                                    # Consider re-engaging or moving on, for now, just log or mark as stale
                                    pass

                    # Check for trial offer (Topic 5)
                    trial_keywords = ['free month',
                                      'trial', 'sign up', 'onboarding']
                    shannon_trial_offer_messages = [
                        msg for msg in conversation_history
                        if msg.get('type') != 'user' and
                        any(keyword in msg.get('text', '').lower()
                            for keyword in trial_keywords)
                    ]

                    if shannon_trial_offer_messages:
                        last_shannon_trial_offer_ts_str = shannon_trial_offer_messages[-1].get(
                            'timestamp')
                        if last_shannon_trial_offer_ts_str:
                            last_shannon_trial_offer_ts = datetime.datetime.fromisoformat(
                                last_shannon_trial_offer_ts_str.split('+')[0])
                            user_responses_after_trial_offer = [
                                msg for msg in conversation_history
                                if msg.get('type') == 'user' and
                                datetime.datetime.fromisoformat(
                                    msg.get('timestamp', '').split('+')[0]) > last_shannon_trial_offer_ts
                            ]
                            if user_responses_after_trial_offer:
                                last_user_response_trial_ts_str = user_responses_after_trial_offer[-1].get(
                                    'timestamp')
                                last_user_response_trial_ts = datetime.datetime.fromisoformat(
                                    last_user_response_trial_ts_str.split('+')[0])
                                journey_stage['last_topic_interaction']['topic5_last_response'] = last_user_response_trial_ts.isoformat(
                                )
                                if (current_time - last_user_response_trial_ts).total_seconds() > 24 * 3600:
                                    journey_stage['topic_progress']['trial_offer_made'] = True
                                    # Or 'Awaiting Trial Signup'
                                    journey_stage['current_stage'] = 'Topic 5 - Trial Offer'
                                    user_updated_this_run = True
                            else:  # No response to trial offer
                                # e.g. 3 days
                                if (current_time - last_shannon_trial_offer_ts).total_seconds() > 72 * 3600:
                                    # Mark as made, even if no response
                                    journey_stage['topic_progress']['trial_offer_made'] = True
                                    journey_stage['current_stage'] = 'Topic 5 - Trial Offer'
                                    user_updated_this_run = True

                if user_updated_this_run:
                    metrics['journey_stage'] = journey_stage
                    if save_metrics_to_sqlite(username, metrics):
                        updated_count += 1
                        logger.info(
                            f"Updated lead journey stage for {username} to {journey_stage.get('current_stage')} in SQLite.")
                    else:
                        logger.error(
                            f"Failed to save updated journey stage for {username} to SQLite.")

            except Exception as e:
                logger.error(
                    f"Error processing lead journey stage for {username}: {e}", exc_info=True)
                continue

        logger.info(
            f"Lead journey stage update completed. Updated {updated_count} leads in SQLite.")
        return data, updated_count  # Return the main data dict and count

    except Exception as e:
        logger.error(
            f"Error in lead journey stage bulk update: {e}", exc_info=True)
        return data, 0


def bulk_update_client_profiles(data: dict) -> tuple[dict, int]:
    """
    Update profiles for paying clients and trial members using Google Sheets data.
    Saves changes per user to SQLite directly.
    """
    try:
        updated_count = 0
        conversations = data.get('conversations', {})
        logger.info(
            f"Starting bulk update for client profiles with sheet data for {len(conversations)} users.")

        for username, user_container in conversations.items():
            metrics = user_container.get('metrics', {})
            if not metrics:
                logger.warning(
                    f"No metrics for {username} in bulk_update_client_profiles.")
                continue

            ig_username = metrics.get('ig_username')
            if not ig_username:
                logger.warning(
                    f"Missing ig_username in metrics for key {username}.")
                continue

            user_updated_this_run = False
            try:
                # Get user data from sheets
                # This is an alias for get_user_sheet_details
                sheet_data = get_checkin_data(ig_username)
                if sheet_data:
                    logger.info(
                        f"Found sheet data for client {ig_username}. Updating profile.")

                    # Update basic metrics
                    metrics['first_name'] = sheet_data.get(
                        'First Name', metrics.get('first_name'))
                    metrics['last_name'] = sheet_data.get(
                        'Last Name', metrics.get('last_name'))
                    metrics['gender'] = sheet_data.get(
                        'Gender', metrics.get('gender'))
                    metrics['weight'] = sheet_data.get(
                        'Weight', metrics.get('weight'))
                    metrics['height'] = sheet_data.get(
                        'Height', metrics.get('height'))
                    # For text fields, prefer sheet data if available, otherwise keep existing
                    metrics['goals_text'] = sheet_data.get(
                        'Long Term Goals', metrics.get('goals_text'))
                    metrics['dietary_requirements'] = sheet_data.get(
                        'Dietary Requirements', metrics.get('dietary_requirements'))
                    metrics['dob'] = sheet_data.get(
                        'Date of Birth', metrics.get('dob'))
                    metrics['gym_access'] = sheet_data.get(
                        'Gym Access', metrics.get('gym_access'))
                    metrics['training_frequency'] = sheet_data.get(
                        'Training Frequency', metrics.get('training_frequency'))
                    metrics['exercises_enjoyed'] = sheet_data.get(
                        'Exercises Enjoyed', metrics.get('exercises_enjoyed'))
                    metrics['daily_calories'] = sheet_data.get(
                        'Daily Calories', metrics.get('daily_calories'))

                    # Mark as complete if sheet data found
                    metrics['profile_complete'] = True
                    metrics['last_updated'] = datetime.datetime.now().isoformat()
                    user_updated_this_run = True

                    # Initialize or update journey stage
                    journey_stage = metrics.get('journey_stage', {})
                    if not isinstance(journey_stage, dict):
                        journey_stage = {}

                    # Update trial/paying status from Google Sheet (assuming these columns exist in your sheet_data)
                    # These column names are examples, adjust to your actual Google Sheet headers
                    # Example column name
                    if sheet_data.get('Subscription Status') == 'Active':
                        logger.info(
                            f"Setting {ig_username} as paying client based on sheet.")
                        journey_stage['is_paying_client'] = True
                        journey_stage['current_stage'] = 'Paying Client'
                        # Clear trial if paying
                        journey_stage['trial_start_date'] = None
                        journey_stage['trial_end_date'] = None
                        user_updated_this_run = True
                    # Example column name
                    elif sheet_data.get('Trial Status') == 'Active':
                        trial_start_str = sheet_data.get(
                            'Trial Start Date')  # Example column name
                        if trial_start_str:
                            try:
                                logger.info(
                                    f"Setting trial dates for {ig_username} based on sheet.")
                                start_date = datetime.datetime.strptime(
                                    trial_start_str, '%Y-%m-%d')  # Adjust format if needed
                                journey_stage['trial_start_date'] = start_date.isoformat(
                                )
                                journey_stage['trial_end_date'] = (
                                    start_date + datetime.timedelta(days=28)).isoformat()
                                # Ensure not marked as paying if in trial
                                journey_stage['is_paying_client'] = False

                                # Calculate trial week
                                days_in_trial = (
                                    datetime.datetime.now() - start_date).days
                                if 0 <= days_in_trial <= 7:
                                    journey_stage['current_stage'] = 'Trial Week 1'
                                elif 8 <= days_in_trial <= 14:
                                    journey_stage['current_stage'] = 'Trial Week 2'
                                elif 15 <= days_in_trial <= 21:
                                    journey_stage['current_stage'] = 'Trial Week 3'
                                elif 22 <= days_in_trial <= 28:
                                    journey_stage['current_stage'] = 'Trial Week 4'
                                else:
                                    # Or similar if past 28 days
                                    journey_stage['current_stage'] = 'Trial Ended'
                                logger.info(
                                    f"Set {ig_username} to {journey_stage['current_stage']} based on sheet trial data.")
                                user_updated_this_run = True
                            except ValueError as ve:
                                logger.error(
                                    f"Invalid trial start date format '{trial_start_str}' for {ig_username}: {ve}")
                        else:  # Trial Active but no start date, maybe set to current stage to indicate active trial
                            # Only if not already in a specific trial week
                            if not journey_stage.get('trial_start_date'):
                                journey_stage['current_stage'] = 'Trial Active (Date Unknown)'
                                user_updated_this_run = True

                    metrics['journey_stage'] = journey_stage
                else:
                    # logger.info(f"No sheet data found for {ig_username}. Profile not updated from sheets.")
                    pass  # No sheet data, do not modify existing SQLite data unless other logic dictates

                if user_updated_this_run:
                    if save_metrics_to_sqlite(ig_username, metrics):
                        updated_count += 1
                        logger.info(
                            f"Client profile for {ig_username} updated in SQLite.")
                    else:
                        logger.error(
                            f"Failed to save updated profile for {ig_username} to SQLite.")

            except Exception as e:
                logger.error(
                    f"Error updating client profile for {ig_username}: {e}", exc_info=True)
                continue

        logger.info(
            f"Client profile update from sheets completed. Updated {updated_count} clients in SQLite.")
        return data, updated_count  # Return main data dict and count

    except Exception as e:
        logger.error(
            f"Error in client profile bulk update: {e}", exc_info=True)
        return data, 0


def display_user_profiles_with_bulk_update(analytics_data_dict):
    """Display user profiles section with bulk update buttons."""
    st.header("👥 User Profiles")

    # Create two columns for the update buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Update Client Profiles (from Sheets)", key="update_clients_btn", type="primary"):
            with st.spinner("Updating client profiles from Google Sheets into SQLite..."):
                # Pass the current state of analytics_data_dict
                updated_data_after_client_sync, update_count = bulk_update_client_profiles(
                    analytics_data_dict)
                if update_count > 0:
                    st.success(
                        f"Successfully updated {update_count} client profiles in SQLite!")
                    # Update session state to reflect changes immediately in the dashboard
                    st.session_state.analytics_data = updated_data_after_client_sync
                    st.rerun()
                else:
                    st.info(
                        "No client profiles needed updating from Sheets, or no sheet data found.")

    with col2:
        if st.button("🔄 Update Lead Stages (Conversation Analysis)", key="update_leads_btn", type="primary"):
            with st.spinner("Analyzing conversations and updating lead stages in SQLite..."):
                updated_data_after_lead_sync, update_count = bulk_update_leads_journey_stage(
                    analytics_data_dict)
                if update_count > 0:
                    st.success(
                        f"Successfully updated {update_count} lead stages in SQLite!")
                    st.session_state.analytics_data = updated_data_after_lead_sync
                    st.rerun()
                else:
                    st.info(
                        "No lead stages needed updating based on conversation analysis.")

    st.info(
        "Use 'Update Client Profiles' for paying clients and trial members to sync with Google Sheets data into SQLite. "
        "Use 'Update Lead Stages' to analyze conversations and update stages for leads in the sales funnel in SQLite."
    )

    # Use the imported display_user_profiles function, passing the potentially updated data
    # Assumes display_user_profiles handles the new structure
    display_user_profiles(st.session_state.analytics_data)


# --- ADDED: Function to display Daily Report --- START ---
def display_daily_report(analytics_data_dict):
    """Display the Daily Report page with pending and completed actions.
       'action_items' are loaded from JSON and are part of analytics_data_dict.
    """
    st.header("📊 Daily Report")

    action_items = analytics_data_dict.get("action_items", [])
    pending_items = [
        item for item in action_items if item.get("status") == "pending"]
    # Assume items not marked 'pending' are completed for now
    completed_items = [
        item for item in action_items if item.get("status") == "completed"]

    st.divider()
    # --- Pending Items --- #
    st.subheader("🚨 Things To Do")
    if not pending_items:
        st.success("✅ All clear! No pending action items.")
    else:
        st.warning(f"Found {len(pending_items)} pending action item(s):")
        for i, item in enumerate(pending_items):
            try:
                # Attempt to parse timestamp, allow for Z or +00:00
                ts_str_raw = item.get("timestamp", "")
                ts = datetime.datetime.fromisoformat(
                    ts_str_raw.replace("Z", "+00:00"))
                ts_str_formatted = ts.strftime("%Y-%m-%d %H:%M UTC")
            except ValueError:
                # Fallback to raw string if parse fails
                ts_str_formatted = item.get("timestamp", "Invalid Date")
            st.markdown(
                f"- **{item.get('client_name', 'Unknown')}** ({ts_str_formatted}): {item.get('task_description', 'No description')}")
            # Optional: Add a button to mark as complete later
            # if st.button(f"Mark Complete", key=f"complete_{i}_{item.get('timestamp')}"):
            #     # Logic to update the status in the JSON file would go here
            #     st.rerun()

    st.divider()
    # --- Completed Items --- #
    st.subheader("✅ Completed Actions (Recently)")
    if not completed_items:
        st.info("No actions marked as completed yet.")
    else:
        # Sort completed items by timestamp, newest first
        completed_items.sort(key=lambda x: x.get(
            "timestamp", ""), reverse=True)
        st.success(
            f"Showing {len(completed_items)} recently completed action(s):")
        # Limit displayed completed items if needed (e.g., last 10)
        for item in completed_items[:10]:  # Display latest 10
            try:
                ts_str_raw = item.get("timestamp", "")
                ts = datetime.datetime.fromisoformat(
                    ts_str_raw.replace("Z", "+00:00"))
                ts_str_formatted = ts.strftime("%Y-%m-%d %H:%M UTC")
            except ValueError:
                ts_str_formatted = item.get("timestamp", "Invalid Date")
            # Use st.markdown for consistency, could use st.write too
            st.markdown(
                f"- **{item.get('client_name', 'Unknown')}** ({ts_str_formatted}): {item.get('task_description', 'No description')}")

# --- ADDED: Function to display Daily Report --- END ---

# --- ADDED: Function to display Response Review Queue --- START ---


def display_response_review_queue():
    st.header("📝 Response Review Queue")

    # --- ADDED: Display Review Accuracy Stats ---
    accuracy_stats = get_review_accuracy_stats()
    if accuracy_stats:
        st.subheader("Review Accuracy Statistics")
        cols = st.columns(4)
        cols[0].metric("Total Processed", accuracy_stats.get(
            "total_processed_including_discarded", 0))
        cols[1].metric("Sent As-Is", f"{accuracy_stats.get('accuracy_percentage', 0.0)}%",
                       delta=f"{accuracy_stats.get('sent_as_is', 0)} count")
        cols[2].metric("Edited by User", f"{accuracy_stats.get('edited_percentage', 0.0)}%",
                       delta=f"{accuracy_stats.get('edited_by_user', 0)} count")
        cols[3].metric("Discarded", f"{accuracy_stats.get('discard_percentage_of_total_processed', 0.0)}%",
                       delta=f"{accuracy_stats.get('discarded_count', 0)} count", delta_color="inverse")

        # Additional detail if needed
        # with st.expander("View Detailed Stats Object"):
        #     st.json(accuracy_stats)
        st.divider()
    # --- END: Display Review Accuracy Stats ---

    pending_reviews = get_pending_reviews()

    if not pending_reviews:
        st.success("🎉 No responses currently pending review!")
        return

    st.info(f"You have {len(pending_reviews)} responses awaiting review.")

    for review_item in pending_reviews:
        review_id = review_item['review_id']
        user_ig = review_item['user_ig_username']
        subscriber_id = review_item['user_subscriber_id']
        incoming_msg = review_item['incoming_message_text']
        proposed_resp = review_item['proposed_response_text']
        original_prompt = review_item['generated_prompt_text']
        conversation_history = review_item.get(
            'conversation_history', [])  # Get the history

        # Use a unique key prefix for widgets inside the loop for each review item
        key_prefix = f"review_{review_id}_"

        with st.expander(f"Review for: {user_ig} (Incoming: \"{review_item.get('user_message_text', incoming_msg)[:50]}...\")", expanded=True):
            # --- MODIFIED: Manual Context Input with a toggle ---
            if f"{key_prefix}show_manual_context" not in st.session_state:
                st.session_state[f"{key_prefix}show_manual_context"] = False

            if st.button("➕ Add Shannon's Missing Context", key=f"{key_prefix}toggle_manual_context_btn"):
                st.session_state[f"{key_prefix}show_manual_context"] = not st.session_state[f"{key_prefix}show_manual_context"]

            manual_context = ""  # Initialize to empty string
            if st.session_state[f"{key_prefix}show_manual_context"]:
                manual_context = st.text_area(
                    "Shannon's Original Comment/Message (Context for History):",
                    height=100,
                    # Changed key to avoid conflict if old one lingers
                    key=f"{key_prefix}manual_context_input",
                    help="If the user's message is a reply to a comment or DM you sent manually, paste your original message here. This will be added to the history *before* the user's message when you click 'Approve & Send'."
                )
            # --- END: Manual Context Input ---

            # Toggle for Conversation History
            show_history = st.toggle(
                "View Conversation History (Last 20 Messages)", key=f"{key_prefix}toggle_history")
            if show_history and conversation_history:
                history_container = st.container(border=True)
                with history_container:
                    history_str_display = ""
                    for msg in conversation_history:  # Already reversed in sqlite_utils
                        sender = "User" if msg.get(
                            'type') == 'user' else "Shanbot"
                        try:
                            # Attempt to parse timestamp for better display
                            ts_obj = datetime.datetime.fromisoformat(
                                msg.get('timestamp', '').split('+')[0])
                            formatted_ts = ts_obj.strftime("%Y-%m-%d %H:%M")
                        except ValueError:
                            formatted_ts = msg.get('timestamp', 'No Timestamp')
                        history_str_display += f"**{sender}** ({formatted_ts}): {msg.get('text', '(empty message)')}\n\n"
                    st.markdown(history_str_display)
            elif show_history and not conversation_history:
                st.caption(
                    "No conversation history found or loaded for this user.")

            # --- ADDING USER MESSAGE DISPLAY HERE ---
            st.markdown("**User Message:**")
            st.text_area("User Message", value=review_item.get(
                'user_message_text', incoming_msg), height=100, disabled=True, key=f"user_msg_{review_id}")
            # --- END USER MESSAGE DISPLAY ---

            st.markdown("**Current Proposed AI Response:**")
            edited_response = st.text_area(
                "Edit Shanbot's Response:", value=proposed_resp, height=150, key=f"{key_prefix}edit")

            user_notes = st.text_input(
                "Why did you edit this response? (helps AI learn):", key=f"{key_prefix}notes",
                help="Optional: Explain why you made changes to help the AI understand your preferences")

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if st.button("Approve & Send", key=f"{key_prefix}send", type="primary"):
                    # Retrieve manual_context value from the text_area if it was shown
                    # The variable `manual_context` from above will hold the value if the box was visible, else it's ""
                    # No, we need to fetch it from session state if the button was used to hide it before sending.
                    # Or better, just use the `manual_context` variable defined in the scope of the review item.

                    current_manual_context = ""
                    # Check if the context area was active
                    if st.session_state.get(f"{key_prefix}show_manual_context", False):
                        # Try to get the value from the input widget if it exists in the current render cycle
                        # This relies on Streamlit's widget state
                        # A more robust way if button clicks cause re-render without text_area might be needed,
                        # but st.text_area usually keeps its value in session_state if a key is provided.
                        # Let's assume `manual_context` variable already holds the latest value if the text_area was visible.
                        # The `manual_context` variable should be up-to-date from the text_area if it was rendered.
                        pass  # manual_context variable from above is used

                    # --- MODIFIED: Insert Manual Context if provided ---
                    # Use the `manual_context` variable directly, which was populated if the text_area was visible
                    if manual_context and manual_context.strip():
                        context_inserted = insert_manual_context_message(
                            user_ig_username=user_ig,
                            subscriber_id=subscriber_id,  # Ensure subscriber_id is available here
                            manual_message_text=manual_context.strip(),
                            user_message_timestamp_str=review_item['incoming_message_timestamp']
                        )
                        if context_inserted:
                            st.toast(
                                f"Manually entered context saved for {user_ig}!", icon="📝")
                            logger.info(
                                f"Successfully inserted manual context for {user_ig} from dashboard.")
                            # Refresh conversation history in the current view if possible, or at least notify
                            # For now, the history shown won't auto-update with this, user will see it on next full load/refresh
                        else:
                            st.error(
                                f"Failed to save manual context for {user_ig}. Please check logs.")
                            logger.error(
                                f"Failed to insert manual context for {user_ig} from dashboard.")
                    # --- END: Insert Manual Context ---

                    # 1. Split the edited response into chunks
                    message_chunks = split_response_into_messages(
                        edited_response)
                    manychat_field_names = [
                        "o1 Response", "o1 Response 2", "o1 Response 3"]

                    all_sends_successful = True
                    first_chunk_sent_successfully = False

                    for i, chunk in enumerate(message_chunks):
                        if i < len(manychat_field_names):
                            field_name = manychat_field_names[i]
                            send_success = update_manychat_fields(
                                subscriber_id, {field_name: chunk}
                            )
                            if send_success:
                                logger.info(
                                    f"Successfully sent chunk {i+1} to {field_name} for {user_ig}")
                                if i == 0:
                                    first_chunk_sent_successfully = True
                                # Small delay between sending parts
                                time.sleep(0.5)
                            else:
                                logger.error(
                                    f"Failed to send chunk {i+1} to {field_name} for {user_ig}")
                                all_sends_successful = False
                                st.error(
                                    f"Failed to send part {i+1} of the message to {user_ig}.")
                                break  # Stop sending further chunks if one fails
                        else:
                            logger.warning(
                                f"More message chunks ({len(message_chunks)}) than defined ManyChat fields ({len(manychat_field_names)}). Chunk {i+1} not sent.")
                            st.warning(
                                f"Message part {i+1} was not sent as it exceeds the number of configured ManyChat fields.")
                            break

                    if first_chunk_sent_successfully:  # Proceed with DB updates if at least the first part was sent
                        # Set "response time" field to "action" in ManyChat
                        mc_field_set_success = update_manychat_fields(
                            subscriber_id, {"response time": "action"})
                        if mc_field_set_success:
                            logger.info(
                                f"Successfully set 'response time' to 'action' for {user_ig} (SID: {subscriber_id})")
                        else:
                            logger.warning(
                                f"Failed to set 'response time' to 'action' for {user_ig} (SID: {subscriber_id})")
                            # Non-critical, so we don't stop the flow, just log a warning

                        # 2. Update review status in DB (using the full edited_response)
                        update_status_success = update_review_status(
                            review_id, "sent", edited_response
                        )
                        if not update_status_success:
                            st.error(
                                f"Failed to update review status for review_id {review_id} in DB."
                            )

                        # 3. Add the full sent message to the main conversation history
                        add_history_success = add_message_to_history(
                            ig_username=user_ig,
                            message_type='ai',
                            message_text=edited_response  # Log the full response
                        )
                        if not add_history_success:
                            st.warning(
                                f"Failed to add sent message to conversation history for {user_ig}."
                            )

                        # 4. Add to learning log (using the full edited_response)
                        log_success = add_to_learning_log(
                            review_id=review_id,
                            user_ig_username=user_ig,
                            user_subscriber_id=subscriber_id,
                            original_prompt_text=original_prompt,
                            original_gemini_response=proposed_resp,
                            edited_response_text=edited_response,  # Log the full response
                            user_notes=user_notes,
                            is_good_example_for_few_shot=None  # Auto-determine based on editing
                        )
                        if not log_success:
                            st.warning(
                                f"Failed to add to learning log for review_id {review_id}."
                            )

                        if all_sends_successful and update_status_success and add_history_success:
                            st.success(
                                f"Response sent to {user_ig}, status updated, history logged, and feedback recorded! Refreshing..."
                            )
                        elif first_chunk_sent_successfully:
                            st.warning(
                                f"Response partially sent to {user_ig}. DB records updated. Some message parts may have failed. Please check logs. Refreshing..."
                            )
                        else:  # This case should ideally not be reached if first_chunk_sent_successfully is the gate for DB ops
                            st.error(
                                f"Message sending failed for {user_ig}. DB operations not fully completed. Please check logs."
                            )
                        st.rerun()
                    elif not all_sends_successful:  # No chunks sent successfully
                        st.error(
                            f"Failed to send message to {user_ig}. Please check ManyChat logs and try again."
                        )

            with col2:
                if st.button("Discard", key=f"{key_prefix}discard"):
                    update_success = update_review_status(
                        review_id, "discarded")
                    log_success = add_to_learning_log(
                        review_id=review_id,
                        user_ig_username=user_ig,
                        user_subscriber_id=subscriber_id,
                        original_prompt_text=original_prompt,
                        original_gemini_response=proposed_resp,
                        edited_response_text="[DISCARDED]",
                        user_notes=f"[DISCARDED by user] {user_notes}".strip()
                    )
                    if update_success:
                        st.warning(
                            f"Response for {user_ig} discarded. Feedback logged. Refreshing...")
                    else:
                        st.error(
                            f"Failed to update review status to discarded for {review_id}.")
                    if not log_success:
                        st.warning(
                            f"Failed to add discarded item to learning log for review_id {review_id}.")
                    st.rerun()
            st.markdown("---")
# --- ADDED: Function to display Response Review Queue --- END ---

# --- ADDED: Function to display Recent Interactions --- START ---


def get_users_from_last_30_days(analytics_data_dict):
    """Get users who have interacted with Shanbot in the last 30 days"""
    current_time = datetime.datetime.now()
    thirty_days_ago = current_time - datetime.timedelta(days=30)

    recent_users = []
    conversations_data = analytics_data_dict.get('conversations', {})

    logger.info(
        f"Checking {len(conversations_data)} users for interactions in last 30 days")

    for username, user_container in conversations_data.items():
        metrics = user_container.get('metrics', {})
        if not metrics:
            continue

        # Debug: Log available fields for first few users
        if len(recent_users) < 3:
            logger.info(
                f"Debug - User {username} available fields: {list(metrics.keys())}")

        # Try multiple possible timestamp fields
        last_interaction = None

        # Method 1: Check last_interaction_timestamp
        last_interaction_ts_str = metrics.get('last_interaction_timestamp')
        if last_interaction_ts_str:
            try:
                last_interaction = datetime.datetime.fromisoformat(
                    last_interaction_ts_str.split('+')[0])
                logger.info(
                    f"Found last_interaction_timestamp for {username}: {last_interaction}")
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Could not parse last_interaction_timestamp for {username}: {e}")

        # Method 2: Check conversation_history for last message timestamp
        if not last_interaction:
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                # Get the last message timestamp
                last_msg = conversation_history[-1]
                last_msg_ts_str = last_msg.get('timestamp', '')
                if last_msg_ts_str:
                    try:
                        last_interaction = datetime.datetime.fromisoformat(
                            last_msg_ts_str.split('+')[0])
                        logger.info(
                            f"Found timestamp from conversation history for {username}: {last_interaction}")
                    except (ValueError, AttributeError) as e:
                        logger.warning(
                            f"Could not parse conversation history timestamp for {username}: {e}")

        # Method 3: Check other possible timestamp fields
        if not last_interaction:
            for field_name in ['last_updated', 'updated_at', 'last_message_time', 'timestamp']:
                field_value = metrics.get(field_name)
                if field_value:
                    try:
                        last_interaction = datetime.datetime.fromisoformat(
                            str(field_value).split('+')[0])
                        logger.info(
                            f"Found timestamp in field '{field_name}' for {username}: {last_interaction}")
                        break
                    except (ValueError, AttributeError):
                        continue

        # If we found a valid timestamp, check if it's within 30 days
        if last_interaction and last_interaction >= thirty_days_ago:
            # Calculate some basic stats
            conversation_history = metrics.get('conversation_history', [])
            user_messages = sum(
                1 for msg in conversation_history if msg.get('type') == 'user')
            ai_messages = sum(
                1 for msg in conversation_history if msg.get('type') != 'user')

            recent_users.append({
                'username': username,
                'ig_username': metrics.get('ig_username', username),
                'last_interaction': last_interaction,
                'days_ago': (current_time - last_interaction).days,
                'user_messages': user_messages,
                'ai_messages': ai_messages,
                'total_messages': len(conversation_history),
                'conversation_history': conversation_history,
                'journey_stage': metrics.get('journey_stage', {}),
                'metrics': metrics
            })
            logger.info(
                f"Added {username} to recent users list (last interaction: {last_interaction})")
        elif last_interaction:
            logger.info(
                f"User {username} last interaction {last_interaction} is older than 30 days")
        else:
            logger.warning(f"No valid timestamp found for user {username}")

    logger.info(
        f"Found {len(recent_users)} users with interactions in last 30 days")

    # Sort by most recent interaction first
    recent_users.sort(key=lambda x: x['last_interaction'], reverse=True)
    return recent_users


def display_recent_interactions(analytics_data_dict):
    """Display the Recent Interactions tab with users from last 30 days"""
    st.header("💬 Recent Interactions (Last 30 Days)")

    # Debug section - let's see what data we have
    with st.expander("🔍 Debug Info - Click to expand", expanded=False):
        conversations_data = analytics_data_dict.get('conversations', {})
        st.write(f"**Total users in database:** {len(conversations_data)}")

        if conversations_data:
            # Show sample user data structure
            sample_username = list(conversations_data.keys())[0]
            sample_user = conversations_data[sample_username]
            sample_metrics = sample_user.get('metrics', {})

            st.write(f"**Sample user:** {sample_username}")
            st.write(
                f"**Available fields in metrics:** {list(sample_metrics.keys())}")

            # Check for timestamp fields
            timestamp_fields = []
            for field_name in sample_metrics.keys():
                if 'time' in field_name.lower() or 'date' in field_name.lower() or field_name in ['timestamp', 'updated_at', 'last_updated']:
                    timestamp_fields.append(
                        f"{field_name}: {sample_metrics.get(field_name)}")

            if timestamp_fields:
                st.write("**Found timestamp fields:**")
                for field in timestamp_fields:
                    st.write(f"• {field}")
            else:
                st.write("**No obvious timestamp fields found**")

            # Check conversation history
            conversation_history = sample_metrics.get(
                'conversation_history', [])
            if conversation_history:
                st.write(
                    f"**Conversation history:** {len(conversation_history)} messages")
                if len(conversation_history) > 0:
                    last_msg = conversation_history[-1]
                    st.write(
                        f"**Last message timestamp:** {last_msg.get('timestamp', 'No timestamp')}")
                    st.write(
                        f"**Last message type:** {last_msg.get('type', 'No type')}")
                    st.write(
                        f"**Last message text preview:** {str(last_msg.get('text', ''))[:100]}...")
            else:
                st.write("**No conversation history found**")

    # Get users from last 30 days
    recent_users = get_users_from_last_30_days(analytics_data_dict)

    if not recent_users:
        st.warning("No users have interacted with Shanbot in the last 30 days.")
        st.info(
            "Check the debug info above to see what data is available and verify timestamp formats.")
        return

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Users", len(recent_users))

    with col2:
        total_user_messages = sum(user['user_messages']
                                  for user in recent_users)
        st.metric("Total User Messages", total_user_messages)

    with col3:
        total_ai_messages = sum(user['ai_messages'] for user in recent_users)
        st.metric("Total AI Messages", total_ai_messages)

    with col4:
        avg_messages_per_user = sum(user['total_messages']
                                    for user in recent_users) / len(recent_users)
        st.metric("Avg Messages/User", f"{avg_messages_per_user:.1f}")

    st.divider()

    # Search/filter functionality
    search_term = st.text_input(
        "🔍 Search users by username:", placeholder="Type username to filter...")

    # Filter users based on search
    if search_term:
        filtered_users = [user for user in recent_users
                          if search_term.lower() in user['ig_username'].lower()]
    else:
        filtered_users = recent_users

    if not filtered_users:
        st.warning(f"No users found matching '{search_term}'")
        return

    st.write(f"Showing {len(filtered_users)} users:")

    # Display each user with their conversation history
    for user in filtered_users:
        # Determine status emoji based on interaction recency
        if user['days_ago'] == 0:
            status_emoji = "🟢"  # Today
        elif user['days_ago'] <= 3:
            status_emoji = "🟡"  # Within 3 days
        elif user['days_ago'] <= 7:
            status_emoji = "🟠"  # Within a week
        else:
            status_emoji = "🔴"  # Older than a week

        # Get journey stage info
        journey_stage = user['journey_stage']
        current_stage = journey_stage.get('current_stage', 'Unknown') if isinstance(
            journey_stage, dict) else 'Unknown'
        is_paying = journey_stage.get('is_paying_client', False) if isinstance(
            journey_stage, dict) else False
        trial_start = journey_stage.get('trial_start_date') if isinstance(
            journey_stage, dict) else None

        # Determine user type
        if is_paying:
            user_type = "💰 Paying Client"
        elif trial_start:
            user_type = "🆓 Trial Member"
        else:
            user_type = "👤 Lead"

        # Create expandable section for each user
        with st.expander(
            f"{status_emoji} **{user['ig_username']}** - {user['days_ago']} days ago | "
            f"{user_type} | Stage: {current_stage} | "
            f"Messages: {user['user_messages']} user, {user['ai_messages']} AI",
            expanded=False
        ):
            # User info section
            col1, col2 = st.columns([1, 2])

            with col1:
                st.write("**User Information:**")
                st.write(
                    f"• Last interaction: {user['last_interaction'].strftime('%Y-%m-%d %H:%M')}")
                st.write(f"• Days since last message: {user['days_ago']}")
                st.write(f"• Total messages: {user['total_messages']}")
                st.write(f"• User messages: {user['user_messages']}")
                st.write(f"• AI messages: {user['ai_messages']}")
                st.write(f"• Current stage: {current_stage}")
                st.write(f"• User type: {user_type}")

                # Additional metrics if available
                metrics = user['metrics']
                if metrics.get('profile_complete'):
                    st.write("• ✅ Profile complete")
                else:
                    st.write("• ❌ Profile incomplete")

            with col2:
                st.write("**Quick Actions:**")
                # Add some quick action buttons
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("📊 View Full Profile", key=f"profile_{user['username']}"):
                        st.info(
                            "Feature to view full profile - would redirect to User Profiles tab")
                with col_b:
                    if st.button("💬 Generate Follow-up", key=f"followup_{user['username']}"):
                        st.info(
                            "Feature to generate follow-up - would redirect to Follow-ups tab")
                with col_c:
                    if st.button("📈 View Journey", key=f"journey_{user['username']}"):
                        st.info(
                            "Feature to view journey - would redirect to Client Journey tab")

            # Conversation history section
            st.write("**Conversation History:**")
            conversation_history = user['conversation_history']

            if not conversation_history:
                st.info("No conversation history available")
            else:
                # Options for viewing conversation
                view_options = st.radio(
                    "View options:",
                    ["Last 10 messages", "Last 20 messages", "All messages"],
                    key=f"view_option_{user['username']}",
                    horizontal=True
                )

                # Determine how many messages to show
                if view_options == "Last 10 messages":
                    messages_to_show = conversation_history[-10:]
                elif view_options == "Last 20 messages":
                    messages_to_show = conversation_history[-20:]
                else:
                    messages_to_show = conversation_history

                # Display conversation in a container with scrolling
                with st.container():
                    # Create a scrollable area for the conversation
                    conversation_text = ""
                    for i, msg in enumerate(messages_to_show):
                        sender = "👤 **User**" if msg.get(
                            'type') == 'user' else "🤖 **Shanbot**"
                        timestamp_str = msg.get('timestamp', '')

                        # Format timestamp
                        try:
                            if timestamp_str:
                                ts = datetime.datetime.fromisoformat(
                                    timestamp_str.split('+')[0])
                                formatted_time = ts.strftime("%m/%d %H:%M")
                            else:
                                formatted_time = "No timestamp"
                        except:
                            formatted_time = "Invalid timestamp"

                        message_text = msg.get('text', '(empty message)')

                        # Truncate very long messages for display
                        if len(message_text) > 500:
                            message_text = message_text[:500] + \
                                "... (truncated)"

                        conversation_text += f"{sender} ({formatted_time}):\n{message_text}\n\n"

                    # Display in a text area for easy reading and copying
                    st.text_area(
                        f"Conversation ({len(messages_to_show)} messages):",
                        value=conversation_text,
                        height=400,
                        key=f"conversation_{user['username']}",
                        help="This conversation history is read-only. Use the scroll bar to navigate through messages."
                    )

                # Show conversation stats
                st.write(f"**Conversation Statistics:**")
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    st.metric("Total Messages", len(conversation_history))
                with col_stats2:
                    if conversation_history:
                        first_msg_date = conversation_history[0].get(
                            'timestamp', '')
                        try:
                            first_date = datetime.datetime.fromisoformat(
                                first_msg_date.split('+')[0])
                            conversation_span = (
                                user['last_interaction'] - first_date).days
                            st.metric("Conversation Span",
                                      f"{conversation_span} days")
                        except:
                            st.metric("Conversation Span", "Unknown")
                    else:
                        st.metric("Conversation Span", "0 days")
                with col_stats3:
                    if user['total_messages'] > 0 and conversation_history:
                        response_rate = (
                            user['user_messages'] / user['total_messages']) * 100
                        st.metric("User Response Rate",
                                  f"{response_rate:.1f}%")
                    else:
                        st.metric("User Response Rate", "0%")

            st.markdown("---")
# --- ADDED: Function to display Recent Interactions --- END ---


# Configure the page
st.set_page_config(
    page_title="Shannon Bot Analytics Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load data - This now loads from SQLite (conversations) and JSON (action_items)
if 'analytics_data' not in st.session_state:
    # load_analytics_data now returns (data_dict, path_to_json_for_actions)
    st.session_state.analytics_data, st.session_state.action_items_json_path = load_analytics_data()
    logger.info("Initial data load performed.")
    if not st.session_state.analytics_data.get('conversations'):
        logger.warning("Initial load resulted in no conversation data.")

# Initialize session state for selected page if it doesn't exist
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "Overview"  # Default page

# Sidebar
st.sidebar.title("Analytics Dashboard")

# Add refresh button to sidebar
if st.sidebar.button("🔄 Refresh Data"):
    # Reload all data
    st.session_state.analytics_data, st.session_state.action_items_json_path = load_analytics_data()
    st.success("Data refreshed successfully!")
    st.rerun()  # Rerun to reflect refreshed data across the dashboard

# Navigation
# Update the radio button to use and set session_state.selected_page
page_options = ["Overview", "Client Journey", "User Profiles",
                "Scheduled Follow-ups", "Bulk Review & Send", "Daily Report",
                "Response Review Queue", "Recent Interactions", "AI Data Assistant"]

# Function to update selected_page in session_state


def update_selected_page():
    # Using a temporary key from radio
    st.session_state.selected_page = st.session_state._sidebar_navigation


st.session_state.selected_page = st.sidebar.radio(
    "Navigation",
    options=page_options,
    key='_sidebar_navigation',  # Use a temporary key for the radio's state
    # Callback to update our actual session state variable
    on_change=update_selected_page,
    # Set default based on session state
    index=page_options.index(st.session_state.selected_page)
)

# Main content area
st.title("Shannon Bot Analytics Dashboard")

if st.session_state.selected_page == "Overview":
    display_overview_tab(st.session_state.analytics_data)

elif st.session_state.selected_page == "Client Journey":
    # Assumes this function handles the new data structure
    display_client_journey(st.session_state.analytics_data)

elif st.session_state.selected_page == "User Profiles":
    display_user_profiles_with_bulk_update(
        st.session_state.analytics_data)  # Pass the main data dict

elif st.session_state.selected_page == "Scheduled Follow-ups":
    if st.button(
        "Bulk Generate Follow-ups",
        on_click=lambda: bulk_generate_followups(
            st.session_state.analytics_data,
            get_users_ready_for_followup(
                st.session_state.analytics_data)  # Pass the main data dict
        ),
        type="primary"
    ):
        st.rerun()  # Rerun to show newly generated messages if any
    display_scheduled_followups_tab(
        st.session_state.analytics_data)  # Pass the main data dict

elif st.session_state.selected_page == "Bulk Review & Send":
    # This function might need review for data structure changes
    display_bulk_review_and_send()

elif st.session_state.selected_page == "Daily Report":
    # Pass the main data dict
    display_daily_report(st.session_state.analytics_data)

elif st.session_state.selected_page == "Response Review Queue":
    display_response_review_queue()  # Call the new function

elif st.session_state.selected_page == "Recent Interactions":
    display_recent_interactions(
        st.session_state.analytics_data)  # Call the new function

elif st.session_state.selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("AI Data Assistant feature coming soon!")
