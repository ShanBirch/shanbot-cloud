import streamlit as st
# import requests # No longer needed
import json
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict  # Added for easier category management
import random  # For random message selection
import re  # Added for regular expressions
from typing import Dict, Any
import numpy as np
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from conversation_analytics_integration import analytics

# Analytics file path
ANALYTICS_FILE_PATH = "C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\analytics_data.json"

# Define constants
ACTIVE_WINDOW = 3600  # 1 hour in seconds

# Define helper functions


def ensure_timezone(dt):
    """Ensure a datetime object has timezone information"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_timestamp(timestamp_str):
    """Parse timestamp string to timezone-aware datetime"""
    try:
        if isinstance(timestamp_str, str):
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return ensure_timezone(dt)
        return ensure_timezone(timestamp_str)
    except (ValueError, TypeError):
        return None


def is_user_active(last_active_time):
    """Check if a user is active based on their last active time"""
    if not last_active_time:
        return False

    now = datetime.now(timezone.utc)
    last_active_dt = parse_timestamp(last_active_time)

    if not last_active_dt:
        return False

    time_diff = now - last_active_dt
    return time_diff.total_seconds() < ACTIVE_WINDOW


# Set page config with explicit sidebar settings
st.set_page_config(
    page_title="Shanbot Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Add custom CSS to ensure sidebar visibility
st.markdown("""
    <style>
    [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
        width: 300px;
    }
    [data-testid="stSidebar"][aria-expanded="false"] > div:first-child {
        width: 300px;
        margin-left: -300px;
    }
    </style>
    """, unsafe_allow_html=True)


def should_follow_up(conversation_data):
    """Determine if we should follow up based on conversation state."""
    # Extract metrics
    conv_metrics = conversation_data.get('metrics', {})

    # Get the last message timestamp
    last_message_time = conv_metrics.get('last_message_time')
    if not last_message_time:
        return False

    # Convert to datetime
    try:
        last_dt = datetime.fromisoformat(last_message_time)
    except ValueError:
        # Handle non-ISO format dates
        try:
            last_dt = datetime.strptime(
                last_message_time, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return False

    # Get current time
    now = datetime.now()

    # Calculate time difference
    time_diff = now - last_dt

    # Debug logging
    print(f"DEBUG - ID: {conversation_data.get('id', 'unknown')}, Last Message: {last_dt}, Diff: {time_diff}, Active: {time_diff.days >= 2}")

    # If no message for 2 days, suggest follow-up
    return time_diff.days >= 2


def analyze_engagement_level(metrics):
    """Analyze the engagement level of a conversation"""
    score = 0
    factors = []

    # Message quantity analysis
    total_messages = metrics.get("total_messages", 0)
    user_messages = metrics.get("user_messages", 0)

    if user_messages >= 5:
        score += 3
        factors.append("High message count")
    elif user_messages >= 3:
        score += 2
        factors.append("Moderate message count")
    elif user_messages >= 1:
        score += 1
        factors.append("Low message count")

    # Response quality analysis
    if metrics.get("user_responses_to_questions", 0) > 0:
        score += 2
        factors.append("Responded to questions")

    # Topic interest analysis
    if metrics.get("fitness_topic_user_initiated"):
        score += 3
        factors.append("User initiated fitness talk")
    elif metrics.get("fitness_topic_ai_initiated"):
        score += 1
        factors.append("Responded to fitness topic")

    # Calculate engagement level
    if score >= 7:
        engagement_level = "HIGH"
    elif score >= 4:
        engagement_level = "MEDIUM"
    else:
        engagement_level = "LOW"

    return {
        "score": score,
        "level": engagement_level,
        "factors": factors
    }


def get_smart_follow_up_timing(conversation_data):
    """Determine optimal follow-up timing based on engagement"""
    metrics = conversation_data.get("metrics", {})

    # Analyze engagement
    engagement = analyze_engagement_level(metrics)

    # Define follow-up timing based on engagement level
    timing = {
        "HIGH": {
            "days_after_end": 2,
            "window_hours": 48,
            "reason": "High engagement warrants quick follow-up"
        },
        "MEDIUM": {
            "days_after_end": 3,
            "window_hours": 24,
            "reason": "Moderate engagement suggests standard timing"
        },
        "LOW": {
            "days_after_end": 4,
            "window_hours": 24,
            "reason": "Low engagement suggests longer wait"
        }
    }

    follow_up_timing = timing[engagement['level']]

    # Calculate actual timestamps
    last_seen = metrics.get("last_seen_timestamp")
    if last_seen:
        last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
        conversation_end = last_seen_dt + timedelta(hours=24)
        follow_up_start = conversation_end + \
            timedelta(days=follow_up_timing['days_after_end'])
        follow_up_end = follow_up_start + \
            timedelta(hours=follow_up_timing['window_hours'])

        follow_up_timing.update({
            "conversation_end": conversation_end,
            "follow_up_start": follow_up_start,
            "follow_up_end": follow_up_end
        })

    return follow_up_timing


def generate_follow_up_message(conversation_data):
    """Generate a casual, friendly follow-up message based on previous conversations"""

    # Get engagement metrics
    conv_metrics = conversation_data.get('metrics', {})
    conv_metadata = conversation_data.get('metadata', {})

    # Get the user name if available
    user_name = conv_metadata.get('user_name', 'there')

    # Basic follow-up template
    follow_up_message = f"Hey {user_name}! How's it going? Just checking in to see how you're doing."

    # Enhance with more context if available
    if 'topic_interests' in conv_metadata:
        interests = conv_metadata.get('topic_interests', [])
        if 'meal_plan' in interests:
            follow_up_message = f"Hey {user_name}! How's your meal plan going? Keeping it clean? 🥗 Still crushing it?"
        elif 'workout' in interests:
            follow_up_message = f"Hey {user_name}! How's your training going this week? Getting those gains? 💪"

    return follow_up_message


def generate_ai_follow_up_message(conversation_data):
    """Generate a personalized follow-up message using Gemini AI based on conversation history"""
    try:
        # Configure Gemini API
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")

        # Get the client's name/username
        client_name = conversation_data.get("ig_username", "")
        if not client_name:
            client_name = conversation_data.get(
                "metrics", {}).get("ig_username", "there")

        # Extract conversation history
        history = conversation_data.get("conversation_history", [])

        # Format the conversation history for the prompt
        history_text = ""
        if history:
            for msg in history:
                sender = "Coach" if msg.get("type") == "ai" else "Client"
                history_text += f"{sender}: {msg.get('text', '')}\n"
        else:
            history_text = "No previous conversation history available."

        # Build the prompt for Gemini
        prompt = f"""
        You are Shannon a Fitness Coach/ owner of Coco's Connected your fitness business,currently engaging with your followers on instagram your goal is to have general chat with your followers and build rapport. You are creating a follow up message - to continue the previous conversation had with the lead - read through the conversation and think of an insigltful question to ask to re-engage the lead, it doesnt have to be fitness releated, it should be releated to th previous conversation. Heres the instagram name if your going to use their name dont use the instagram name - figure it there real name from the instagram name {client_name}.

        Recent conversation history:
        {history_text}

        Guidelines for the follow-up message:
        2. Analyse the history context and create a question from it
        3. Keep it brief (5-20 words)
        4. Only include a single appropriate emoji if relevant
        5. Make it personal and engaging
        6. Keep it simple

        Here's an example: Heya! How's things? Hows the (insert something from the conversation) going the week?

        Format: Just provide the message without any additional text or explanations.
        """

        # Generate the response
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-thinking-exp-01-21",
        )

        response = model.generate_content(prompt)
        follow_up_message = response.text.strip()

        # If the response is empty or too long, fall back to the regular message
        if not follow_up_message or len(follow_up_message) > 200:
            return generate_follow_up_message(conversation_data)

        return follow_up_message

    except Exception as e:
        st.error(f"Error generating AI follow-up message: {e}")
        # Fallback to regular follow-up message if generation fails
        return generate_follow_up_message(conversation_data)


def load_analytics_data():
    try:
        analytics.load_analytics()
        return analytics.global_metrics, analytics.conversation_metrics
    except Exception as e:
        st.error(f"Error loading analytics data: {e}")
        return {}, {}


# Initialize session state
if 'global_metrics' not in st.session_state:
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()

# Initialize auto-refresh settings in session state
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60  # Default 60 seconds

# Sidebar navigation
st.sidebar.title("Shanbot Analytics")

# Add refresh controls
col1, col2 = st.sidebar.columns(2)
with col1:
    st.session_state.auto_refresh = st.checkbox(
        "Auto Refresh", value=st.session_state.auto_refresh)
with col2:
    if st.session_state.auto_refresh:
        st.session_state.refresh_interval = st.number_input("Interval (s)",
                                                            min_value=10,
                                                            max_value=300,
                                                            value=st.session_state.refresh_interval)

# Add manual refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.success("Data refreshed successfully!")

# Navigation selection in sidebar
selected_page = st.sidebar.radio(
    "Navigation",
    ["Overview", "User Profiles"]
)

# Show data loading status
st.sidebar.markdown("---")
st.sidebar.info("Loaded data from analytics_data.json")

# Main content area
st.title("Shanbot Analytics")

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # Calculate user metrics
    total_users = len(st.session_state.conversation_metrics)

    # Calculate active/inactive users
    now = datetime.now(timezone.utc)  # Use UTC for consistency
    active_users = 0
    inactive_users = 0

    for user_data in st.session_state.conversation_metrics.values():
        # Get the conversation end time
        conv_end = user_data.get("conversation_end_time")
        if conv_end:
            try:
                # Parse the timestamp and ensure it's UTC
                if isinstance(conv_end, str):
                    last_active = datetime.fromisoformat(
                        conv_end.replace('Z', '+00:00'))
                else:
                    last_active = conv_end

                # Convert to UTC if not already
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)

                # Check if active within last hour
                time_diff = now - last_active
                if time_diff.total_seconds() < ACTIVE_WINDOW:  # 1 hour in seconds
                    active_users += 1
                else:
                    inactive_users += 1
            except (ValueError, TypeError) as e:
                st.error(f"Error parsing timestamp: {e}")
                inactive_users += 1
        else:
            inactive_users += 1

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Stats")

        # Debug expander for User Stats calculations
        with st.expander("User Stats Debug"):
            st.write("Raw Data:")
            st.write(
                f"Total conversations in metrics: {len(st.session_state.conversation_metrics)}")

            # Show active/inactive calculation details
            active_count = 0
            inactive_count = 0
            for user_id, user_data in st.session_state.conversation_metrics.items():
                conv_end = user_data.get("conversation_end_time")
                if conv_end:
                    try:
                        # Parse the timestamp
                        if isinstance(conv_end, str):
                            last_active = datetime.fromisoformat(
                                conv_end.replace('Z', '+00:00'))
                        else:
                            last_active = conv_end

                        # Ensure UTC
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(
                                tzinfo=timezone.utc)

                        # Calculate time difference
                        time_diff = now - last_active
                        minutes_diff = time_diff.total_seconds() / 60

                        st.write(f"User {user_id}:")
                        st.write(f"  - Last active: {last_active}")
                        st.write(
                            f"  - Minutes since last message: {minutes_diff:.1f}")
                        st.write(
                            f"  - Status: {'Active' if minutes_diff < 60 else 'Inactive'}")

                        if time_diff.total_seconds() < ACTIVE_WINDOW:
                            active_count += 1
                    except (ValueError, TypeError) as e:
                        st.write(
                            f"  - Error parsing timestamp for user {user_id}: {e}")
                        inactive_count += 1

            st.write("\nCalculated Totals:")
            st.write(f"Active Users (recounted): {active_count}")
            st.write(f"Inactive Users (recounted): {inactive_count}")

        # Display metrics
        st.metric("Total Users", total_users)
        st.metric("Active Users (1h)", active_users,
                  help="Users who have had a conversation in the last hour")
        st.metric("Inactive Users", inactive_users,
                  help="Users who haven't had a conversation in the last hour")

    with col2:
        st.subheader("Conversion Metrics")

        # Get total signups and inquiries
        total_signups = 0
        total_inquiries = 0
        total_offers = 0

        # Debug expander for Conversion Metrics
        with st.expander("Conversion Metrics Debug"):
            st.write("Detailed Conversion Data:")
            for user_id, conv in st.session_state.conversation_metrics.items():
                # Track metrics for this user
                user_metrics = {
                    "signup": conv.get("signup_recorded", False),
                    "inquiries": conv.get("coaching_inquiry_count", 0),
                    "offer_shown": conv.get("offer_mentioned_in_conv", False)
                }

                # Update totals
                if user_metrics["signup"]:
                    total_signups += 1
                if user_metrics["inquiries"] > 0:
                    total_inquiries += 1
                if user_metrics["offer_shown"]:
                    total_offers += 1

                # Only show users with any conversion activity
                if any(user_metrics.values()):
                    st.write(f"\nUser {user_id}:")
                    st.write(f"  - Signed up: {user_metrics['signup']}")
                    st.write(
                        f"  - Inquiries made: {user_metrics['inquiries']}")
                    st.write(f"  - Offer shown: {user_metrics['offer_shown']}")

            st.write("\nTotals:")
            st.write(f"Total Signups: {total_signups}")
            st.write(f"Total Inquiries: {total_inquiries}")
            st.write(f"Total Offers Shown: {total_offers}")

        # Display metrics
        st.metric("Total Memberships Sold", total_signups,
                  help="Number of users who have signed up for membership")
        st.metric("Coaching Inquiries", total_inquiries,
                  help="Number of users who have inquired about coaching")

        # Calculate and display conversion rate
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                  help="Percentage of users who signed up after seeing an offer")

    with col3:
        st.subheader("Engagement Overview")

        # Debug expander for Engagement Metrics
        with st.expander("Engagement Metrics Debug"):
            st.write("Raw Message Counts from Global Metrics:")
            st.write(json.dumps(st.session_state.global_metrics, indent=2))

            st.write("\nMessage Count Verification:")
            total_messages = 0
            user_messages = 0
            ai_messages = 0

            # Count messages from conversation history
            for user_id, conv in st.session_state.conversation_metrics.items():
                history = conv.get("conversation_history", [])
                conv_total = len(history)
                conv_user = sum(
                    1 for msg in history if msg.get("type") != "ai")
                conv_ai = sum(1 for msg in history if msg.get("type") == "ai")

                total_messages += conv_total
                user_messages += conv_user
                ai_messages += conv_ai

                if conv_total > 0:  # Only show conversations with messages
                    st.write(f"\nUser {user_id} Message Counts:")
                    st.write(f"  - Total Messages: {conv_total}")
                    st.write(f"  - User Messages: {conv_user}")
                    st.write(f"  - AI Messages: {conv_ai}")

            st.write("\nTotal Counts (from conversation history):")
            st.write(f"Total Messages: {total_messages}")
            st.write(f"User Messages: {user_messages}")
            st.write(f"AI Messages: {ai_messages}")

            # Get counts from global metrics
            global_total = st.session_state.global_metrics.get(
                "total_messages", 0)
            global_user = st.session_state.global_metrics.get(
                "total_user_messages", 0)
            global_ai = st.session_state.global_metrics.get(
                "total_ai_messages", 0)

            st.write("\nGlobal Metric Counts:")
            st.write(f"Total Messages: {global_total}")
            st.write(f"User Messages: {global_user}")
            st.write(f"AI Messages: {global_ai}")

            # Calculate response rate
            response_rate = (global_ai / global_user *
                             100) if global_user > 0 else 0
            st.write(f"\nResponse Rate Calculation:")
            st.write(
                f"{global_ai} AI messages / {global_user} user messages = {response_rate:.1f}%")

        # Display metrics
        st.metric("Total Messages", global_total,
                  help="Total number of messages exchanged")
        st.metric("User Messages", global_user,
                  help="Total number of messages sent by users")
        st.metric("AI Messages", global_ai,
                  help="Total number of messages sent by the AI")
        st.metric("Response Rate", f"{response_rate:.1f}%",
                  help="Ratio of AI responses to user messages")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"])

    # Function to categorize users
    def get_responder_category(user_data):
        message_count = user_data.get("user_messages", 0)
        if message_count >= 10:
            return "High"
        elif message_count >= 4:
            return "Medium"
        else:
            return "Low"

    # Sort users into categories
    high_responders = []
    medium_responders = []
    low_responders = []

    now = datetime.now(timezone.utc)

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Get username (either IG username or user ID if not available)
        username = user_data.get("ig_username", user_id)

        # Get last active time and calculate status
        last_active = user_data.get("conversation_end_time", "Never")
        is_active = False
        formatted_last_active = "Never"

        if last_active != "Never":
            last_active_dt = parse_timestamp(last_active)
            if last_active_dt:
                is_active = is_user_active(last_active)
                formatted_last_active = last_active_dt.strftime(
                    "%Y-%m-%d %H:%M:%S")

        # Get message count
        message_count = user_data.get("total_messages", 0)

        # Create user info dict
        user_info = {
            "id": user_id,
            "username": username,
            "last_active": formatted_last_active,
            "message_count": message_count,
            "is_active": is_active,
            "status_indicator": "🟢" if is_active else "🔴"
        }

        # Add to appropriate category
        category = get_responder_category(user_data)
        if category == "High":
            high_responders.append(user_info)
        elif category == "Medium":
            medium_responders.append(user_info)
        else:
            low_responders.append(user_info)

    # Sort each list by active status first, then by message count
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (-x["is_active"], -x["message_count"]))

    # Display users in each tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high = st.selectbox(
                "Select User",
                options=high_responders,
                format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages",
                key="high_responders"
            )
            if selected_high:
                # Automatically update session state and trigger navigation
                st.session_state.update({
                    'selected_page': 'User Profiles',
                    'selected_user_id': selected_high['id']
                })
                st.rerun()

    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium = st.selectbox(
                "Select User",
                options=medium_responders,
                format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages",
                key="medium_responders"
            )
            if selected_medium:
                # Automatically update session state and trigger navigation
                st.session_state.update({
                    'selected_page': 'User Profiles',
                    'selected_user_id': selected_medium['id']
                })
                st.rerun()

    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low = st.selectbox(
                "Select User",
                options=low_responders,
                format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages",
                key="low_responders"
            )
            if selected_low:
                # Automatically update session state and trigger navigation
                st.session_state.update({
                    'selected_page': 'User Profiles',
                    'selected_user_id': selected_low['id']
                })
                st.rerun()

elif selected_page == "User Profiles":
    st.header("👥 User Profiles")

    # Get the user ID from session state if coming from responder tabs
    selected_user_id = st.session_state.get('selected_user_id', None)

    # Create a list of users with their basic info for selection
    user_list = []

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Get username (either IG username or user ID if not available)
        username = user_data.get("ig_username", user_id)

        # Get last active time and calculate status
        last_active = user_data.get("conversation_end_time", "Never")
        is_active = False
        formatted_last_active = "Never"

        if last_active != "Never":
            last_active_dt = parse_timestamp(last_active)
            if last_active_dt:
                is_active = is_user_active(last_active)
                formatted_last_active = last_active_dt.strftime(
                    "%Y-%m-%d %H:%M:%S")

        # Get message count
        message_count = user_data.get("total_messages", 0)

        # Create user info dict
        user_info = {
            "id": user_id,
            "username": username,
            "last_active": formatted_last_active,
            "message_count": message_count,
            "is_active": is_active,
            "status_indicator": "🟢" if is_active else "🔴"
        }

        # Add to appropriate category
        category = get_responder_category(user_data)
        if category == "High":
            high_responders.append(user_info)
        elif category == "Medium":
            medium_responders.append(user_info)
        else:
            low_responders.append(user_info)

    # Sort each list by active status first, then by message count
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (-x["is_active"], -x["message_count"]))

    # If we have a selected user from responder tabs, find it in the list
    selected_user = None
    if selected_user_id:
        selected_user = next(
            (user for user in user_list if user["id"] == selected_user_id), None)

    # If no user is selected from responder tabs, show the dropdown
    if not selected_user:
        selected_user = st.selectbox(
            "Select User",
            options=user_list,
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages"
        )
    else:
        # Show the selected user's info without the dropdown
        st.info(
            f"Viewing profile for: {selected_user['status_indicator']} {selected_user['username']}")
        # Add a button to clear selection and return to list
        if st.button("← Back to User List"):
            st.session_state.selected_user_id = None
            st.rerun()

    if selected_user:
        user_data = st.session_state.conversation_metrics[selected_user["id"]]

        # Create three columns for user metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("User Info")
            st.write(f"**Username:** {user_data.get('ig_username', 'N/A')}")
            st.write(f"**User ID:** {selected_user['id']}")
            st.write(
                f"**First Seen:** {user_data.get('conversation_start_time', 'N/A')}")

            # Show user status and last active time
            last_active_time = user_data.get("conversation_end_time")
            if last_active_time:
                last_active_dt = parse_timestamp(last_active_time)
                if last_active_dt:
                    is_active = is_user_active(last_active_time)
                    now = datetime.now(timezone.utc)
                    time_diff = now - last_active_dt
                    minutes_ago = time_diff.total_seconds() / 60

                    status = "🟢 Active" if is_active else "🔴 Inactive"
                    st.write(f"**Status:** {status}")
                    st.write(f"**Last Active:** {minutes_ago:.1f} minutes ago")
            else:
                st.write(f"**Status:** 🔴 Inactive")
                st.write("**Last Active:** Unknown")

        with col2:
            st.subheader("Engagement Metrics")
            total_msgs = user_data.get("total_messages", 0)
            user_msgs = user_data.get("user_messages", 0)
            ai_msgs = user_data.get("ai_messages", 0)

            st.metric("Total Messages", total_msgs)
            st.metric("User Messages", user_msgs)
            st.metric("AI Messages", ai_msgs)

            # Calculate response rate
            if user_msgs > 0:
                response_rate = (ai_msgs / user_msgs) * 100
                st.metric("Response Rate", f"{response_rate:.1f}%")

        with col3:
            st.subheader("Conversion Info")
            st.write(
                f"**Coaching Inquiries:** {user_data.get('coaching_inquiry_count', 0)}")
            st.write(
                f"**Offer Shown:** {'Yes' if user_data.get('offer_mentioned_in_conv', False) else 'No'}")
            st.write(
                f"**Signed Up:** {'Yes' if user_data.get('signup_recorded', False) else 'No'}")

            # Show topics mentioned
            st.write("**Topics Mentioned:**")
            topics = []
            if user_data.get("vegan_topic_mentioned", False):
                topics.append("Vegan")
            if user_data.get("weight_loss_mentioned", False):
                topics.append("Weight Loss")
            if user_data.get("muscle_gain_mentioned", False):
                topics.append("Muscle Gain")
            st.write(", ".join(topics) if topics else "None")

        # Show conversation history
        st.subheader("Conversation History")
        history = user_data.get("conversation_history", [])
        if history:
            for msg in history:
                # Create a message container with different styles for user/AI
                is_ai = msg.get("type") == "ai"
                with st.container():
                    # Format timestamp
                    timestamp = msg.get("timestamp", "")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(
                                timestamp.replace('Z', '+00:00'))
                            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass

                    # Display message with different colors for AI/User
                    st.markdown(f"""
                        <div style='
                            padding: 10px; 
                            border-radius: 5px; 
                            margin: 5px 0; 
                            background-color: {"#e1f5fe" if is_ai else "#f5f5f5"};
                            border-left: 5px solid {"#0288d1" if is_ai else "#9e9e9e"};
                        '>
                        <small>{timestamp}</small><br>
                        <strong>{"AI" if is_ai else "User"}</strong>: {msg.get("text", "")}
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No conversation history available")

# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Auto-refresh logic
if st.session_state.auto_refresh:
    time.sleep(st.session_state.refresh_interval)
    st.rerun()

# Test Gemini follow-up message generation
with st.expander("Test Gemini Follow-up Message Generator"):
    st.write(
        "Test the Gemini-powered follow-up message generation with the current conversation.")

    # Button to generate a follow-up message
    if st.button("Generate Follow-up Message"):
        with st.spinner("Generating message with Gemini..."):
            try:
                # Get the current user's conversation data
                if not selected_display_name:
                    st.warning(
                        "Please select a conversation in the Conversation Interface first.")
                else:
                    conversation_data = conversations[subscriber_id_to_lookup]

                    # Get follow-up message using Gemini
                    ai_message = generate_ai_follow_up_message(
                        conversation_data)

                    # Get standard follow-up message for comparison
                    standard_message = generate_follow_up_message(
                        conversation_data)

                    # Display both messages
                    st.success("Messages generated successfully!")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Gemini-generated Message")
                        st.info(ai_message)

                    with col2:
                        st.subheader("Standard Template Message")
                        st.info(standard_message)

                        # Display conversation history used
                        st.subheader("Conversation History Used")
                        history = conversation_data.get(
                            "conversation_history", [])
                        for msg in history:
                            sender = "Coach" if msg.get(
                                "type") == "ai" else "Client"
                            st.text(f"{sender}: {msg.get('text', '')}")

            except Exception as e:
                st.error(f"Error generating message: {str(e)}")
                if "GEMINI_API_KEY" not in os.environ and not hasattr(st.secrets, "GEMINI_API_KEY"):
                    st.error(
                        "GEMINI_API_KEY not found. Please add it to your environment variables or Streamlit secrets.")

# Add test user function


def add_test_user():
    test_user_id = "test_user_123"
    current_time = datetime.now(timezone.utc)

    # Add user message
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Hey! I'm interested in getting fit. How much does coaching cost?",
        message_type="user",
        timestamp=current_time.isoformat(),
        ig_username="test_fitness_enthusiast"
    )

    # Add AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Hey there! 👋 Great to hear you're interested in fitness! Our coaching programs start at $X per month. Would you like to know more about what's included?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=1)).isoformat()
    )

    # Add another user message
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Yes please! I'm particularly interested in weight loss.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=2)).isoformat()
    )

    # Add another AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Perfect! Here's a link to our program: cocospersonaltraining.com/online. It includes personalized workouts, nutrition guidance, and weekly check-ins. Would you like to get started?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=3)).isoformat()
    )

    return "Test user added successfully!"


# Add test user button in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    st.sidebar.success(result)
    # Refresh the data
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.rerun()
