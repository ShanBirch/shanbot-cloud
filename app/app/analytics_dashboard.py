import threading
import google.generativeai as genai
import re
import logging
import time
from datetime import timezone
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import os
from conversation_analytics_integration import analytics
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("conversation_analytics")

# Function definitions


def load_followup_manager():
    """Load the followup_manager module"""
    global followup_manager
    try:
        # Try to load from parent directory
        import sys
        import os
        parent_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        followup_manager_path = os.path.join(parent_dir, "followup_manager.py")
        if not os.path.exists(followup_manager_path):
            st.error(
                f"followup_manager.py not found at {followup_manager_path}")
            return False

        # Add parent directory to path if not already there
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        # Try importing now
        import importlib
        import followup_manager
        # Force reload in case it was changed
        importlib.reload(followup_manager)
        return True
    except ImportError as e:
        st.error(f"Could not import followup_manager: {e}")
        return False
    except Exception as e:
        st.error(f"Unexpected error loading followup_manager: {e}")
        return False


def display_conversation(selected_user):
    """Display a single conversation with a user"""
    user_data = st.session_state.conversation_metrics[selected_user["id"]]
    conversation_id = selected_user["id"]
    username = user_data.get("ig_username", conversation_id)

    # Direct Message Section - Always show this first
    st.markdown("### 📱 Send Message")

    # Message input
    direct_message = st.text_area(
        "Type your message here:",
        key=f"direct_msg_{selected_user['id']}",
        height=100
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        # Send button
        if st.button("📤 Send Message", key=f"send_msg_{selected_user['id']}"):
            if not username or username == conversation_id:
                st.error("No Instagram username found for this user")
            else:
                with st.spinner(f"Sending message to {username}..."):
                    try:
                        # Load followup_manager
                        import importlib.util
                        import sys
                        import os

                        # Get the parent directory path
                        parent_dir = os.path.dirname(
                            os.path.dirname(os.path.abspath(__file__)))

                        # Add parent directory to Python path if not already there
                        if parent_dir not in sys.path:
                            sys.path.append(parent_dir)

                        # Import followup_manager
                        spec = importlib.util.spec_from_file_location(
                            "followup_manager",
                            os.path.join(parent_dir, "followup_manager.py")
                        )
                        followup_manager = importlib.util.module_from_spec(
                            spec)
                        spec.loader.exec_module(followup_manager)

                        # Get or create driver
                        driver = followup_manager.get_driver()
                        if not driver:
                            driver = followup_manager.setup_driver()

                        if driver:
                            # Send the message
                            result = followup_manager.send_follow_up_message(
                                driver,
                                username,
                                direct_message
                            )

                            if result.get("success", False):
                                # Update analytics
                                user_data["last_follow_up_date"] = datetime.now(
                                    timezone.utc).isoformat()
                                user_data["follow_ups_sent"] = user_data.get(
                                    "follow_ups_sent", 0) + 1

                                # Add to follow-up history
                                if "follow_up_history" not in user_data:
                                    user_data["follow_up_history"] = []

                                user_data["follow_up_history"].append({
                                    "date": datetime.now(timezone.utc).isoformat(),
                                    "message": direct_message,
                                    "sent_via_instagram": True
                                })

                                # Save updates
                                st.session_state.conversation_metrics[selected_user["id"]] = user_data
                                analytics.export_analytics()

                                st.success(
                                    f"Message sent to {username} successfully!")
                                # Clear the message input
                                st.session_state[f"direct_msg_{selected_user['id']}"] = ""
                                st.rerun()
                            else:
                                st.error(
                                    f"Failed to send message: {result.get('error', 'Unknown error')}")
                        else:
                            st.error("Failed to setup browser")
                    except Exception as e:
                        st.error(f"Error sending message: {e}")

    with col2:
        # Generate AI message button
        if st.button("🤖 Generate AI Message", key=f"gen_msg_{selected_user['id']}"):
            with st.spinner("Generating personalized message..."):
                try:
                    follow_up_message = generate_ai_follow_up_message(
                        user_data)
                    # Update the text area with the generated message
                    st.session_state[f"direct_msg_{selected_user['id']}"] = follow_up_message
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating message: {e}")

    # Add a new section for follow-up history
    st.markdown("---")
    with st.expander("Follow-up Message History", expanded=False):
        if "follow_up_history" in user_data and user_data["follow_up_history"]:
            for idx, followup in enumerate(reversed(user_data["follow_up_history"])):
                try:
                    date = datetime.fromisoformat(
                        followup.get("date", "").replace('Z', '+00:00'))
                    date_display = date.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    date_display = followup.get("date", "Unknown date")

                st.markdown(f"**Sent on {date_display}:**")
                st.markdown(
                    f"_{followup.get('message', 'No message content')}_")
                st.markdown("---")
        else:
            st.info("No follow-up messages have been sent yet.")

    st.markdown("---")

    # Rest of the user profile display
    st.subheader("User Info")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Username:**", username)
        st.write("**User ID:**", selected_user["id"])
        st.write("**First Seen:**",
                 user_data.get("conversation_start_time", "N/A"))

        # Add responder category
        message_count = user_data.get("user_messages", 0)
        if message_count >= 10:
            responder_category = "High Responder"
            category_emoji = "🔥"
        elif message_count >= 4:
            responder_category = "Medium Responder"
            category_emoji = "📊"
        else:
            responder_category = "Low Responder"
            category_emoji = "🔄"

        st.write(
            f"**Responder Category:** {category_emoji} {responder_category}")

    with col2:
        st.write("**Total Messages:**", user_data.get("total_messages", 0))
        st.write("**User Messages:**", user_data.get("user_messages", 0))
        st.write("**AI Messages:**", user_data.get("ai_messages", 0))

    with col3:
        st.write("**Coaching Inquiries:**",
                 user_data.get("coaching_inquiry_count", 0))
        st.write("**Offer Shown:**",
                 "Yes" if user_data.get("offer_mentioned_in_conv", False) else "No")
        st.write("**Signed Up:**",
                 "Yes" if user_data.get("signup_recorded", False) else "No")

    # Display conversation history
    st.subheader("💬 Conversation History")
    history = user_data.get("conversation_history", [])

    if history:
        for msg in history:
            is_ai = msg.get("type") == "ai"
            with st.container():
                timestamp = msg.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(
                            timestamp.replace('Z', '+00:00'))
                        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

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
            st.info("No conversation history available.")

# Helper function for timestamp parsing


def parse_timestamp(timestamp_str):
    """Parse a timestamp string into a datetime object with timezone awareness."""
    try:
        if isinstance(timestamp_str, datetime):
            dt = timestamp_str
        else:
            # Handle ISO format with or without timezone
            if 'Z' in timestamp_str:
                # Replace Z with +00:00 for UTC time
                timestamp_str = timestamp_str.replace('Z', '+00:00')

            # Parse the ISO format string
            dt = datetime.fromisoformat(timestamp_str)

        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except Exception as e:
        logger.warning(f"Error parsing timestamp {timestamp_str}: {e}")
        return None

# Function for overall quality score calculation


def calculate_overall_quality_score(conversation_metrics):
    # Start with a base score
    score = 5.0

    # Adjust based on response time (faster is better)
    avg_response_time = conversation_metrics.get('avg_response_time', 0)
    if avg_response_time < 60:  # Less than 1 minute
        score += 1.5
    elif avg_response_time < 300:  # Less than 5 minutes
        score += 1.0
    elif avg_response_time < 900:  # Less than 15 minutes
        score += 0.5
    elif avg_response_time > 3600:  # More than 1 hour
        score -= 1.0

    # Adjust based on conversation length (longer generally indicates better engagement)
    num_messages = conversation_metrics.get('num_messages', 0)
    if num_messages > 20:
        score += 1.5
    elif num_messages > 10:
        score += 1.0
    elif num_messages > 5:
        score += 0.5
    elif num_messages < 3:
        score -= 1.0

    # Adjust based on user satisfaction indicators
    positive_reactions = conversation_metrics.get('positive_reactions', 0)
    negative_reactions = conversation_metrics.get('negative_reactions', 0)

    # Net reaction score
    reaction_score = positive_reactions - negative_reactions
    if reaction_score > 5:
        score += 2.0
    elif reaction_score > 0:
        score += 1.0
    elif reaction_score < -3:
        score -= 2.0

    # Ensure score stays within 1-10 range
    score = max(1.0, min(score, 10.0))

    return score


# Set page config
st.set_page_config(
    page_title="Shannon Bot Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load analytics data


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

# Initialize session state variables for auto-refresh
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60  # Default 60 seconds
if 'view_profile' not in st.session_state:
    st.session_state.view_profile = None
if 'ai_assistant_messages' not in st.session_state:
    st.session_state.ai_assistant_messages = []

# Define constants
ACTIVE_WINDOW = 3600  # 1 hour in seconds
ANALYTICS_FILE_PATH = "C:\\Users\\Shannon\\analytics_data.json"
AUTO_FOLLOWUP_ENABLED = False
SCHEDULED_FOLLOWUPS = {}

# Add test scheduled followups for visibility testing
# Comment this out when not testing
if not SCHEDULED_FOLLOWUPS:
    SCHEDULED_FOLLOWUPS = {
        "test_user1": [
            {
                "message": "Hey, how's your workout going?",
                "scheduled_time": (datetime.now() + timedelta(hours=24)).isoformat(),
                "status": "pending"
            }
        ],
        "test_user2": [
            {
                "message": "Did you try that new exercise routine?",
                "scheduled_time": (datetime.now() + timedelta(hours=48)).isoformat(),
                "status": "pending"
            }
        ]
    }

# Sidebar
st.sidebar.title("Analytics Dashboard")

# Add refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.success("Data refreshed successfully!")

# Navigation
selected_page = st.sidebar.radio(
    "Select Section",
    ["Overview", "User Profiles", "Conversations", "Scheduled Follow-ups",
        "Daily Report", "Analytics Export", "AI Data Assistant"],
    key="main_navigation"
)

# Main content area
st.title("Shannon Bot Analytics Dashboard")

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # Calculate Overall Quality Score
    overall_quality_score = calculate_overall_quality_score(
        st.session_state.conversation_metrics)

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Conversation Stats")
        st.metric("Total Conversations",
                  st.session_state.global_metrics.get("total_conversations", 0))
        st.metric("Total Messages",
                  st.session_state.global_metrics.get("total_messages", 0))
        st.metric("User Messages",
                  st.session_state.global_metrics.get("total_user_messages", 0))
        st.metric("Bot Messages",
                  st.session_state.global_metrics.get("total_ai_messages", 0))

    with col2:
        st.subheader("Response Metrics")
        total_responses = st.session_state.global_metrics.get(
            "question_stats", {}).get("user_responses_to_questions", 0)
        total_ai = st.session_state.global_metrics.get("total_ai_messages", 0)
        response_rate = (total_responses / total_ai *
                         100) if total_ai > 0 else 0
        st.metric("Total Responses", total_responses)
        st.metric("Response Rate", f"{response_rate:.1f}%")

    with col3:
        st.subheader("Engagement Overview")
        total_messages = st.session_state.global_metrics.get(
            "total_messages", 0)
        user_messages = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        ai_messages = st.session_state.global_metrics.get(
            "total_ai_messages", 0)

        # Get question stats
        question_stats = st.session_state.global_metrics.get(
            "question_stats", {})
        questions_asked = question_stats.get("ai_questions_asked", 0)
        questions_responded = question_stats.get(
            "user_responses_to_questions", 0)

        # Calculate total response rate
        total_response_rate = (
            questions_responded / questions_asked * 100) if questions_asked > 0 else 0

        # Display metrics
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Response Rate", f"{total_response_rate:.1f}%",
                  help="Percentage of AI questions that received a user response")

        # Debug info in expander
        with st.expander("Show Debug Info"):
            st.write("Raw Numbers:")
            st.write(f"Total Messages: {total_messages}")
            st.write(f"User Messages: {user_messages}")
            st.write(f"AI Messages: {ai_messages}")
            st.write(f"Questions Asked: {questions_asked}")
            st.write(f"Questions Responded: {questions_responded}")
            st.write("Response Rate Calculation:",
                     f"{questions_responded} responses / {questions_asked} questions = {total_response_rate:.1f}%")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"]
    )

    # Function to categorize users
    def get_responder_category(user_data):
        # Use 'user_messages' for categorization, default to 0 if missing
        user_message_count = user_data.get("user_messages", 0)
        if user_message_count >= 51:
            return "High"
        elif user_message_count >= 11:  # 11 to 50
            return "Medium"
        elif user_message_count >= 1:  # 1 to 10
            return "Low"
        else:  # 0 messages
            return "No Responder"

    # Sort users into categories
    high_responders = []
    medium_responders = []
    low_responders = []

    now = datetime.now(timezone.utc)

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Get username (either IG username or user ID if not available)
        username = user_data.get("ig_username") or user_id

        # Calculate status based on last_message_timestamp
        is_active = False
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                last_active_dt = parse_timestamp(last_active_timestamp)
                if last_active_dt:
                    time_diff = now - last_active_dt
                    if time_diff.total_seconds() < ACTIVE_WINDOW:
                        is_active = True
            except Exception:  # Ignore errors for sorting/display purpose
                pass

        status_indicator = "🟢" if is_active else "🔴"

        # Get BOTH total and user message counts
        total_message_count = user_data.get("total_messages", 0)
        # Get user message count for display
        user_message_count = user_data.get("user_messages", 0)

        # Create user info dict including status and user message count
        user_info = {
            "id": user_id,
            "username": username,
            # Keep total for sorting consistency?
            "total_message_count": total_message_count,
            "user_message_count": user_message_count,  # Use this for display in format_func
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        }

        # Add to appropriate category based on USER messages
        # Uses user_messages internally
        category = get_responder_category(user_data)
        if category == "High":
            high_responders.append(user_info)
        elif category == "Medium":
            medium_responders.append(user_info)
        elif category == "Low":
            low_responders.append(user_info)
        # Ignore "No Responder"

    # Sort each list by active status first (descending), then by TOTAL message count (descending)
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (x["is_active"], x["total_message_count"]), reverse=True)

    # Display the high responders tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high_index = st.selectbox(
                "High Engagement Users",
                options=range(len(high_responders)),
                format_func=lambda i: f"{high_responders[i]['status_indicator']} {high_responders[i]['username']} - {high_responders[i]['user_message_count']} user msgs",
                key="high_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_high_button"):
                st.session_state.view_profile = high_responders[selected_high_index]['id']
                st.rerun()
        else:
            st.info("No high responders found")

    # Display the medium responders tab
    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium_index = st.selectbox(
                "Medium Engagement Users",
                options=range(len(medium_responders)),
                format_func=lambda i: f"{medium_responders[i]['status_indicator']} {medium_responders[i]['username']} - {medium_responders[i]['user_message_count']} user msgs",
                key="medium_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_medium_button"):
                st.session_state.view_profile = medium_responders[selected_medium_index]['id']
                st.rerun()
        else:
            st.info("No medium responders found")

    # Display the low responders tab
    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low_index = st.selectbox(
                "Low Engagement Users",
                options=range(len(low_responders)),
                format_func=lambda i: f"{low_responders[i]['status_indicator']} {low_responders[i]['username']} - {low_responders[i]['user_message_count']} user msgs",
                key="low_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_low_button"):
                st.session_state.view_profile = low_responders[selected_low_index]['id']
                st.rerun()
        else:
            st.info("No low responders found")

elif selected_page == "User Profiles":
    st.header("👥 User Profiles")

    # Get the user ID from view_profile if set
    selected_user_id = st.session_state.view_profile

    # Create a list of users with their basic info for selection
    user_list = []
    now = datetime.now(timezone.utc)  # Get current time once for efficiency

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Get username (either IG username or user ID if not available)
        username = user_data.get("ig_username") or user_id

        # Calculate status based on last_message_timestamp
        is_active = False
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                last_active_dt = parse_timestamp(last_active_timestamp)
                if last_active_dt:
                    time_diff = now - last_active_dt
                    if time_diff.total_seconds() < ACTIVE_WINDOW:
                        is_active = True
            except Exception:  # Ignore errors for sorting/display purpose
                pass

        status_indicator = "🟢" if is_active else "🔴"

        # Get message count
        message_count = user_data.get("total_messages", 0)
        user_message_count = user_data.get("user_messages", 0)

        # Create user info dict including status
        user_list.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "user_message_count": user_message_count,
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        })

    # Sort users by active status first (descending), then by message count (descending)
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

    # Add search functionality
    search_query = st.text_input("🔍 Search by username", "")
    if search_query:
        filtered_user_list = [
            user for user in user_list if search_query.lower() in user["username"].lower()]
        if filtered_user_list:
            st.success(f"Found {len(filtered_user_list)} matching users")
            user_list = filtered_user_list
        else:
            st.warning(f"No users found matching '{search_query}'")

    # If we have a selected user from responder tabs, find it in the list
    selected_user_from_id = None
    if selected_user_id:
        selected_user_from_id = next(
            (user for user in user_list if user["id"] == selected_user_id), None)

    # If no user is selected from responder tabs, show the dropdown
    if not selected_user_from_id:
        selected_user = st.selectbox(
            "Select User",
            options=user_list,
            # Update format_func to include the status indicator and user message count
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['user_message_count']} user msgs ({x['message_count']} total)"
        )
    else:
        # Show the selected user's info without the dropdown
        st.info(
            f"Viewing profile for: {selected_user_from_id['status_indicator']} {selected_user_from_id['username']}")
        # Use the found user object
        selected_user = selected_user_from_id
        # Add a button to clear selection and return to list
        if st.button("← Back to Overview"):
            st.session_state.view_profile = None
            st.rerun()  # Rerun to go back to overview/dropdown view

    if selected_user:
        display_conversation(selected_user)

elif selected_page == "Conversations":
    st.header("💬 Conversations")
    st.info("This section will contain conversation details. Still under development.")

elif selected_page == "Daily Report":
    st.header("📅 Daily Report")
    st.info("This section will contain daily metrics. Still under development.")

elif selected_page == "Analytics Export":
    st.header("📊 Analytics Export")
    st.info("This section will provide export functionality. Still under development.")

elif selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("Ask questions about your analytics data in natural language.")

    # Display chat messages from history on app rerun
    for message in st.session_state.ai_assistant_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Ask about your data..."):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        st.session_state.ai_assistant_messages.append(
            {"role": "user", "content": prompt})

        # --- Prepare data context for Gemini ---
        # Use data already loaded into session state
        global_data = st.session_state.get('global_metrics', {})
        conv_data = st.session_state.get('conversation_metrics', {})

        # Simple summary of conversation data (can be expanded)
        conv_summary = (
            f"- Total Users/Conversations: {len(conv_data)}\n"
            f"- User IDs/Usernames (first 10): {list(conv_data.keys())[:10]}\n"
            # Add more summary points as needed
        )

        # Convert global data to string
        global_data_str = json.dumps(global_data, indent=2)

        # --- Construct Gemini Prompt ---
        gemini_prompt = f"""
You are a helpful data analyst assistant embedded in a Streamlit dashboard. Your task is to answer
 questions about Instagram follower interaction data based ONLY on the provided data context.

**Data Context:**

**1. Global Metrics:**
```json
{global_data_str}
```

**2. Conversation Data Summary:**
{conv_summary}

**Important Rules:**
- Base your answers STRICTLY on the data provided above.
- Do not make assumptions or use external knowledge.
- If the provided data doesn't contain the answer, state that clearly.
- If the user asks about a specific user/ID, and you need more detail than the summary provides, state that you need the specific user's data (you cannot retrieve it yourself).
- Keep answers concise and informative.

**User Question:**
{prompt}

**Answer:**
"""

        # --- Call Gemini API ---
        try:
            with st.spinner("Analyzing data..."):
                genai.configure(
                    api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
                # Change the model used for analysis
                model = genai.GenerativeModel(
                    'gemini-2.0-flash-thinking-exp-01-21')
                response = model.generate_content(gemini_prompt)
                ai_response = response.text.strip()

            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(ai_response)
            # Add assistant response to chat history
            st.session_state.ai_assistant_messages.append(
                {"role": "assistant", "content": ai_response})

        except Exception as e:
            st.error(f"Error communicating with AI: {e}")
            logger.error(f"AI Assistant Error: {e}", exc_info=True)
            with st.chat_message("assistant"):
                st.markdown(
                    "Sorry, I encountered an error trying to process your request.")
            st.session_state.ai_assistant_messages.append(
                {"role": "assistant", "content": "Sorry, I encountered an error."})

elif selected_page == "Scheduled Follow-ups":
    st.header("⏱️ Scheduled Follow-ups")
    st.info("This page helps you manage follow-ups for inactive users based on timing rules: High responders (48 hours), Medium responders (5 days), Low responders (7 days).")

    # Initialize required session state variables
    if "scheduled_follow_ups" not in st.session_state:
        st.session_state.scheduled_follow_ups = {}

    # Display scheduled followups
    st.subheader("Currently Scheduled Follow-ups")

    if not SCHEDULED_FOLLOWUPS or all(not msgs for msgs in SCHEDULED_FOLLOWUPS.values()):
        st.success("No users currently need scheduled follow-ups.")
    else:
        # Create column headers
        cols = st.columns([0.3, 0.2, 0.2, 0.2, 0.1])
        cols[0].write("**Username**")
        cols[1].write("**Scheduled Time**")
        cols[2].write("**Message**")
        cols[3].write("**Status**")
        cols[4].write("**Action**")

        st.markdown("---")

        # Display each scheduled followup
        for username, messages in SCHEDULED_FOLLOWUPS.items():
            for msg_idx, msg in enumerate(messages):
                if msg.get('status') == 'sent':
                    continue  # Skip already sent messages

                cols = st.columns([0.3, 0.2, 0.2, 0.2, 0.1])

                # Username
                cols[0].write(username)

                # Scheduled time
                scheduled_time = msg.get('scheduled_time', 'Not set')
                try:
                    if isinstance(scheduled_time, str):
                        dt = datetime.fromisoformat(
                            scheduled_time.replace('Z', '+00:00'))
                        scheduled_time = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
                cols[1].write(scheduled_time)

                # Message preview (truncated)
                message = msg.get('message', '')
                if len(message) > 30:
                    message = message[:27] + "..."
                cols[2].write(message)

                # Status
                cols[3].write(msg.get('status', 'pending'))

                # Delete button
                if cols[4].button("Delete", key=f"delete_followup_{username}_{msg_idx}"):
                    if delete_scheduled_followup(username):
                        st.success(
                            f"Removed {username} from scheduled followups")
                        st.rerun()

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Loaded data from analytics_data.json")

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
        message_text="Yes, I'd like to know more about the coaching program.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=5)).isoformat()
    )

    st.success("Test user added successfully!")


def log_followup_success(username, message):
    """Log a successful follow-up message"""
    # Update analytics data
    analytics_data = load_analytics_data()

    # If this username has a conversation, update it
    if "conversations" in analytics_data and username in analytics_data["conversations"]:
        conversation = analytics_data["conversations"][username]

        if "messages" not in conversation:
            conversation["messages"] = []

        # Add the follow-up message to the conversation
        conversation["messages"].append({
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "auto_followup"
        })

        # Update last_followup_date
        conversation["last_followup_date"] = datetime.now(
            timezone.utc).isoformat()

        # Save updated analytics data
        save_analytics_data(analytics_data)


# Function for logging follow-up failure
def log_followup_failure(username, error):
    """Log a failed follow-up message"""
    # Update analytics data to track the failure
    analytics_data = load_analytics_data()

    # If this username has a conversation, update it
    if "conversations" in analytics_data and username in analytics_data["conversations"]:
        conversation = analytics_data["conversations"][username]

        if "followup_errors" not in conversation:
            conversation["followup_errors"] = []

        # Add the error to the conversation
        conversation["followup_errors"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error
        })

        # Save updated analytics data
        save_analytics_data(analytics_data)


def generate_ai_follow_up_message(conversation_data):
    """Generate a personalized follow-up message using Gemini AI based on conversation history and profile analysis without time restrictions"""
    try:
        # Configure Gemini API
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")

        # Get the client's name/username safely
        client_ig_username = conversation_data.get("ig_username")
        client_analysis = conversation_data.get("client_analysis", {})
        profile_bio = client_analysis.get("profile_bio", {})
        # Get name from profile if available, otherwise fallback to username
        client_name = profile_bio.get("PERSON NAME") or profile_bio.get(
            "person_name") or client_ig_username or "there"

        # Extract conversation history
        history = conversation_data.get("conversation_history", [])

        # Format the conversation history for the prompt
        history_text = ""
        if history:
            # Limit to most recent 15 messages to keep prompt size reasonable
            recent_history = history[-15:] if len(history) > 15 else history
            for msg in recent_history:
                sender = "Coach" if msg.get("type") == "ai" else "Client"
                history_text += f"{sender}: {msg.get('text', '')}\n"
        else:
            history_text = "No previous conversation history available."

        # Format profile bio information for the prompt
        profile_info_text = "No profile information available."
        if profile_bio:
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
            # Handle case where bio exists but fields are empty
            if profile_info_text == "Client Profile Information:\n":
                profile_info_text = "Basic profile bio exists, but specific details (interests, lifestyle, personality) are not populated."

        # Add follow-up context
        follow_up_context = ""
        last_message_time = conversation_data.get("last_message_timestamp")
        if last_message_time:
            try:
                last_dt = parse_timestamp(last_message_time)
                if last_dt:
                    now = datetime.now(timezone.utc)
                    time_diff = now - last_dt
                    days_inactive = time_diff.days
                    if days_inactive > 0:
                        follow_up_context = f"\nThis user has been inactive for {days_inactive} days since their last message. The follow-up should re-engage them without being too pushy."
            except Exception:
                pass

        # Check previous follow-ups
        previous_follow_ups = conversation_data.get("follow_up_history", [])
        if previous_follow_ups:
            follow_up_context += "\n\nPrevious follow-up messages sent:"
            # Show last 2 follow-ups
            for idx, followup in enumerate(previous_follow_ups[-2:]):
                follow_up_context += f"\n- {followup.get('message', 'No message content')}"

        # Build the prompt for Gemini
        prompt = f"""
        You are Shannon, a Fitness Coach and owner of Coco's Connected fitness business, engaging with your followers on Instagram. Your goal is to build rapport and re-engage leads.
        You are creating a follow-up message for a client named {client_name} (IG: {client_ig_username}).

        Instructions:
        1. Carefully review BOTH the recent conversation history AND the client's profile information provided below.
        2. Based on BOTH sources, formulate an insightful and relevant question to continue the conversation or re-engage them.
        3. The question can be about topics discussed previously OR about their known interests/lifestyle from their profile.
        4. Keep the message brief and casual (5-25 words).
        5. Include a single appropriate emoji if relevant.
        6. Make it personal and engaging, referencing something specific if possible.
        7. DO NOT ask generic questions like "How are you?" or "What's up?" unless there's absolutely nothing else to go on.
        8. Your final output should ONLY be the message text itself.
        9. Do not use the user's name in the message

        Client Profile Information:
        {profile_info_text}

        Recent Conversation History:
        {history_text}
        {follow_up_context}

        Generate the follow-up message now:
        """

        # --- Try Primary Model (Flash) ---
        primary_model_name = "gemini-2.0-flash"
        fallback_model_name = "gemini-2.0-flash-lite"  # Updated fallback model
        follow_up_message = None
        error_occurred = None

        try:
            logger.info(
                f"Attempting generation for {client_ig_username} with {primary_model_name}...")
            model = genai.GenerativeModel(model_name=primary_model_name)
            # Configure safety settings (important!)
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            response = model.generate_content(
                prompt, safety_settings=safety_settings)
            follow_up_message = response.text.strip()
            logger.info(f"Successfully generated with {primary_model_name}.")

        except Exception as e_primary:
            logger.warning(
                f"Generation with {primary_model_name} failed for {client_ig_username}: {type(e_primary).__name__} - {e_primary}. Attempting fallback...")
            error_occurred = e_primary  # Store primary error

            # --- Try Fallback Model (Pro) ---
            try:
                logger.info(
                    f"Attempting generation for {client_ig_username} with fallback {fallback_model_name}...")
                model = genai.GenerativeModel(model_name=fallback_model_name)
                # Re-apply safety settings for fallback model
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                }
                response = model.generate_content(
                    prompt, safety_settings=safety_settings)
                follow_up_message = response.text.strip()
                logger.info(
                    f"Successfully generated with fallback {fallback_model_name}.")
                error_occurred = None  # Clear error if fallback succeeded

            except Exception as e_fallback:
                logger.error(
                    f"Fallback generation with {fallback_model_name} also failed for {client_ig_username}: {type(e_fallback).__name__} - {e_fallback}", exc_info=True)
                error_occurred = e_fallback  # Store fallback error
                # Let the process fall through to the final exception handler/fallback

        # --- Check result and handle final fallback ---
        # If an error still exists after trying both models, or message is invalid
        if error_occurred or not follow_up_message or len(follow_up_message.split()) > 30:
            if error_occurred:
                # Log the final error that persisted
                error_message = f"AI generation failed for {client_ig_username} after trying both models. Final Error: {type(error_occurred).__name__} - {error_occurred}"
                logger.error(error_message)
                status_code = getattr(error_occurred, 'status_code', None) or getattr(
                    error_occurred, 'code', None)
                if status_code:
                    st.error(
                        f"API Error ({status_code}) generating follow-up: {str(error_occurred)}")
                else:
                    st.error(
                        f"Error generating AI follow-up: {str(error_occurred)}")
            else:
                # Handle invalid message content (too long/empty)
                logger.warning(
                    f"AI generated message invalid (empty/too long) for {client_ig_username}, falling back. AI Message: '{follow_up_message}'")
                st.warning(
                    f"Generated message was empty or too long for {client_ig_username}. Using basic fallback.")

            # Final Fallback to simpler message generation
            logger.info(
                f"Falling back to basic generation for {client_ig_username}.")
            return generate_follow_up_message(conversation_data)

        # If we got here, generation was successful with one of the models
        logger.info(
            f"Generated AI follow-up for {client_ig_username}: '{follow_up_message}'")
        return follow_up_message

    # This outer except block catches errors *before* API call attempt (e.g., config)
    except Exception as e:
        # --- Enhanced Error Logging ---
        error_message = f"Error generating AI follow-up for {conversation_data.get('ig_username', 'unknown')}: {type(e).__name__} - {str(e)}"
        logger.error(error_message, exc_info=True)

        # Attempt to extract status code if it's an API error
        status_code = getattr(
            e, 'status_code', None) or getattr(e, 'code', None)
        if status_code:
            error_message += f" (Status Code: {status_code})"
            st.error(
                f"API Error ({status_code}) generating follow-up: {str(e)}")
        else:
            st.error(f"Error generating AI follow-up: {str(e)}")
        # --- End Enhanced Error Logging ---

        # Fallback to regular follow-up message if generation fails
        # Return None or raise exception? Returning fallback for now.
        return generate_follow_up_message(conversation_data)


def generate_follow_up_message(conversation_data):
    """Generate a casual, friendly follow-up message based on previous conversations - used as fallback"""

    # Get the user name if available from various possible locations
    client_ig_username = conversation_data.get("ig_username") or "there"
    client_analysis = conversation_data.get("client_analysis", {})
    profile_bio = client_analysis.get("profile_bio", {})
    client_name = profile_bio.get("PERSON NAME") or profile_bio.get(
        "person_name") or client_ig_username or "there"

    # Extract basic interests if available
    interests = []
    if profile_bio and profile_bio.get("INTERESTS"):
        interests = profile_bio.get("INTERESTS")
    elif profile_bio and profile_bio.get("interests"):
        interests = profile_bio.get("interests")

    # Basic follow-up templates
    general_templates = [
        "How's your fitness journey going? 💪",
        "Been crushing any good workouts lately?",
        "Any fitness goals you're working on this week? 🏋️",
        "Curious if you've tried any new exercises lately? 🏃‍♀️",
        "How's your nutrition been this week? 🥗",
        "Have you been keeping active? 💯"
    ]

    # Interest-based templates if interests are available
    interest_templates = {
        "workout": [
            "How are those workouts going? Making progress? 💪",
            "Still hitting those training sessions? How's it feeling?",
            "Made any gains with your workout routine lately? 🏋️"
        ],
        "nutrition": [
            "How's your meal plan working for you? 🥗",
            "Been keeping up with your nutrition goals?",
            "Found any good healthy recipes lately? 🍲"
        ],
        "weight loss": [
            "How's your weight loss journey progressing? 📉",
            "Still on track with your goals? How can I help?",
            "Any challenges with your weight loss program lately?"
        ],
        "muscle": [
            "How's the muscle building going? 💪",
            "Been hitting your protein goals for those gains?",
            "Any new PRs in your strength training lately? 🏋️"
        ],
        "cardio": [
            "How's your cardio training going? 🏃‍♀️",
            "Hit any new running or cardio milestones?",
            "Been keeping up with your cardio sessions?"
        ]
    }

    # Try to find match with interests
    matching_templates = []
    if interests:
        for interest in interests:
            interest_lower = interest.lower()
            for key, templates in interest_templates.items():
                if key in interest_lower:
                    matching_templates.extend(templates)

    # If we found interest-based templates, use those, otherwise use general
    if matching_templates:
        return random.choice(matching_templates)
    else:
        return random.choice(general_templates)


def delete_scheduled_followup(username):
    """Delete a scheduled followup for a specific username"""
    global SCHEDULED_FOLLOWUPS

    if username in SCHEDULED_FOLLOWUPS:
        # Remove this user from scheduled followups
        SCHEDULED_FOLLOWUPS.pop(username)
        # Save the updated scheduled followups
        save_scheduled_followups()
        return True
    return False
