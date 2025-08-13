"""
Follow-up Utilities Module
This file contains shared functions used by both the main dashboard
and the Follow-up Manager to avoid circular imports.
"""

import streamlit as st
import logging
from datetime import datetime
import json
import os

# Assuming these imports are correct based on dashboard.py structure
from shared_utils import get_user_topics, call_gemini_with_retry_sync, GEMINI_MODEL_PRO, GEMINI_API_KEY
from scheduled_followups import get_user_category, get_topic_for_category
from dashboard_sqlite_utils import add_message_to_history


logger = logging.getLogger(__name__)

# --- Functions moved from dashboard.py ---


def get_response_level_wait_time(num_responses):
    """Return wait time in days based on response level"""
    if num_responses >= 20:  # High responder (green)
        return 2  # 48 hours
    elif num_responses >= 11:  # Medium responder (yellow)
        return 5  # 5 days
    else:  # Low responder (orange/red)
        return 7  # 7 days


def get_users_ready_for_followup(analytics_data: dict):
    """Determine which users are ready for follow-up based on their response level, matching user_profiles logic."""
    ready_for_followup = {
        'high_responders': [],
        'medium_responders': [],
        'low_responders': [],
        'total_count': 0
    }
    current_time = datetime.now()
    known_non_user_keys = ["conversations",
                           "action_items", "conversation_history"]
    processed_usernames = set()

    def process_user(username, user_data):
        if username in processed_usernames:
            return
        processed_usernames.add(username)
        metrics = user_data.get('metrics', {})
        if not metrics:
            return
        last_interaction_ts_str = metrics.get('last_interaction_timestamp')
        last_message_time = None
        if last_interaction_ts_str:
            try:
                last_message_time = datetime.fromisoformat(
                    last_interaction_ts_str.split('+')[0])
            except (ValueError, AttributeError):
                pass
        if not last_message_time:
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                try:
                    last_msg_in_history = conversation_history[-1]
                    last_message_time = datetime.fromisoformat(
                        last_msg_in_history.get('timestamp', '').split('+')[0])
                except (IndexError, ValueError, AttributeError):
                    pass
        if not last_message_time:
            return
        num_responses = metrics.get('user_messages', 0)
        wait_days = get_response_level_wait_time(num_responses)
        time_since_last_message = current_time - last_message_time
        if time_since_last_message.days >= wait_days:
            user_info = {
                'username': username,
                'days_since_last_message': time_since_last_message.days,
                'response_count': num_responses,
                'last_message_time': last_message_time,
                'metrics': metrics  # Add metrics for later use
            }
            if num_responses >= 20:
                ready_for_followup['high_responders'].append(user_info)
            elif num_responses >= 11:
                ready_for_followup['medium_responders'].append(user_info)
            else:
                ready_for_followup['low_responders'].append(user_info)
            ready_for_followup['total_count'] += 1

    nested_conversations = analytics_data.get('conversations')
    if isinstance(nested_conversations, dict):
        for username, user_data in nested_conversations.items():
            process_user(username, user_data)
    return ready_for_followup


def generate_follow_up_message(conversation_history, topic, days_since_last=None):
    """Generate a follow-up message using Gemini with timing context."""
    if not GEMINI_API_KEY or GEMINI_API_KEY in ["YOUR_GEMINI_API_KEY", "your_gemini_api_key_here"]:
        st.error("Gemini API key not available.")
        return "[Gemini not available]"
    try:
        formatted_history = ""
        for msg in conversation_history:
            sender = "User" if msg.get('type') == 'user' else "Shannon"
            formatted_history += f"{sender}: {msg.get('text', '')}\n"

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
        {formatted_history}

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

        response_text = call_gemini_with_retry_sync(GEMINI_MODEL_PRO, prompt)
        return response_text
    except Exception as e:
        st.error(f"Error generating message: {e}")
        logger.error(f"Gemini message generation error: {e}", exc_info=True)
        return None


def save_followup_queue():
    """Save the follow-up queue to a file."""
    queue_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\followup_queue.json"
    try:
        with open(queue_file, 'w') as f:
            json.dump({
                'messages': st.session_state.get('message_queue', []),
                'created_at': datetime.now().isoformat()
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

    # --- REVISED: Check session state for a bulk-generated message ---
    session_state_msg_key = f"generated_message_{username}"
    session_state_topic_key = f"selected_topic_{username}"

    # If a message exists in session state, load it into the text area
    if session_state_msg_key in st.session_state:
        user_followup_info['generated_message'] = st.session_state[session_state_msg_key]
    if session_state_topic_key in st.session_state:
        user_followup_info['selected_topic'] = st.session_state[session_state_topic_key]

    # Get user_data by checking the 'conversations' part of all_analytics_data
    user_container = all_analytics_data.get('conversations', {}).get(username)
    if not user_container or 'metrics' not in user_container:
        st.error(f"Could not find data for user '{username}'.")
        return
    metrics = user_container['metrics']
    with st.expander(f"{username} - {user_followup_info['days_since_last_message']} days since last message"):
        info_col, history_col = st.columns([1, 1])
        with info_col:
            st.write("### User Information")
            st.write(
                f"**Response count:** {user_followup_info['response_count']}")
            st.write(
                f"**Last message:** {user_followup_info['last_message_time'].strftime('%Y-%m-%d %H:%M')}")
            available_topics = get_user_topics(metrics)
            if not available_topics:
                st.warning("No conversation topics available for this user")
                current_topic = "General catch-up"
            else:
                user_category = get_user_category(metrics)
                current_topic = get_topic_for_category(user_category, metrics)
                st.write("### Current Topic")
                st.info(current_topic)
                if st.button(f"Generate Message", key=f"gen_{username}"):
                    with st.spinner("Generating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic, user_followup_info.get('days_since_last_message', None))
                    if message:
                        user_followup_info['generated_message'] = message
                        user_followup_info['selected_topic'] = current_topic
                        st.success("Message generated!")
                        st.rerun()
                    else:
                        st.error("Failed to generate message.")
        with history_col:
            st.write("### Conversation History")
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                st.write("Last 5 messages:")
                for msg in conversation_history[-5:]:
                    sender = "User" if msg.get(
                        'type') == 'user' else "Shannon"
                    st.write(f"**{sender}:** {msg.get('text', '')}")
            else:
                st.info("No conversation history available")
        st.write("### Follow-up Message")
        if 'generated_message' in user_followup_info:
            # Create a text area for editing the message
            edited_message = st.text_area(
                "Edit message if needed:",
                value=user_followup_info['generated_message'],
                key=f"edit_{username}",
                height=100
            )

            # --- REVISED: Action buttons ---
            col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
            with col1:
                # Add a regenerate button
                if st.button("Regenerate", key=f"regen_{username}"):
                    with st.spinner("Regenerating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic, user_followup_info.get('days_since_last_message', None))
                        if message:
                            # Update session state directly
                            st.session_state[session_state_msg_key] = message
                            st.success("Message regenerated!")
                            st.rerun()
                        else:
                            st.error("Failed to regenerate message.")

            with col2:
                # Add queue message button
                if st.button("Queue", key=f"queue_{username}", type="primary"):
                    queue_message_for_followup(
                        username, edited_message, current_topic)

                    # Clean up session state for this user now that it's queued
                    if session_state_msg_key in st.session_state:
                        del st.session_state[session_state_msg_key]
                    if session_state_topic_key in st.session_state:
                        del st.session_state[session_state_topic_key]

                    st.success(f"Message queued for {username}")
                    st.rerun()

            with col3:
                # Add a clear button
                if st.button("Clear", key=f"clear_{username}"):
                    # Clean up session state for this user
                    if session_state_msg_key in st.session_state:
                        del st.session_state[session_state_msg_key]
                    if session_state_topic_key in st.session_state:
                        del st.session_state[session_state_topic_key]

                    st.info(f"Cleared generated message for {username}")
                    st.rerun()

            # Update the stored message in session state if edited
            if edited_message != user_followup_info.get('generated_message'):
                st.session_state[session_state_msg_key] = edited_message
                # Rerun to ensure the change is visually confirmed if needed, or just let it be for the next action
                # st.rerun()
        else:
            st.info("Click 'Generate Message' to create a new follow-up.")
