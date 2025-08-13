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

# Your ManyChat API key
MANYCHAT_API_KEY = "996573:5b6dc180662de1be343655db562ee918"

# Define constants
ACTIVE_WINDOW = 3600  # 1 hour in seconds
ANALYTICS_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "analytics_data.json")
AUTO_FOLLOWUP_ENABLED = False
SCHEDULED_FOLLOWUPS = {}

# Verify file exists at startup
if not os.path.exists(ANALYTICS_FILE_PATH):
    print(f"Warning: Analytics file not found at {ANALYTICS_FILE_PATH}")
    # Try parent directory as fallback
    parent_path = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), "analytics_data.json")
    if os.path.exists(parent_path):
        ANALYTICS_FILE_PATH = parent_path
        print(
            f"Found analytics file in parent directory: {ANALYTICS_FILE_PATH}")

# Helper Functions


def get_client_status_category(user_data):
    """Determine the client's status category based on their data"""
    # Get the first message timestamp
    first_message_timestamp = None
    conversation_history = user_data.get("conversation_history", [])
    if conversation_history:
        first_message = conversation_history[0]
        first_message_timestamp = parse_timestamp(
            first_message.get("timestamp"))

    # Get whether they're a paying client
    is_paying = user_data.get("is_paying_client", False)

    if is_paying:
        return "💰 Paying Client"

    if first_message_timestamp:
        now = datetime.now(timezone.utc)
        days_since_first_message = (now - first_message_timestamp).days

        if days_since_first_message <= 7:  # First week
            return "🆕 Trial - Week 1"
        elif days_since_first_message <= 21:  # 2-3rd week
            return "📅 Trial - Week 2-3"
        elif days_since_first_message <= 30:  # Last week
            return "⚠️ Trial - Final Week"

    return "❓ Unknown Status"


def calculate_overall_quality_score(conversation_metrics):
    """Calculate an overall quality score for a conversation"""
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


def generate_ai_follow_up_message(conversation_data):
    """Generate a personalized follow-up message using Gemini AI"""
    try:
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
        client_analysis = conversation_data.get("client_analysis", {})
        profile_bio = client_analysis.get("profile_bio", {})

        # Gather all available information
        interests = profile_bio.get(
            "INTERESTS") or profile_bio.get("interests") or []
        lifestyle = profile_bio.get(
            "LIFESTYLE") or profile_bio.get("lifestyle")
        personality = profile_bio.get("PERSONALITY TRAITS") or profile_bio.get(
            "personality_traits") or []
        fitness_goals = profile_bio.get(
            "FITNESS GOALS") or profile_bio.get("fitness_goals") or []
        conversation_topics = client_analysis.get("conversation_topics", [])
        key_insights = client_analysis.get("key_insights", [])

        # Get conversation metrics
        total_messages = conversation_data.get("total_messages", 0)
        user_messages = conversation_data.get("user_messages", 0)
        response_rate = conversation_data.get("response_rate", 0)
        conversation_rating = conversation_data.get("conversation_rating", "")

        # Get recent conversation history
        history = conversation_data.get("conversation_history", [])
        history_text = ""
        if history:
            recent_history = history[-15:] if len(history) > 15 else history
            for msg in recent_history:
                sender = "Coach" if msg.get("type") == "ai" else "Client"
                history_text += f"{sender}: {msg.get('text', '')}\n"
        else:
            history_text = "No previous conversation history available."

        # Build detailed profile info text
        profile_info_text = "Client Profile Information:\n"

        if interests:
            profile_info_text += f"- Interests: {', '.join(interests)}\n"
        if lifestyle and lifestyle not in ["Unknown", ""]:
            profile_info_text += f"- Lifestyle: {lifestyle}\n"
        if personality:
            profile_info_text += f"- Personality Traits: {', '.join(personality)}\n"
        if fitness_goals:
            profile_info_text += f"- Fitness Goals: {', '.join(fitness_goals)}\n"
        if conversation_topics:
            profile_info_text += f"- Recent Topics: {', '.join(conversation_topics)}\n"
        if key_insights:
            profile_info_text += f"- Key Insights: {', '.join(key_insights)}\n"

        # Add engagement metrics
        profile_info_text += f"\nEngagement Level:\n"
        profile_info_text += f"- Total Messages: {total_messages}\n"
        profile_info_text += f"- Response Rate: {response_rate}%\n"
        if conversation_rating:
            profile_info_text += f"- Conversation Rating: {conversation_rating}\n"

        # Add inactivity context
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
                        follow_up_context = f"\nThis user has been inactive for {days_inactive} days."
            except Exception:
                pass

        prompt = f"""You are Shannon, a Fitness Coach and owner of Coco's Connected fitness business. Create a follow-up message for a client.

Profile Info:
{profile_info_text}

Chat History:
{history_text}
{follow_up_context}

Instructions:
1. Keep it brief and casual (5-25 words)
2. Include one relevant emoji
3. Reference their specific interests, goals, or previous conversations
4. Make it personal and engaging without using their name or username
5. If they have fitness goals, try to reference them
6. If they discussed specific topics, consider following up on those
7. Output ONLY the message text
8. NEVER include their Instagram username or real name
9. Match their communication style based on personality traits

Example: "How's that new workout split working for you? 💪"
"""

        # Try primary model first
        try:
            model = genai.GenerativeModel(
                'gemini-2.0-flash-thinking-exp-01-21')
            response = model.generate_content(prompt)
            follow_up_message = response.text.strip()
        except Exception as e:
            # If primary model fails (e.g., rate limit), try fallback model
            if "429" in str(e):
                logger.info(
                    "Primary model rate limited, trying fallback model...")
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                follow_up_message = response.text.strip()
            else:
                raise e

        if not follow_up_message or len(follow_up_message.split()) > 30:
            # Use more personalized templates based on profile
            templates = [
                "How's your fitness journey going? 💪",
                "Been crushing any good workouts lately?",
                "Any fitness goals you're working on this week? 🏋️",
                "Curious if you've tried any new exercises lately? 🏃‍♀️",
                "How's your nutrition been this week? 🥗",
                "Have you been keeping active? 💯"
            ]

            # Add goal-specific templates if available
            if fitness_goals:
                templates.extend([
                    f"Making progress on your {goal.lower()} goal? 💪" for goal in fitness_goals[:2]
                ])

            # Add interest-specific templates if available
            if interests:
                templates.extend([
                    f"How's the {interest.lower()} training going? 🎯" for interest in interests[:2]
                ])

            follow_up_message = random.choice(templates)

        # Double check to ensure no names are in the message
        if "name" in profile_bio:
            name = profile_bio.get(
                "PERSON NAME") or profile_bio.get("person_name")
            if name and name.lower() in follow_up_message.lower():
                follow_up_message = random.choice(templates)

        return follow_up_message

    except Exception as e:
        logger.error(f"Error generating AI follow-up message: {e}")
        return "Hey! How's your fitness journey going? 💪"


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

    # Add Client Status Section at the top
    st.markdown("### 👤 Client Status")
    status_col1, status_col2 = st.columns([1, 1])

    with status_col1:
        # Get client status
        client_status = get_client_status_category(user_data)
        st.info(f"Status: {client_status}")

        # Paying Client Toggle
        is_paying = user_data.get("is_paying_client", False)
        if st.toggle("Paying Client", value=is_paying, key=f"paying_toggle_{selected_user['id']}"):
            if not is_paying:  # Only update if it's a change
                user_data["is_paying_client"] = True
                user_data["payment_start_date"] = datetime.now(
                    timezone.utc).isoformat()
                st.success("Marked as paying client!")
                # Save the updated data
                st.session_state.conversation_metrics[selected_user["id"]] = user_data
                analytics.export_analytics()

    with status_col2:
        # Trial Status Information
        trial_start = None
        conversation_history = user_data.get("conversation_history", [])
        if conversation_history:
            first_message = conversation_history[0]
            trial_start = parse_timestamp(first_message.get("timestamp"))

        if trial_start:
            now = datetime.now(timezone.utc)
            days_in_trial = (now - trial_start).days
            if days_in_trial <= 30 and not is_paying:
                days_remaining = 30 - days_in_trial
                st.info(
                    f"Trial Status: Day {days_in_trial}/30 ({days_remaining} days remaining)")
            elif is_paying:
                payment_start = parse_timestamp(
                    user_data.get("payment_start_date"))
                if payment_start:
                    days_as_client = (now - payment_start).days
                    st.success(f"Paying Client for {days_as_client} days")
            else:
                st.warning("Trial Period Ended")

    st.markdown("---")

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
                        if load_followup_manager():
                            # Get or create driver
                            driver = followup_manager.get_driver()
                            if not driver:
                                driver = followup_manager.setup_driver()

                            if driver:
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
        # Create two columns for Generate AI Message and Send Now buttons
        gen_col, send_col = st.columns(2)

        with gen_col:
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

        with send_col:
            # Send Now button (only enabled if there's a generated message)
            if st.button("📨 Send Now", key=f"send_now_{selected_user['id']}",
                         disabled=f"direct_msg_{selected_user['id']}" not in st.session_state):
                message_to_send = st.session_state.get(
                    f"direct_msg_{selected_user['id']}", "")
                if message_to_send:
                    with st.spinner(f"Sending message to {username}..."):
                        try:
                            if load_followup_manager():
                                driver = followup_manager.get_driver()
                                if not driver:
                                    driver = followup_manager.setup_driver()

                                if driver:
                                    result = followup_manager.send_follow_up_message(
                                        driver,
                                        username,
                                        message_to_send
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
                                            "message": message_to_send,
                                            "sent_via_instagram": True
                                        })

                                        # Save updates
                                        st.session_state.conversation_metrics[selected_user["id"]] = user_data
                                        analytics.export_analytics()

                                        st.success(
                                            f"Follow-up message sent to {username} successfully!")
                                        # Clear the message
                                        st.session_state[f"direct_msg_{selected_user['id']}"] = ""
                                        st.rerun()
                                    else:
                                        st.error(
                                            f"Failed to send message: {result.get('error', 'Unknown error')}")
                                else:
                                    st.error("Failed to setup browser")
                        except Exception as e:
                            st.error(f"Error sending message: {e}")
                else:
                    st.error("No message to send. Generate a message first.")

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
    st.subheader("📋 User Profile & Analysis")

    # Create three columns for different aspects of the profile
    profile_col1, profile_col2, profile_col3 = st.columns([1, 1, 1])

    with profile_col1:
        st.markdown("### 👤 Basic Info")
        client_analysis = user_data.get("client_analysis", {})
        profile_bio = client_analysis.get("profile_bio", {})

        # Display basic profile information
        if profile_bio:
            if "PERSON NAME" in profile_bio or "person_name" in profile_bio:
                st.write("**Name:**", profile_bio.get("PERSON NAME")
                         or profile_bio.get("person_name"))
            if "AGE" in profile_bio or "age" in profile_bio:
                st.write("**Age:**", profile_bio.get("AGE")
                         or profile_bio.get("age"))
            if "LOCATION" in profile_bio or "location" in profile_bio:
                st.write("**Location:**", profile_bio.get("LOCATION")
                         or profile_bio.get("location"))
            if "OCCUPATION" in profile_bio or "occupation" in profile_bio:
                st.write("**Occupation:**", profile_bio.get("OCCUPATION")
                         or profile_bio.get("occupation"))
        else:
            st.info("No basic profile information available")

    with profile_col2:
        st.markdown("### 🎯 Interests & Lifestyle")
        if profile_bio:
            # Display interests
            interests = profile_bio.get(
                "INTERESTS") or profile_bio.get("interests") or []
            if interests:
                st.write("**Interests:**")
                for interest in interests:
                    st.write(f"• {interest}")

            # Display lifestyle information
            lifestyle = profile_bio.get(
                "LIFESTYLE") or profile_bio.get("lifestyle")
            if lifestyle and lifestyle not in ["Unknown", ""]:
                st.write("**Lifestyle:**", lifestyle)

            # Display personality traits
            personality = profile_bio.get("PERSONALITY TRAITS") or profile_bio.get(
                "personality_traits") or []
            if personality:
                st.write("**Personality Traits:**")
                for trait in personality:
                    st.write(f"• {trait}")
        else:
            st.info("No interests or lifestyle information available")

    with profile_col3:
        st.markdown("### 💬 Conversation Analysis")
        # Display conversation rating and summary
        rating = user_data.get("conversation_rating")
        if rating:
            st.write("**Conversation Rating:**", rating)
        summary = user_data.get("conversation_summary")
        if summary:
            st.write("**Summary:**", summary)

        # Display fitness goals if available
        if profile_bio:
            fitness_goals = profile_bio.get(
                "FITNESS GOALS") or profile_bio.get("fitness_goals") or []
            if fitness_goals:
                st.write("**Fitness Goals:**")
                for goal in fitness_goals:
                    st.write(f"• {goal}")

    # Add Conversation Topics Section
    st.markdown("### 🗣️ Conversation Topics")
    topics = client_analysis.get("conversation_topics", [])
    if topics:
        # Create columns for topics
        topic_cols = st.columns(3)
        for idx, topic in enumerate(topics):
            with topic_cols[idx % 3]:
                st.write(f"• {topic}")
    else:
        st.info("No conversation topics analyzed yet")

    # Add Engagement Metrics
    st.markdown("### 📊 Engagement Metrics")
    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)

    with metrics_col1:
        st.metric("Messages Sent", user_data.get("user_messages", 0))

    with metrics_col2:
        st.metric("Response Rate", f"{user_data.get('response_rate', 0)}%")

    with metrics_col3:
        st.metric("Questions Asked", user_data.get("questions_asked", 0))

    with metrics_col4:
        st.metric("Questions Answered", user_data.get("questions_answered", 0))

    # Add Key Insights Section
    st.markdown("### 🔍 Key Insights")
    insights = client_analysis.get("key_insights", [])
    if insights:
        for insight in insights:
            st.write(f"• {insight}")
    else:
        st.info("No key insights available yet")

    st.markdown("---")

    # Continue with existing conversation history display
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

# Helper Functions


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


def format_timestamp(timestamp_str):
    """Format a timestamp string into a readable format"""
    if not timestamp_str:
        return "Unknown"

    try:
        dt = parse_timestamp(timestamp_str)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass

    return timestamp_str


def needs_followup(user_data):
    """Check if a user needs follow-up based on their data"""
    if not user_data:
        return False

    try:
        last_message_time = user_data.get("last_message_timestamp")
        if not last_message_time:
            return False

        last_dt = parse_timestamp(last_message_time)
        if not last_dt:
            return False

        now = datetime.now(timezone.utc)
        time_diff = now - last_dt

        # Get message count for engagement level
        message_count = user_data.get("user_messages", 0)

        # Determine follow-up timing based on engagement
        if message_count >= 51:
            required_inactive_hours = 48  # High responders: 48 hours
        elif message_count >= 11:
            required_inactive_hours = 120  # Medium responders: 5 days
        else:
            required_inactive_hours = 168  # Low responders: 7 days

        hours_inactive = time_diff.total_seconds() / 3600

        # Check if enough time has passed
        if hours_inactive >= required_inactive_hours:
            # Check if we've already followed up recently
            last_followup = user_data.get("last_follow_up_date")
            if last_followup:
                last_followup_dt = parse_timestamp(last_followup)
                if last_followup_dt:
                    days_since_followup = (now - last_followup_dt).days
                    if days_since_followup < 7:  # Don't follow up more than once a week
                        return False
            return True

    except Exception as e:
        logger.error(f"Error checking follow-up status: {e}")

    return False


def schedule_followup(username, message):
    """Schedule a follow-up message for a user"""
    if not username or not message:
        return False

    # Default to 24 hours from now
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=24)

    # Add to scheduled followups
    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time.isoformat(),
        "status": "pending"
    })

    return True


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


def display_scheduled_list():
    """Display the list of scheduled follow-ups"""
    if not SCHEDULED_FOLLOWUPS:
        st.info("No scheduled follow-ups")
        return

    for username, followups in SCHEDULED_FOLLOWUPS.items():
        for followup in followups:
            with st.expander(f"Follow-up for @{username}"):
                st.write("**Scheduled Time:**",
                         format_timestamp(followup["scheduled_time"]))
                st.write("**Message:**", followup["message"])
                st.write("**Status:**", followup["status"])

                if followup["status"] == "pending":
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Send Now", key=f"send_{username}"):
                            try:
                                # Load followup_manager
                                if load_followup_manager():
                                    with st.spinner(f"Sending to @{username}..."):
                                        # Get or create driver
                                        driver = followup_manager.get_driver()
                                        if not driver:
                                            driver = followup_manager.setup_driver()

                                        if driver:
                                            result = followup_manager.send_follow_up_message(
                                                driver,
                                                username,
                                                followup["message"]
                                            )

                                            if result.get("success", False):
                                                followup["status"] = "sent"
                                                st.success(
                                                    "Message sent successfully!")
                                                st.rerun()
                                            else:
                                                st.error(
                                                    f"Failed to send: {result.get('error', 'Unknown error')}")
                                        else:
                                            st.error("Failed to setup browser")
                            except Exception as e:
                                st.error(f"Error sending message: {e}")

                    with col2:
                        if st.button("Cancel", key=f"cancel_{username}"):
                            if delete_scheduled_followup(username):
                                st.success("Follow-up cancelled")
                                st.rerun()


def display_sent_list():
    """Display the list of sent follow-ups"""
    sent_followups = []

    # Collect sent follow-ups from conversation metrics
    for user_id, user_data in st.session_state.conversation_metrics.items():
        username = user_data.get("ig_username", user_id)
        history = user_data.get("follow_up_history", [])

        for followup in history:
            if isinstance(followup, dict):
                sent_followups.append({
                    "username": username,
                    "date": followup.get("date"),
                    "message": followup.get("message", "No message content")
                })

    if sent_followups:
        # Sort by date, newest first
        sent_followups.sort(key=lambda x: x.get("date", ""), reverse=True)

        for followup in sent_followups:
            with st.expander(f"@{followup['username']} - {format_timestamp(followup['date'])}"):
                st.write(followup["message"])
    else:
        st.info("No follow-ups have been sent yet")


def display_scheduled_followups():
    """Display the scheduled follow-ups section"""
    st.header("Scheduled Follow-ups")

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Needs Follow-up", "Scheduled", "Sent"])

    with tab1:
        st.subheader("Users Needing Follow-up")
        global_metrics, conversation_metrics = load_analytics_data()

        # Get all users who need follow-up
        users_needing_followup = []
        for user_id, data in conversation_metrics.items():
            if needs_followup(data):
                last_message_time = data.get("last_message_timestamp")
                if last_message_time:
                    try:
                        last_dt = parse_timestamp(last_message_time)
                        if last_dt:
                            now = datetime.now(timezone.utc)
                            time_diff = now - last_dt
                            hours_inactive = time_diff.total_seconds() / 3600
                            users_needing_followup.append({
                                "id": user_id,
                                "username": data.get("ig_username", user_id),
                                "hours_inactive": hours_inactive,
                                "data": data
                            })
                    except Exception as e:
                        logger.error(f"Error processing user {user_id}: {e}")

        # Sort users by hours inactive
        users_needing_followup.sort(
            key=lambda x: x["hours_inactive"], reverse=True)

        if users_needing_followup:
            st.write(
                f"Found {len(users_needing_followup)} users needing follow-up")

            # Add bulk generate button
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("🤖 Generate All Follow-up Messages", key="bulk_generate"):
                    with st.spinner("Generating personalized follow-up messages..."):
                        progress_bar = st.progress(0)
                        for idx, user in enumerate(users_needing_followup):
                            # Generate message
                            follow_up_message = generate_ai_follow_up_message(
                                user["data"])
                            message_key = f"message_{user['id']}"
                            st.session_state[message_key] = follow_up_message
                            # Update progress
                            progress = (idx + 1) / len(users_needing_followup)
                            progress_bar.progress(progress)
                        st.success("Generated all follow-up messages!")
                        st.rerun()

            with col2:
                if st.button("📅 Schedule All", key="bulk_schedule", disabled="bulk_generate" not in st.session_state):
                    with st.spinner("Scheduling follow-ups..."):
                        scheduled_count = 0
                        for user in users_needing_followup:
                            message_key = f"message_{user['id']}"
                            if message_key in st.session_state:
                                schedule_followup(
                                    user["username"], st.session_state[message_key])
                                scheduled_count += 1
                        st.success(f"Scheduled {scheduled_count} follow-ups!")
                        st.rerun()

            # Display individual users
            for user in users_needing_followup:
                username = user["username"]
                hours = user["hours_inactive"]
                days = int(hours / 24)

                with st.expander(f"@{username} - Inactive for {days} days"):
                    user_data = user["data"]

                    # Display user info
                    st.write("Last Active:", format_timestamp(
                        user_data.get("last_message_timestamp", "")))
                    st.write("Engagement Level:", user_data.get(
                        "engagement_level", "Unknown"))

                    message_key = f"message_{user['id']}"
                    if message_key in st.session_state:
                        # Show generated message
                        st.text_area(
                            "Generated Message:", st.session_state[message_key], key=f"display_{user['id']}")
                        if st.button("Schedule Follow-up", key=f"schedule_{user['id']}"):
                            schedule_followup(
                                username, st.session_state[message_key])
                            st.success(f"Follow-up scheduled for @{username}")
                            st.rerun()
                    else:
                        # Generate individual message button
                        if st.button(f"Generate Follow-up for @{username}", key=f"gen_{user['id']}"):
                            with st.spinner("Generating personalized follow-up message..."):
                                follow_up_message = generate_ai_follow_up_message(
                                    user_data)
                                st.session_state[message_key] = follow_up_message
                                st.rerun()
        else:
            st.info("No users currently need follow-up!")

    with tab2:
        st.subheader("Scheduled Follow-ups")
        display_scheduled_list()

    with tab3:
        st.subheader("Sent Follow-ups")
        display_sent_list()


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
        st.write("Debug: Attempting to load analytics data...")
        # Try to load with UTF-8 encoding first
        with open(ANALYTICS_FILE_PATH, 'r', encoding='utf-8') as f:
            st.write(f"Debug: Successfully opened file: {ANALYTICS_FILE_PATH}")
            data = json.load(f)
            st.write("Debug: Successfully parsed JSON data")

            # Get global metrics
            analytics.global_metrics = data.get('global_metrics', {})

            # Get conversations from the correct key
            conversations = data.get('conversations', {})

            # Process each conversation
            processed_conversations = {}
            for user_id, conv_data in conversations.items():
                # Extract metrics from the nested structure
                metrics = conv_data.get('metrics', {})
                if metrics:
                    processed_conversations[user_id] = metrics

            analytics.conversation_metrics = processed_conversations

            # Add debug info about what was loaded
            num_conversations = len(analytics.conversation_metrics)
            st.write(f"Debug: Found {num_conversations} conversations")
            if num_conversations > 0:
                # Show sample of what we found
                sample_id = next(iter(analytics.conversation_metrics))
                sample_data = analytics.conversation_metrics[sample_id]
                st.write("Debug: Sample conversation data:", {
                    "id": sample_id,
                    "username": sample_data.get("ig_username"),
                    "total_messages": sample_data.get("total_messages"),
                    "has_history": bool(sample_data.get("conversation_history"))
                })
            else:
                st.warning("Warning: No conversations found in the data file")

            return analytics.global_metrics, analytics.conversation_metrics

    except UnicodeDecodeError:
        st.error("Error: Failed to decode file with UTF-8 encoding")
        try:
            # Fallback to default encoding if UTF-8 fails
            analytics.load_analytics()
            return analytics.global_metrics, analytics.conversation_metrics
        except Exception as e:
            st.error(
                f"Error: Failed to load analytics with default encoding: {str(e)}")
            return {}, {}
    except FileNotFoundError:
        st.error(f"Error: Could not find file at {ANALYTICS_FILE_PATH}")
        return {}, {}
    except json.JSONDecodeError as e:
        st.error(f"Error: Invalid JSON in file: {str(e)}")
        return {}, {}
    except Exception as e:
        st.error(f"Error: Unexpected error loading analytics data: {str(e)}")
        st.write("Debug: Full error:", str(e))
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

# Initialize analysis state in session state if not present
if 'analysis_running' not in st.session_state:
    st.session_state.analysis_running = False
if 'analysis_progress' not in st.session_state:
    st.session_state.analysis_progress = 0
if 'analysis_total' not in st.session_state:
    st.session_state.analysis_total = 0
if 'analysis_processed' not in st.session_state:
    st.session_state.analysis_processed = 0
if 'analysis_status' not in st.session_state:
    st.session_state.analysis_status = ""

# Sidebar
st.sidebar.title("Analytics Dashboard")

# Add refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.success("Data refreshed successfully!")

# Add Analysis Button to Sidebar
st.sidebar.markdown("---")
st.sidebar.header("Conversation Analysis")

# Create containers in sidebar for analysis status
status_container = st.sidebar.empty()
progress_container = st.sidebar.empty()
results_container = st.sidebar.empty()

# Show current analysis status if running
if st.session_state.analysis_running:
    status_container.info(st.session_state.analysis_status)
    if st.session_state.analysis_total > 0:
        progress_container.progress(st.session_state.analysis_progress)
        results_container.text(
            f"Processed: {st.session_state.analysis_processed}/{st.session_state.analysis_total}")


def start_analysis():
    if st.session_state.analysis_running:
        status_container.warning("Analysis already in progress...")
        return

    st.session_state.analysis_running = True
    ANALYSIS_INACTIVITY_THRESHOLD = timedelta(hours=48)
    now = datetime.now(timezone.utc)
    conversations_to_analyze = []

    # Show initial status
    st.session_state.analysis_status = "Finding inactive conversations..."
    status_container.info(st.session_state.analysis_status)

    # Identify conversations needing analysis
    for user_id, user_data in st.session_state.conversation_metrics.items():
        if user_data.get("conversation_summary") is not None:
            continue

        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                last_active_dt = parse_timestamp(last_active_timestamp)
                if last_active_dt and (now - last_active_dt) > ANALYSIS_INACTIVITY_THRESHOLD:
                    conversations_to_analyze.append(user_id)
            except Exception as e:
                logger.warning(
                    f"Could not parse timestamp for analysis check on user {user_id}: {e}")

    if not conversations_to_analyze:
        st.session_state.analysis_status = "✓ No new conversations to analyze"
        status_container.success(st.session_state.analysis_status)
        st.session_state.analysis_running = False
    else:
        st.session_state.analysis_total = len(conversations_to_analyze)
        st.session_state.analysis_status = f"Analyzing {st.session_state.analysis_total} conversations..."
        status_container.info(st.session_state.analysis_status)
        analyzed_count = 0

        try:
            # Configure Gemini
            genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
            model = genai.GenerativeModel(
                'gemini-2.0-flash-thinking-exp-01-21')

            # Analyze each conversation
            for i, user_id in enumerate(conversations_to_analyze):
                user_data = st.session_state.conversation_metrics[user_id]
                try:
                    # Update progress
                    st.session_state.analysis_progress = (
                        i + 1) / st.session_state.analysis_total
                    st.session_state.analysis_processed = i + 1
                    progress_container.progress(
                        st.session_state.analysis_progress)
                    results_container.text(
                        f"Processed: {st.session_state.analysis_processed}/{st.session_state.analysis_total}")

                    # Prepare data for prompt
                    history = user_data.get("conversation_history", [])
                    client_analysis = user_data.get("client_analysis", {})
                    profile_bio = client_analysis.get("profile_bio", {})
                    key_metrics = {
                        "user_messages": user_data.get("user_messages", 0),
                        "ai_messages": user_data.get("ai_messages", 0),
                        "coaching_inquiries": user_data.get("coaching_inquiry_count", 0),
                        "signed_up": user_data.get("signup_recorded", False),
                        "offer_mentioned": user_data.get("offer_mentioned_in_conv", False)
                    }

                    history_text = "\n".join(
                        [f"{msg.get('type', 'unknown').capitalize()}: {msg.get('text', '')}" for msg in history])
                    profile_text = json.dumps(profile_bio, indent=2)
                    metrics_text = json.dumps(key_metrics, indent=2)

                    prompt = f"""
You are a conversation analyst reviewing interactions between a fitness coach (AI) and a potential client (User) on Instagram.
Analyze the provided conversation history, user profile, and key metrics.

**Conversation History:**
{history_text}

**User Profile Bio:**
{profile_text}

**Key Metrics:**
{metrics_text}

**Your Task:**
Provide a concise analysis of this conversation in two parts, separated by '***':
1.  **Rating:** Assign ONE category that best describes the conversation's outcome or potential: [Hot Lead, Warm Lead, Nurture, Signup, General Chat, Stalled, Inquiry Only].
2.  **Summary:** Briefly explain your rating (1-2 sentences).

**Example Output:**
Warm Lead***User showed interest in fitness goals and asked about programs, but didn't commit. Good potential for follow-up.

**Analysis:**
"""
                    # Call Gemini with retry logic
                    max_retries = 1
                    attempt = 0
                    analysis_text = None
                    while attempt <= max_retries:
                        try:
                            response = model.generate_content(prompt)
                            analysis_text = response.text.strip()
                            break
                        except Exception as e:
                            if "429" in str(e) and attempt < max_retries:
                                retry_delay_seconds = 10
                                st.session_state.analysis_status = f"Rate limit - retrying in {retry_delay_seconds}s..."
                                status_container.warning(
                                    st.session_state.analysis_status)
                                time.sleep(retry_delay_seconds)
                                attempt += 1
                            else:
                                raise e

                    # Parse rating and summary
                    if analysis_text and '***' in analysis_text:
                        parts = analysis_text.split('***', 1)
                        rating = parts[0].strip()
                        summary = parts[1].strip()
                    else:
                        rating = "Analysis Error"
                        summary = "Could not parse AI response."

                    # Store results
                    st.session_state.conversation_metrics[user_id]['conversation_rating'] = rating
                    st.session_state.conversation_metrics[user_id]['conversation_summary'] = summary
                    analyzed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error analyzing conversation for user {user_id}: {e}")
                    st.session_state.conversation_metrics[user_id]['conversation_rating'] = "Analysis Failed"
                    st.session_state.conversation_metrics[user_id][
                        'conversation_summary'] = f"Error: {e}"

                time.sleep(2)  # Small delay between API calls

            # Save updated analytics
            if analyzed_count > 0:
                try:
                    analytics.export_analytics()
                    st.session_state.analysis_status = f"✓ Analyzed {analyzed_count} conversations"
                    status_container.success(st.session_state.analysis_status)
                except Exception as e:
                    st.session_state.analysis_status = f"Failed to save: {str(e)}"
                    status_container.error(st.session_state.analysis_status)
            else:
                st.session_state.analysis_status = "No conversations were analyzed"
                status_container.warning(st.session_state.analysis_status)

        except Exception as e:
            st.session_state.analysis_status = f"Analysis error: {str(e)}"
            status_container.error(st.session_state.analysis_status)

        # Clear progress displays
        progress_container.empty()
        results_container.empty()
        st.session_state.analysis_running = False


# Add the analysis button that calls our function
if st.sidebar.button("Analyze Inactive Conversations (48h+)", disabled=st.session_state.analysis_running):
    start_analysis()

# Navigation
# Add "view_profile" to session state if not present
if 'view_profile' not in st.session_state:
    st.session_state.view_profile = None

# Determine default page based on view_profile state
default_nav_index = 0  # Default to Overview
if st.session_state.view_profile:
    default_nav_index = 1  # Switch to User Profiles if a profile is selected

# Add "AI Data Assistant" to the list of pages
nav_options = ["Overview", "User Profiles",
               "Scheduled Follow-ups", "Daily Report", "AI Data Assistant"]
selected_page = st.sidebar.radio(
    "Navigation",
    nav_options,
    index=default_nav_index  # Set index based on whether a profile is being viewed
)

# If user manually selected User Profiles, clear any previous selection
if selected_page == "User Profiles" and not st.session_state.view_profile:
    pass  # Or maybe clear view_profile? Depends on flow.

# If user selects Overview or AI Assistant, clear view_profile
if selected_page not in ["User Profiles", "Conversations"]:
    st.session_state.view_profile = None

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

    # Add new function for client status categorization
    def get_client_status_category(user_data):
        """Determine the client's status category based on their data"""
        # Get the first message timestamp
        first_message_timestamp = None
        conversation_history = user_data.get("conversation_history", [])
        if conversation_history:
            first_message = conversation_history[0]
            first_message_timestamp = parse_timestamp(
                first_message.get("timestamp"))

        # Get whether they're a paying client
        is_paying = user_data.get("is_paying_client", False)

        if is_paying:
            return "💰 Paying Client"

        if first_message_timestamp:
            now = datetime.now(timezone.utc)
            days_since_first_message = (now - first_message_timestamp).days

            if days_since_first_message <= 7:  # First week
                return "🆕 Trial - Week 1"
            elif days_since_first_message <= 21:  # 2-3rd week
                return "📅 Trial - Week 2-3"
            elif days_since_first_message <= 30:  # Last week
                return "⚠️ Trial - Final Week"
        else:
            return "❓ Unknown Status"

    # Sort users into categories
    high_responders = []
    medium_responders = []
    low_responders = []

    # Add new category lists
    free_trial_week1 = []
    free_trial_week2_3 = []
    free_trial_final = []
    paying_clients = []

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
        user_message_count = user_data.get("user_messages", 0)

        # Create user info dict including status and user message count
        user_info = {
            "id": user_id,
            "username": username,
            "total_message_count": total_message_count,
            "user_message_count": user_message_count,
            "is_active": is_active,
            "status_indicator": status_indicator
        }

        # Add to appropriate engagement category based on USER messages
        category = get_responder_category(user_data)
        if category == "High":
            high_responders.append(user_info)
        elif category == "Medium":
            medium_responders.append(user_info)
        elif category == "Low":
            low_responders.append(user_info)

        # Add to appropriate client status category
        client_status = get_client_status_category(user_data)
        if client_status == "💰 Paying Client":
            paying_clients.append(user_info)
        elif client_status == "🆕 Trial - Week 1":
            free_trial_week1.append(user_info)
        elif client_status == "📅 Trial - Week 2-3":
            free_trial_week2_3.append(user_info)
        elif client_status == "⚠️ Trial - Final Week":
            free_trial_final.append(user_info)

    # Sort each list by active status first (descending), then by TOTAL message count (descending)
    for responder_list in [high_responders, medium_responders, low_responders,
                           free_trial_week1, free_trial_week2_3, free_trial_final, paying_clients]:
        responder_list.sort(key=lambda x: (
            x["is_active"], x["total_message_count"]), reverse=True)

    # Display the responder tabs
    responder_tabs = st.tabs([
        "High Responders",
        "Medium Responders",
        "Low Responders",
        "Free Trial - Week 1",
        "Free Trial - Week 2-3",
        "Free Trial - Final Week",
        "Paying Clients"
    ])

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

            if st.button("View Profile", key="view_low_button"):
                st.session_state.view_profile = low_responders[selected_low_index]['id']
                st.rerun()
        else:
            st.info("No low responders found")

    # Display Free Trial - Week 1 tab
    with responder_tabs[3]:
        st.subheader(f"Free Trial - Week 1 ({len(free_trial_week1)})")
        if free_trial_week1:
            selected_week1_index = st.selectbox(
                "First Week Trial Users",
                options=range(len(free_trial_week1)),
                format_func=lambda i: f"{free_trial_week1[i]['status_indicator']} {free_trial_week1[i]['username']} - {free_trial_week1[i]['user_message_count']} user msgs",
                key="week1_select"
            )

            if st.button("View Profile", key="view_week1_button"):
                st.session_state.view_profile = free_trial_week1[selected_week1_index]['id']
                st.rerun()
        else:
            st.info("No users in their first trial week")

    # Display Free Trial - Week 2-3 tab
    with responder_tabs[4]:
        st.subheader(f"Free Trial - Week 2-3 ({len(free_trial_week2_3)})")
        if free_trial_week2_3:
            selected_week23_index = st.selectbox(
                "Week 2-3 Trial Users",
                options=range(len(free_trial_week2_3)),
                format_func=lambda i: f"{free_trial_week2_3[i]['status_indicator']} {free_trial_week2_3[i]['username']} - {free_trial_week2_3[i]['user_message_count']} user msgs",
                key="week23_select"
            )

            if st.button("View Profile", key="view_week23_button"):
                st.session_state.view_profile = free_trial_week2_3[selected_week23_index]['id']
                st.rerun()
        else:
            st.info("No users in weeks 2-3 of trial")

    # Display Free Trial - Final Week tab
    with responder_tabs[5]:
        st.subheader(f"Free Trial - Final Week ({len(free_trial_final)})")
        if free_trial_final:
            selected_final_index = st.selectbox(
                "Final Week Trial Users",
                options=range(len(free_trial_final)),
                format_func=lambda i: f"{free_trial_final[i]['status_indicator']} {free_trial_final[i]['username']} - {free_trial_final[i]['user_message_count']} user msgs",
                key="final_week_select"
            )

            if st.button("View Profile", key="view_final_button"):
                st.session_state.view_profile = free_trial_final[selected_final_index]['id']
                st.rerun()
        else:
            st.info("No users in their final trial week")

    # Display Paying Clients tab
    with responder_tabs[6]:
        st.subheader(f"Paying Clients ({len(paying_clients)})")
        if paying_clients:
            selected_paying_index = st.selectbox(
                "Paying Clients",
                options=range(len(paying_clients)),
                format_func=lambda i: f"{paying_clients[i]['status_indicator']} {paying_clients[i]['username']} - {paying_clients[i]['user_message_count']} user msgs",
                key="paying_select"
            )

            if st.button("View Profile", key="view_paying_button"):
                st.session_state.view_profile = paying_clients[selected_paying_index]['id']
                st.rerun()
        else:
            st.info("No paying clients found")

    # Add All Users section
    st.header("👥 All Users")

    # Get and sort all users
    all_users = []
    for user_id, user_data in st.session_state.conversation_metrics.items():
        username = user_data.get("ig_username") or user_id
        is_active = False
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                last_active_dt = parse_timestamp(last_active_timestamp)
                if last_active_dt:
                    time_diff = now - last_active_dt
                    if time_diff.total_seconds() < ACTIVE_WINDOW:
                        is_active = True
            except Exception:
                pass

        status_indicator = "🟢" if is_active else "🔴"
        client_status = get_client_status_category(user_data)
        message_count = user_data.get("total_messages", 0)
        user_message_count = user_data.get("user_messages", 0)

        all_users.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "user_message_count": user_message_count,
            "is_active": is_active,
            "status_indicator": status_indicator,
            "client_status": client_status
        })

    # Sort users by active status first, then by message count
    all_users.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

    # Add search functionality for all users
    search_query = st.text_input("🔍 Search users", "")
    filtered_users = all_users
    if search_query:
        filtered_users = [
            user for user in all_users if search_query.lower() in user["username"].lower()]
        if filtered_users:
            st.success(f"Found {len(filtered_users)} matching users")
        else:
            st.warning(f"No users found matching '{search_query}'")

    # Display all users in a grid layout
    cols = st.columns(3)
    for idx, user in enumerate(filtered_users):
        with cols[idx % 3]:
            with st.container():
                st.markdown(f"""
                    <div style='padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 5px 0;'>
                        <h4>{user['status_indicator']} {user['username']}</h4>
                        <p>{user['client_status']}</p>
                        <p>Messages: {user['user_message_count']}</p>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("View Profile", key=f"view_profile_{user['id']}"):
                    st.session_state.view_profile = user['id']
                    st.rerun()

    st.markdown("---")

    # Continue with the existing responder categories display
    st.header("📊 User Categories")

    # ... rest of the existing responder categories code ...

elif selected_page == "User Profiles":
    st.header("👥 User Profiles")

    # Debug information
    st.write("Debug: Keys in session state:", list(st.session_state.keys()))
    st.write("Debug: Number of conversations:", len(
        st.session_state.conversation_metrics))

    # Simple list of users
    for user_id, user_data in st.session_state.conversation_metrics.items():
        st.write("---")
        st.write(f"User ID: {user_id}")
        st.write(f"Username: {user_data.get('ig_username', 'Unknown')}")
        st.write(f"Total Messages: {user_data.get('total_messages', 0)}")
        st.write(f"User Messages: {user_data.get('user_messages', 0)}")

        if st.button(f"View Profile", key=f"view_{user_id}"):
            display_conversation({
                "id": user_id,
                "username": user_data.get("ig_username", user_id)
            })

elif selected_page == "Scheduled Follow-ups":
    display_scheduled_followups()

elif selected_page == "Daily Report":
    st.header("📅 Daily Report")

    # Get today's date
    today = datetime.now(timezone.utc).date()

    # Create columns for metrics
    col1, col2, col3 = st.columns(3)

    # Initialize counters
    today_conversations = 0
    hot_leads = []
    warm_leads = []
    total_messages_today = 0

    # Process conversation data
    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Check last message timestamp
        last_message_time = user_data.get("last_message_timestamp")
        if last_message_time:
            last_message_dt = parse_timestamp(last_message_time)
            if last_message_dt and last_message_dt.date() == today:
                today_conversations += 1
                total_messages_today += user_data.get("total_messages", 0)

        # Check conversation rating
        rating = user_data.get("conversation_rating")
        username = user_data.get("ig_username", user_id)
        if rating == "Hot Lead":
            hot_leads.append({
                "username": username,
                "last_active": last_message_time,
                "messages": user_data.get("total_messages", 0)
            })
        elif rating == "Warm Lead":
            warm_leads.append({
                "username": username,
                "last_active": last_message_time,
                "messages": user_data.get("total_messages", 0)
            })

    # Display metrics in columns
    with col1:
        st.metric("Today's Conversations", today_conversations)
        st.metric("Total Messages Today", total_messages_today)

    with col2:
        st.metric("Hot Leads", len(hot_leads))
        if hot_leads:
            with st.expander("View Hot Leads"):
                for lead in hot_leads:
                    st.write(f"👤 {lead['username']}")
                    if lead['last_active']:
                        last_active_dt = parse_timestamp(lead['last_active'])
                        if last_active_dt:
                            st.caption(
                                f"Last active: {last_active_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    st.caption(f"Total messages: {lead['messages']}")
                    st.markdown("---")

    with col3:
        st.metric("Warm Leads", len(warm_leads))
        if warm_leads:
            with st.expander("View Warm Leads"):
                for lead in warm_leads:
                    st.write(f"👤 {lead['username']}")
                    if lead['last_active']:
                        last_active_dt = parse_timestamp(lead['last_active'])
                        if last_active_dt:
                            st.caption(
                                f"Last active: {last_active_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    st.caption(f"Total messages: {lead['messages']}")
                    st.markdown("---")

    # Add activity timeline
    st.subheader("Today's Activity Timeline")

    # Create a list of today's activities
    today_activities = []
    for user_id, user_data in st.session_state.conversation_metrics.items():
        history = user_data.get("conversation_history", [])
        username = user_data.get("ig_username", user_id)

        for msg in history:
            timestamp = msg.get("timestamp")
            if timestamp:
                msg_dt = parse_timestamp(timestamp)
                if msg_dt and msg_dt.date() == today:
                    today_activities.append({
                        "time": msg_dt,
                        "username": username,
                        "type": msg.get("type"),
                        "text": msg.get("text")
                    })

    # Sort activities by time
    today_activities.sort(key=lambda x: x["time"], reverse=True)

    # Display timeline
    if today_activities:
        for activity in today_activities:
            time_str = activity["time"].strftime("%H:%M:%S")
            msg_type = "🤖" if activity["type"] == "ai" else "👤"
            st.markdown(f"**{time_str}** {msg_type} {activity['username']}")
            st.markdown(f"_{activity['text']}_")
            st.markdown("---")
    else:
        st.info("No activities recorded today yet.")

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


def display_scheduled_followups():
    """Display the scheduled follow-ups section"""
    st.header("Scheduled Follow-ups")

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Needs Follow-up", "Scheduled", "Sent"])

    with tab1:
        st.subheader("Users Needing Follow-up")
        global_metrics, conversation_metrics = load_analytics_data()

        # Get all users who need follow-up
        users_needing_followup = []
        for user_id, data in conversation_metrics.items():
            if needs_followup(data):
                last_message_time = data.get("last_message_timestamp")
                if last_message_time:
                    try:
                        last_dt = parse_timestamp(last_message_time)
                        if last_dt:
                            now = datetime.now(timezone.utc)
                            time_diff = now - last_dt
                            hours_inactive = time_diff.total_seconds() / 3600
                            users_needing_followup.append({
                                "id": user_id,
                                "username": data.get("ig_username", user_id),
                                "hours_inactive": hours_inactive,
                                "data": data
                            })
                    except Exception as e:
                        logger.error(f"Error processing user {user_id}: {e}")

        # Sort users by hours inactive
        users_needing_followup.sort(
            key=lambda x: x["hours_inactive"], reverse=True)

        if users_needing_followup:
            st.write(
                f"Found {len(users_needing_followup)} users needing follow-up")

            # Add bulk generate button
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("🤖 Generate All Follow-up Messages", key="bulk_generate"):
                    with st.spinner("Generating personalized follow-up messages..."):
                        progress_bar = st.progress(0)
                        for idx, user in enumerate(users_needing_followup):
                            # Generate message
                            follow_up_message = generate_ai_follow_up_message(
                                user["data"])
                            message_key = f"message_{user['id']}"
                            st.session_state[message_key] = follow_up_message
                            # Update progress
                            progress = (idx + 1) / len(users_needing_followup)
                            progress_bar.progress(progress)
                        st.success("Generated all follow-up messages!")
                        st.rerun()

            with col2:
                if st.button("📅 Schedule All", key="bulk_schedule", disabled="bulk_generate" not in st.session_state):
                    with st.spinner("Scheduling follow-ups..."):
                        scheduled_count = 0
                        for user in users_needing_followup:
                            message_key = f"message_{user['id']}"
                            if message_key in st.session_state:
                                schedule_followup(
                                    user["username"], st.session_state[message_key])
                                scheduled_count += 1
                        st.success(f"Scheduled {scheduled_count} follow-ups!")
                        st.rerun()

            # Display individual users
            for user in users_needing_followup:
                username = user["username"]
                hours = user["hours_inactive"]
                days = int(hours / 24)

                with st.expander(f"@{username} - Inactive for {days} days"):
                    user_data = user["data"]

                    # Display user info
                    st.write("Last Active:", format_timestamp(
                        user_data.get("last_message_timestamp", "")))
                    st.write("Engagement Level:", user_data.get(
                        "engagement_level", "Unknown"))

                    message_key = f"message_{user['id']}"
                    if message_key in st.session_state:
                        # Show generated message
                        st.text_area(
                            "Generated Message:", st.session_state[message_key], key=f"display_{user['id']}")
                        if st.button("Schedule Follow-up", key=f"schedule_{user['id']}"):
                            schedule_followup(
                                username, st.session_state[message_key])
                            st.success(f"Follow-up scheduled for @{username}")
                            st.rerun()
                    else:
                        # Generate individual message button
                        if st.button(f"Generate Follow-up for @{username}", key=f"gen_{user['id']}"):
                            with st.spinner("Generating personalized follow-up message..."):
                                follow_up_message = generate_ai_follow_up_message(
                                    user_data)
                                st.session_state[message_key] = follow_up_message
                                st.rerun()
        else:
            st.info("No users currently need follow-up!")

    with tab2:
        st.subheader("Scheduled Follow-ups")
        display_scheduled_list()

    with tab3:
        st.subheader("Sent Follow-ups")
        display_sent_list()


def needs_followup(user_data):
    """Check if a user needs follow-up based on their data"""
    if not user_data:
        return False

    try:
        last_message_time = user_data.get("last_message_timestamp")
        if not last_message_time:
            return False

        last_dt = parse_timestamp(last_message_time)
        if not last_dt:
            return False

        now = datetime.now(timezone.utc)
        time_diff = now - last_dt

        # Get message count for engagement level
        message_count = user_data.get("user_messages", 0)

        # Determine follow-up timing based on engagement
        if message_count >= 51:
            required_inactive_hours = 48  # High responders: 48 hours
        elif message_count >= 11:
            required_inactive_hours = 120  # Medium responders: 5 days
        else:
            required_inactive_hours = 168  # Low responders: 7 days

        hours_inactive = time_diff.total_seconds() / 3600

        # Check if enough time has passed
        if hours_inactive >= required_inactive_hours:
            # Check if we've already followed up recently
            last_followup = user_data.get("last_follow_up_date")
            if last_followup:
                last_followup_dt = parse_timestamp(last_followup)
                if last_followup_dt:
                    days_since_followup = (now - last_followup_dt).days
                    if days_since_followup < 7:  # Don't follow up more than once a week
                        return False
            return True

    except Exception as e:
        logger.error(f"Error checking follow-up status: {e}")

    return False


def format_timestamp(timestamp_str):
    """Format a timestamp string into a readable format"""
    if not timestamp_str:
        return "Unknown"

    try:
        dt = parse_timestamp(timestamp_str)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass

    return timestamp_str


def schedule_followup(username, message):
    """Schedule a follow-up message for a user"""
    if not username or not message:
        return False

    # Default to 24 hours from now
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=24)

    # Add to scheduled followups
    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time.isoformat(),
        "status": "pending"
    })

    return True


def display_scheduled_list():
    """Display the list of scheduled follow-ups"""
    if not SCHEDULED_FOLLOWUPS:
        st.info("No scheduled follow-ups")
        return

    for username, followups in SCHEDULED_FOLLOWUPS.items():
        for followup in followups:
            with st.expander(f"Follow-up for @{username}"):
                st.write("**Scheduled Time:**",
                         format_timestamp(followup["scheduled_time"]))
                st.write("**Message:**", followup["message"])
                st.write("**Status:**", followup["status"])

                if followup["status"] == "pending":
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Send Now", key=f"send_{username}"):
                            try:
                                # Load followup_manager
                                if load_followup_manager():
                                    with st.spinner(f"Sending to @{username}..."):
                                        # Get or create driver
                                        driver = followup_manager.get_driver()
                                        if not driver:
                                            driver = followup_manager.setup_driver()

                                        if driver:
                                            result = followup_manager.send_follow_up_message(
                                                driver,
                                                username,
                                                followup["message"]
                                            )

                                            if result.get("success", False):
                                                followup["status"] = "sent"
                                                st.success(
                                                    "Message sent successfully!")
                                                st.rerun()
                                            else:
                                                st.error(
                                                    f"Failed to send: {result.get('error', 'Unknown error')}")
                                        else:
                                            st.error("Failed to setup browser")
                            except Exception as e:
                                st.error(f"Error sending message: {e}")

                    with col2:
                        if st.button("Cancel", key=f"cancel_{username}"):
                            if delete_scheduled_followup(username):
                                st.success("Follow-up cancelled")
                                st.rerun()


def display_sent_list():
    """Display the list of sent follow-ups"""
    sent_followups = []

    # Collect sent follow-ups from conversation metrics
    for user_id, user_data in st.session_state.conversation_metrics.items():
        username = user_data.get("ig_username", user_id)
        history = user_data.get("follow_up_history", [])

        for followup in history:
            if isinstance(followup, dict):
                sent_followups.append({
                    "username": username,
                    "date": followup.get("date"),
                    "message": followup.get("message", "No message content")
                })

    if sent_followups:
        # Sort by date, newest first
        sent_followups.sort(key=lambda x: x.get("date", ""), reverse=True)

        for followup in sent_followups:
            with st.expander(f"@{followup['username']} - {format_timestamp(followup['date'])}"):
                st.write(followup["message"])
    else:
        st.info("No follow-ups have been sent yet")
