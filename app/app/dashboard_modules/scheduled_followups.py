import streamlit as st
import datetime
from typing import Dict, Any, List, Tuple
import google.generativeai as genai
import os
import json
import google.oauth2.service_account
import googleapiclient.discovery
import logging
from googleapiclient.discovery import build

# Configure Gemini
GEMINI_API_KEY = "AIzaSyCrYZwENVEhfo0IF6puWyQaYlFW1VRWY-k"
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.0-flash')

# Google Sheets configuration
SHEETS_CREDENTIALS_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\sheets_credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"

# Set up logging
logger = logging.getLogger(__name__)


def get_user_category(user_data: Dict[str, Any]) -> str:
    """Determine the user's current category/stage"""
    metrics = user_data.get('metrics', {})

    # Check for journey stage indicators in order
    if metrics.get('is_paying_client'):
        return "Paying Client"
    elif metrics.get('trial_week_4'):
        return "Trial Week 4"
    elif metrics.get('trial_week_3'):
        return "Trial Week 3"
    elif metrics.get('trial_week_2'):
        return "Trial Week 2"
    elif metrics.get('trial_week_1'):
        return "Trial Week 1"
    elif metrics.get('trial_offer_made'):
        return "Topic 5 (Trial Offer Made)"
    elif metrics.get('topic4_completed'):
        return "Topic 4"
    elif metrics.get('topic3_completed'):
        return "Topic 3"
    elif metrics.get('topic2_completed'):
        return "Topic 2"
    else:
        return "Topic 1"


def get_user_topics(user_data: Dict[str, Any]) -> List[str]:
    """Get conversation topics from user's analytics data"""
    try:
        client_analysis = user_data.get(
            'metrics', {}).get('client_analysis', {})
        topics = client_analysis.get('conversation_topics', [])
        metrics = user_data.get('metrics', {})

        # Filter out empty or None topics
        filtered_topics = [
            topic for topic in topics if topic and not topic.startswith('**')]

        # Add Topic 5 if not already present
        topic_5 = "Topic 5 - Enquire about leads fitness journey - offer 1 month trial"
        if topic_5 not in filtered_topics:
            filtered_topics.append(topic_5)

        # Add appropriate trial week or paying client messages based on metrics
        current_time = datetime.datetime.now().time()
        morning_message = "Monday Morning: Goooooood Morning! Ready for the week?"
        evening_message = "Wednesday Night: Heya! Hows your week going?"

        if metrics.get('is_paying_client'):
            filtered_topics.extend([
                f"Paying Client - {morning_message}",
                f"Paying Client - {evening_message}"
            ])
        elif metrics.get('trial_week_4'):
            filtered_topics.extend([
                f"Trial Week 4 - {morning_message}",
                f"Trial Week 4 - {evening_message}"
            ])
        elif metrics.get('trial_week_3'):
            filtered_topics.extend([
                f"Trial Week 3 - {morning_message}",
                f"Trial Week 3 - {evening_message}"
            ])
        elif metrics.get('trial_week_2'):
            filtered_topics.extend([
                f"Trial Week 2 - {morning_message}",
                f"Trial Week 2 - {evening_message}"
            ])
        elif metrics.get('trial_week_1'):
            filtered_topics.extend([
                f"Trial Week 1 - {morning_message}",
                f"Trial Week 1 - {evening_message}"
            ])

        return filtered_topics
    except Exception:
        return ["Topic 5 - Enquire about leads fitness journey - offer 1 month trial"]


def get_topic_for_category(category: str, user_data: Dict[str, Any]) -> str:
    """Get the appropriate topic based on user category"""
    # For Topic 5 and Trial Period, use hardcoded topics
    if category == "Topic 5 (Trial Offer Made)":
        return "Topic 5 - Enquire about leads fitness journey - offer 1 month trial"
    elif category == "Trial Week 1":
        current_time = datetime.datetime.now().time()
        if current_time.hour < 12:  # Morning
            return "Trial Week 1 - Monday Morning: Goooooood Morning! Ready for the week?"
        else:  # Evening
            return "Trial Week 1 - Wednesday Night: Heya! Hows your week going?"
    elif category == "Trial Week 2":
        current_time = datetime.datetime.now().time()
        if current_time.hour < 12:  # Morning
            return "Trial Week 2 - Monday Morning: Goooooood Morning! Ready for the week?"
        else:  # Evening
            return "Trial Week 2 - Wednesday Night: Heya! Hows your week going?"
    elif category == "Trial Week 3":
        current_time = datetime.datetime.now().time()
        if current_time.hour < 12:  # Morning
            return "Trial Week 3 - Monday Morning: Goooooood Morning! Ready for the week?"
        else:  # Evening
            return "Trial Week 3 - Wednesday Night: Heya! Hows your week going?"
    elif category == "Trial Week 4":
        current_time = datetime.datetime.now().time()
        if current_time.hour < 12:  # Morning
            return "Trial Week 4 - Monday Morning: Goooooood Morning! Ready for the week?"
        else:  # Evening
            return "Trial Week 4 - Wednesday Night: Heya! Hows your week going?"
    elif category == "Paying Client":
        current_time = datetime.datetime.now().time()
        if current_time.hour < 12:  # Morning
            return "Paying Client - Monday Morning: Goooooood Morning! Ready for the week?"
        else:  # Evening
            return "Paying Client - Wednesday Night: Heya! Hows your week going?"

    # For all other topics, get from user's analytics data
    client_analysis = user_data.get('metrics', {}).get('client_analysis', {})
    conversation_topics = client_analysis.get('conversation_topics', [])

    # Filter out empty or None topics
    available_topics = [
        topic for topic in conversation_topics if topic and not topic.startswith('**')]

    # Try to find a topic that matches the current category
    if available_topics:
        for topic in available_topics:
            if category in topic:  # e.g., if "Topic 4" is in the topic string
                return topic

    # If no matching topic found, return a default message
    return f"No specific topic found for {category}"


def generate_follow_up_message(conversation_history: List[Dict[str, Any]], topic: str, days_since_last=None) -> str:
    """Generate a follow-up message using Gemini with timing context and fallback models."""
    models = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-2.0-flash-thinking-exp-01-21'
    ]

    # Format conversation history without f-strings
    history_text = ""
    for msg in conversation_history:
        sender = 'User' if msg.get('type') == 'user' else 'Shannon'
        text = msg.get('text', '')
        history_text += f"{sender}: {text}\n"

    # Create timing-aware prompt
    timing_context = ""
    if days_since_last:
        if days_since_last <= 2:
            timing_context = f"It's been {days_since_last} days since they last messaged - this is a recent follow-up, so keep it casual and direct."
        elif days_since_last <= 7:
            timing_context = f"It's been {days_since_last} days since they last messaged - acknowledge the gap briefly and re-engage warmly."
        elif days_since_last <= 14:
            timing_context = f"It's been {days_since_last} days (about {days_since_last//7} weeks) since they last messaged - acknowledge the longer gap and restart the conversation gently."
        else:
            timing_context = f"It's been {days_since_last} days (over {days_since_last//7} weeks) since they last messaged - this is a re-engagement message, be warm and understanding about the gap."

    prompt = f"""You are Shannon, a casual Australian fitness coach reaching out to someone on Instagram.

    TIMING CONTEXT: {timing_context}

    TOPIC TO DISCUSS: {topic}

    PREVIOUS CONVERSATION:
    {history_text}

    Create a casual, friendly follow-up message that:
    - Acknowledges the time gap appropriately (if relevant)
    - Transitions naturally into the topic
    - Feels personal and conversational
    - Is between 1-15 words total
    - Uses Shannon's relaxed Australian tone

    Examples by timing:
    - 2-3 days: "hey! been thinking about [topic]..."
    - 1 week: "heya! how's things been? was just thinking about [topic]..."
    - 2+ weeks: "hey there! hope you've been well! was just thinking about [topic]..."

    Generate ONLY the message, no other text:"""

    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if '429' in str(e):
                continue  # Try next model
            st.error(f"Error generating message with {model_name}: {e}")
            return None
    st.error("All Gemini models are over quota or failed. Please try again later.")
    return None


def get_user_bio(user_data: Dict[str, Any]) -> str:
    """Extract a small bio/summary for the user from analytics data."""
    metrics = user_data.get('metrics', {})
    # Always get ig_username
    ig_username = metrics.get('ig_username', 'Unknown User')

    client_analysis = metrics.get('client_analysis', {})
    # This can be a dict, string, or None
    profile_bio_data = client_analysis.get('profile_bio')

    name_component = ""
    interests_component = ""
    raw_bio_component = ""

    if isinstance(profile_bio_data, dict):
        person_name = profile_bio_data.get('PERSON NAME')
        if person_name and isinstance(person_name, str) and person_name.strip():
            name_component = f" | Name: {person_name.strip()}"

        interests_list = profile_bio_data.get('INTERESTS')
        if interests_list and isinstance(interests_list, list):
            # Filter for string items and remove empty strings before joining
            valid_interests = [str(i).strip() for i in interests_list if isinstance(
                i, (str, int, float)) and str(i).strip()]
            if valid_interests:
                interests_component = f" | Interests: {', '.join(valid_interests)}"
    elif isinstance(profile_bio_data, str) and profile_bio_data.strip():
        raw_bio_component = f" | Bio: {profile_bio_data.strip()}"

    summary = f"User: {ig_username}{name_component}{interests_component}{raw_bio_component}"

    # If no extra details were added beyond ig_username
    if not name_component and not interests_component and not raw_bio_component:
        summary = f"User: {ig_username} (No additional bio details)"

    return summary


def bulk_generate_followups(analytics_data: Dict[str, Any], followup_data: Dict[str, Any]):
    """Generate follow-ups for all users ready and store in session state."""
    bulk = []
    # To avoid issues if a user is in followup_data but somehow not in analytics_data main/conversations keys as expected
    processed_usernames = set()

    for responder_type in ['high_responders', 'medium_responders', 'low_responders']:
        # user_info is from get_users_ready_for_followup
        for user_info in followup_data[responder_type]:
            username = user_info['username']
            if username in processed_usernames:
                continue

            user_data = None
            # Try to get user_data from top-level first
            if username in analytics_data and isinstance(analytics_data[username], dict):
                user_data = analytics_data[username]
            # If not found at top-level, try under 'conversations'
            elif 'conversations' in analytics_data and isinstance(analytics_data.get('conversations'), dict) and \
                 username in analytics_data['conversations'] and isinstance(analytics_data['conversations'][username], dict):
                user_data = analytics_data['conversations'][username]

            if not user_data:
                st.warning(
                    f"Could not find data for user '{username}' in analytics_data. Skipping bulk generation for this user.")
                # Mark as processed to avoid repeated warnings
                processed_usernames.add(username)
                continue

            metrics = user_data.get('metrics', {})
            if not isinstance(metrics, dict):
                st.warning(
                    f"Metrics for user '{username}' is not a dictionary. Skipping bulk generation.")
                processed_usernames.add(username)
                continue

            user_category = get_user_category(user_data)
            topic = get_topic_for_category(user_category, user_data)
            conversation_history = metrics.get('conversation_history', [])
            # Get timing information from user_info
            days_since_last = user_info.get('days_since_last_message', None)
            message = generate_follow_up_message(
                conversation_history, topic, days_since_last)
            bio = get_user_bio(user_data)
            bulk.append({
                'username': username,
                'bio': bio,
                'topic': topic,
                'message': message,
                'user_category': user_category
            })
            processed_usernames.add(username)
    st.session_state.bulk_followups = bulk


def display_bulk_review_and_send():
    """Display the bulk review and send page."""
    st.header("📦 Bulk Review & Send Follow-ups")
    if 'bulk_followups' not in st.session_state or not st.session_state.bulk_followups:
        st.info("No bulk follow-ups generated yet. Go to Scheduled Follow-ups and click 'Bulk Generate Follow-ups'.")
        return
    edited_messages = []
    for i, user in enumerate(st.session_state.bulk_followups):
        with st.expander(f"{user['username']} - {user['user_category']}"):
            st.write(f"**Bio:** {user['bio']}")
            st.write(f"**Topic:** {user['topic']}")
            msg = st.text_area("Edit message if needed:",
                               value=user['message'], key=f"bulkmsg_{i}", height=100)
            # --- Determine checkin_type for bulk --- START ---
            checkin_type = None
            topic_lower = user['topic'].lower()
            if "monday morning" in topic_lower:
                checkin_type = 'monday'
            elif "wednesday night" in topic_lower:
                checkin_type = 'wednesday'
            # --- Determine checkin_type for bulk --- END ---
            edited_messages.append({
                'username': user['username'],
                'bio': user['bio'],
                'topic': user['topic'],
                'message': msg,
                'user_category': user['user_category'],
                'checkin_type': checkin_type
            })
    if st.button("🚀 Bulk Send All", type="primary"):
        # Add all messages to the queue
        if 'message_queue' not in st.session_state:
            st.session_state.message_queue = []
        for user in edited_messages:
            st.session_state.message_queue.append({
                'username': user['username'],
                'message': user['message'],
                'topic': user['topic'],
                'queued_time': datetime.datetime.now().isoformat(),
                'checkin_type': user['checkin_type']
            })
        st.success(
            "All messages queued for sending! Follow-up manager will process these messages.")
        st.session_state.bulk_followups = []


def display_user_followup(user: Dict[str, Any], analytics_data: Dict[str, Any], message_queue: List[Dict[str, Any]]):
    """Display user follow-up information with message generation and sending capabilities"""
    username = user['username']
    user_data = analytics_data['conversations'][username]
    metrics = user_data.get('metrics', {})

    # Get user category
    user_category = get_user_category(user_data)

    # Get appropriate topic based on category and user data
    current_topic = get_topic_for_category(user_category, user_data)

    with st.expander(f"{username} - {user['days_since_last_message']} days since last message - {user_category}"):
        info_col, history_col = st.columns([1, 1])

        with info_col:
            st.write("### User Information")
            st.write(f"**Response count:** {user['response_count']}")
            st.write(
                f"**Last message:** {user['last_message_time'].strftime('%Y-%m-%d %H:%M')}")
            st.write(f"**Current Stage:** {user_category}")

            st.write("### Current Topic")
            st.info(current_topic)

            if st.button(f"Generate Message", key=f"gen_{username}"):
                with st.spinner("Generating message..."):
                    conversation_history = metrics.get(
                        'conversation_history', [])
                    message = generate_follow_up_message(
                        conversation_history, current_topic, user.get('days_since_last_message', None))
                    user['generated_message'] = message
                    user['selected_topic'] = current_topic
                    st.success("Message generated!")

        with history_col:
            st.write("### Conversation History")
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                st.write("Last 5 messages:")
                for msg in conversation_history[-5:]:
                    sender = "User" if msg.get('type') == 'user' else "Shannon"
                    st.write(f"**{sender}:** {msg.get('text', '')}")
            else:
                st.info("No conversation history available")

        st.write("### Follow-up Message")
        if 'generated_message' in user:
            edited_message = st.text_area(
                "Edit message if needed:",
                value=user['generated_message'],
                key=f"edit_{username}",
                height=100
            )

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("Regenerate", key=f"regen_{username}"):
                    with st.spinner("Regenerating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic, user.get('days_since_last_message', None))
                        user['generated_message'] = message
                        user['selected_topic'] = current_topic
                        st.success("Message regenerated!")

            with col2:
                if st.button("Queue Message", key=f"queue_{username}"):
                    # --- Determine checkin_type for single queue --- START ---
                    checkin_type = None
                    topic_lower = current_topic.lower()
                    if "monday morning" in topic_lower:
                        checkin_type = 'monday'
                    elif "wednesday night" in topic_lower:
                        checkin_type = 'wednesday'
                    # --- Determine checkin_type for single queue --- END ---
                    message_queue.append({
                        'username': username,
                        'message': edited_message,
                        'topic': current_topic,
                        'queued_time': datetime.datetime.now().isoformat(),
                        'checkin_type': checkin_type
                    })
                    st.success(f"Message queued for {username}")

            if edited_message != user['generated_message']:
                user['generated_message'] = edited_message
                st.success("Message updated!")
        else:
            st.warning("Click 'Generate Message' to create a message")


def should_progress_to_next_topic(user_data: Dict[str, Any]) -> bool:
    """Determine if a user should progress to the next topic based on response level and time."""
    metrics = user_data.get('metrics', {})
    conversation_history = metrics.get('conversation_history', [])

    if not conversation_history:
        return False

    # Get last message time
    last_message = conversation_history[-1]
    try:
        last_message_time = datetime.datetime.fromisoformat(
            last_message.get('timestamp', '').split('+')[0])
    except (ValueError, AttributeError):
        return False

    # Check if 24 hours have passed since last message
    time_since_last_message = datetime.datetime.now() - last_message_time
    if time_since_last_message.total_seconds() < 86400:  # 24 hours in seconds
        return False

    # Get number of responses and corresponding wait time
    num_responses = metrics.get('user_messages', 0)
    wait_days = get_response_level_wait_time(num_responses)

    # Check if enough time has passed based on response level
    return time_since_last_message.days >= wait_days


def verify_trial_signup(instagram_username: str) -> Tuple[bool, bool]:
    """
    Verify if a user has signed up for the trial by checking the onboarding Google Sheet.
    Also checks if they are a paying client.
    Returns tuple of (is_trial, is_paying)
    """
    try:
        # Use the same credentials and spreadsheet as the onboarding flow
        creds = google.oauth2.service_account.Credentials.from_service_account_file(
            SHEETS_CREDENTIALS_PATH, scopes=SCOPES)
        service = googleapiclient.discovery.build(
            'sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        result = sheet.values().get(
            spreadsheetId=ONBOARDING_SPREADSHEET_ID,
            range=ONBOARDING_RANGE_NAME
        ).execute()

        values = result.get('values', [])
        if not values:
            logger.error("No data found in onboarding sheet")
            return False, False

        # Get the header row to understand column positions
        headers = values[0]
        logger.info(f"Found headers in sheet: {headers}")

        # Look for Instagram Name and Paying Client columns
        instagram_col = next(
            (i for i, h in enumerate(headers) if h == "Instagram Name"), None)
        paying_col = next(
            (i for i, h in enumerate(headers) if h == "Paying Client"), None)

        if instagram_col is None:
            logger.error("'Instagram Name' column not found in sheet")
            return False, False

        # Search for the Instagram username
        normalized_username = instagram_username.strip().lower()
        logger.info(f"Looking for username: {normalized_username}")

        for row in values[1:]:  # Skip header row
            if instagram_col < len(row):
                sheet_username = row[instagram_col].strip().lower()
                if normalized_username == sheet_username:
                    # Check if they're a paying client
                    is_paying = False
                    if paying_col is not None and paying_col < len(row):
                        # True if any text exists
                        is_paying = bool(row[paying_col].strip())
                    logger.info(
                        f"Found {instagram_username} in sheet - Trial: True, Paying: {is_paying}")
                    return True, is_paying

        logger.info(
            f"Username {instagram_username} not found in onboarding sheet")
        return False, False

    except Exception as e:
        logger.error(f"Error verifying trial signup: {e}")
        logger.error(f"Full error details: {str(e)}")
        return False, False


def progress_user_to_next_topic(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Progress user to next topic if conditions are met."""
    metrics = user_data.get('metrics', {})

    # Check for signup regardless of current stage
    instagram_username = metrics.get('ig_username')
    if instagram_username and not metrics.get('trial_week_1') and not metrics.get('is_paying_client'):
        # Verify if they've signed up
        if verify_trial_signup(instagram_username):
            logger.info(
                f"Verified signup for {instagram_username}, progressing to Trial Week 1")
            metrics['trial_week_1'] = True
            user_data['metrics'] = metrics
            return user_data

    # Only continue with normal progression if they haven't signed up
    if not should_progress_to_next_topic(user_data):
        return user_data

    if metrics.get('is_paying_client') or any(metrics.get(f'trial_week_{i}') for i in range(2, 5)):
        return user_data

    # Normal topic progression
    if not metrics.get('topic2_completed'):
        metrics['topic2_completed'] = True
    elif not metrics.get('topic3_completed'):
        metrics['topic3_completed'] = True
    elif not metrics.get('topic4_completed'):
        metrics['topic4_completed'] = True
    elif not metrics.get('trial_offer_made'):
        metrics['trial_offer_made'] = True

    user_data['metrics'] = metrics
    return user_data


def save_analytics_data(analytics_data: Dict[str, Any], analytics_file: str) -> bool:
    """Save updated analytics data back to file."""
    try:
        with open(analytics_file, 'w') as f:
            json.dump(analytics_data, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving analytics data: {e}")
        return False


def check_sheet_for_signups(analytics_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Check Google Sheet for new signups and paying clients, update dashboard data accordingly.
    Returns tuple of (updated_data, was_updated)
    """
    try:
        data_updated = False

        # Create a lookup dictionary of dashboard usernames
        dashboard_users = {}
        for username, user_data in analytics_data.get('conversations', {}).items():
            metrics = user_data.get('metrics', {})
            ig_username = metrics.get('ig_username', '').strip().lower()
            if ig_username:
                dashboard_users[ig_username] = (username, user_data)

        # Create progress bar
        total_users = len(dashboard_users)
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Check each dashboard user against the sheet
        for idx, (ig_username, (username, user_data)) in enumerate(dashboard_users.items(), 1):
            # Update progress
            progress = int((idx / total_users) * 100)
            progress_bar.progress(progress)
            status_text.text(
                f"Checking user {idx} of {total_users}: {ig_username}")

            is_trial, is_paying = verify_trial_signup(ig_username)
            metrics = user_data.get('metrics', {})

            if is_paying and not metrics.get('is_paying_client'):
                # Update to paying client
                logger.info(f"Updating {ig_username} to paying client status")
                metrics['is_paying_client'] = True
                metrics['trial_week_1'] = False  # Remove trial status
                metrics['trial_week_2'] = False
                metrics['trial_week_3'] = False
                metrics['trial_week_4'] = False
                analytics_data['conversations'][username]['metrics'] = metrics
                data_updated = True
            elif is_trial and not metrics.get('trial_week_1') and not metrics.get('is_paying_client'):
                # Update to trial if not already in trial and not paying
                logger.info(f"Updating {ig_username} to trial status")
                metrics['trial_week_1'] = True
                analytics_data['conversations'][username]['metrics'] = metrics
                data_updated = True

        # Clear progress bar and status after completion
        progress_bar.empty()
        status_text.empty()

        return analytics_data, data_updated

    except Exception as e:
        logger.error(f"Error checking sheet for signups: {e}")
        logger.error(f"Full error details: {str(e)}")
        return analytics_data, False


def display_scheduled_followups(analytics_data: Dict[str, Any], analytics_file: str):
    """Display the scheduled follow-ups section"""
    st.header("📅 Scheduled Follow-ups")

    # Check for normal topic progression for all users
    data_updated = False
    for username, user_data in analytics_data.get('conversations', {}).items():
        updated_user_data = progress_user_to_next_topic(user_data)
        if updated_user_data != user_data:
            analytics_data['conversations'][username] = updated_user_data
            data_updated = True

    # Save changes if any progressions occurred
    if data_updated:
        if save_analytics_data(analytics_data, analytics_file):
            st.success("Users progressed to next topics where applicable")
        else:
            st.error("Failed to save topic progression changes")

    # Initialize message queue in session state if not exists
    if 'message_queue' not in st.session_state:
        st.session_state.message_queue = []

    # Get users ready for follow-up
    followup_data = get_users_ready_for_followup(analytics_data)

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Ready for Follow-up", followup_data['total_count'])
    with col2:
        st.metric("High Responders Ready (48h)", len(
            followup_data['high_responders']))
    with col3:
        st.metric("Medium Responders Ready (5d)", len(
            followup_data['medium_responders']))
    with col4:
        st.metric("Low Responders Ready (7d)", len(
            followup_data['low_responders']))

    # Display queued messages if any exist
    if st.session_state.message_queue:
        st.subheader("📬 Queued Messages")
        st.write(
            f"{len(st.session_state.message_queue)} messages queued for sending")

        with st.expander("View Queued Messages"):
            for msg in st.session_state.message_queue:
                st.write(f"**To:** {msg['username']}")
                st.write(f"**Topic:** {msg['topic']}")
                st.write(f"**Message:** {msg['message']}")
                st.write("---")

        if st.button("🚀 Send All Queued Messages", type="primary"):
            if save_followup_queue(st.session_state.message_queue, analytics_file):
                st.success(
                    "Messages queued for sending! Follow-up manager will process these messages.")
                st.session_state.message_queue = []
            else:
                st.error("Failed to queue messages for sending")

    # Create tabs for different response levels
    high_tab, medium_tab, low_tab = st.tabs([
        "🟢 High Responders",
        "🟡 Medium Responders",
        "🟠 Low Responders"
    ])

    with high_tab:
        if followup_data['high_responders']:
            for user in followup_data['high_responders']:
                display_user_followup(
                    user, analytics_data, st.session_state.message_queue)
        else:
            st.info("No high responders ready for follow-up")

    with medium_tab:
        if followup_data['medium_responders']:
            for user in followup_data['medium_responders']:
                display_user_followup(
                    user, analytics_data, st.session_state.message_queue)
        else:
            st.info("No medium responders ready for follow-up")

    with low_tab:
        if followup_data['low_responders']:
            for user in followup_data['low_responders']:
                display_user_followup(
                    user, analytics_data, st.session_state.message_queue)
        else:
            st.info("No low responders ready for follow-up")


def get_user_sheet_details(ig_username: str) -> dict:
    """Get user details from Google Sheet"""
    try:
        # Initialize the Sheets API
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(
            SHEETS_CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        service = build('sheets', 'v4', credentials=credentials)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=ONBOARDING_SPREADSHEET_ID,
            range=ONBOARDING_RANGE_NAME
        ).execute()
        values = result.get('values', [])

        if not values:
            logger.warning('No data found in sheet')
            return {}

        # Find the header row (first row)
        headers = values[0]

        # Find the row with matching Instagram username
        for row in values[1:]:  # Skip header row
            # Ensure row has enough columns
            row_data = row + [''] * (len(headers) - len(row))
            row_dict = dict(zip(headers, row_data))

            # Check if this is the user we're looking for
            if row_dict.get('Instagram Username', '').lower() == ig_username.lower():
                return row_dict

        logger.warning(f'No data found for Instagram username: {ig_username}')
        return {}

    except Exception as e:
        logger.error(f'Error getting sheet data: {str(e)}')
        return {}
