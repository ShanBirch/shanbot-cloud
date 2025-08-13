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


def should_follow_up(conversation_data):
    """Determine if we should follow up based on:
    - Previous follow-up attempts
    - Their response rate
    - Time since last follow-up
    """
    metrics = conversation_data.get("metrics", {})

    # Get follow-up history
    follow_ups_sent = metrics.get("follow_ups_sent", 0)
    follow_up_responses = metrics.get("follow_up_responses", 0)
    last_follow_up_date = metrics.get("last_follow_up_date")

    # Stop if we've hit maximum attempts
    MAX_FOLLOW_UPS = 3
    if follow_ups_sent >= MAX_FOLLOW_UPS:
        return False

    # Check response rate to follow-ups
    if follow_ups_sent > 0:
        response_rate = follow_up_responses / follow_ups_sent
        if response_rate == 0:
            return False
        elif response_rate < 0.5 and follow_ups_sent >= 2:
            return False

    # Get timing based on engagement
    timing = get_smart_follow_up_timing(conversation_data)
    now = datetime.now(timezone.utc)

    # Check for manual override
    if metrics.get("manual_override"):
        manual_date = metrics.get("manual_follow_up_date")
        if manual_date:
            manual_dt = datetime.fromisoformat(manual_date)
            # Allow follow-up within 1 hour window of manual time
            time_until_manual = manual_dt - now
            if timedelta(minutes=-30) <= time_until_manual <= timedelta(minutes=30):
                return True
            elif time_until_manual > timedelta(minutes=30):
                return False

    # If this isn't our first follow-up, ensure enough time has passed since the last one
    if last_follow_up_date:
        last_follow_up_dt = datetime.fromisoformat(
            last_follow_up_date.replace('Z', '+00:00'))
        time_since_last_follow_up = now - last_follow_up_dt

        # Wait at least 3 days between follow-ups
        if time_since_last_follow_up < timedelta(days=3):
            return False

    # Check if we're in the follow-up window
    if not timing.get('follow_up_start'):
        return False

    if now < timing['follow_up_start']:
        return False

    if now > timing['follow_up_end']:
        return False

    return True


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
    metrics = conversation_data.get("metrics", {})
    conversation_history = metrics.get("conversation_history", [])

    # Get engagement metrics
    engagement = analyze_engagement_level(metrics)

    # Simple casual openers
    casual_openers = [
        "Heya!",
        "Hey!",
        "Hey there!",
    ]

    # If no conversation history, use default message
    if not conversation_history:
        return f"{random.choice(casual_openers)} How's things? 💪"

    # Get last few user messages
    last_user_messages = [msg for msg in conversation_history
                          if msg.get("type") != "ai"][-5:]  # Get last 5 user messages

    if not last_user_messages:
        return f"{random.choice(casual_openers)} How's things? 💪"

    # Analyze the last few messages for topics
    def extract_topics(text):
        """Extract potential topics from a message"""
        text = text.lower()

        # Split into sentences and words
        sentences = text.split('.')
        words = text.split()

        topics = []

        # Common fitness-related terms to ignore in topic detection
        common_terms = {'the', 'and', 'was', 'is', 'are', 'been', 'have', 'had',
                        'going', 'doing', 'done', 'it', 'that', 'this', 'these',
                        'those', 'they', 'im', "i'm", 'ive', 'just', 'like', 'got'}

        # Look for nouns and key phrases
        for sentence in sentences:
            words = sentence.strip().split()

            # Find potential topics (nouns and important words)
            for i, word in enumerate(words):
                # Skip common terms
                if word in common_terms:
                    continue

                # Check for compound topics (e.g., "leg day", "meal prep")
                if i < len(words) - 1:
                    compound = f"{word} {words[i+1]}"
                    if any(term in compound for term in ['day', 'prep', 'training', 'session', 'workout']):
                        topics.append(compound)
                        continue

                # Individual topics
                if len(word) > 2:  # Skip very short words
                    topics.append(word)

        return topics

    # Analyze recent messages
    recent_topics = []
    for msg in last_user_messages:
        text = msg.get("text", "")
        if text:
            topics = extract_topics(text)
            recent_topics.extend(topics)

    # Get most recent significant topic
    if recent_topics:
        # Get the most recent topic that's not in common terms
        latest_topic = recent_topics[-1]

        # Generate contextual follow-up
        if any(term in latest_topic for term in ['squat', 'bench', 'deadlift', 'lift']):
            message = f"{random.choice(casual_openers)} How's the {latest_topic} going? 💪"
        elif 'sore' in latest_topic or 'doms' in latest_topic:
            message = f"{random.choice(casual_openers)} Still sore from last session? 😅"
        elif any(term in latest_topic for term in ['work', 'job', 'business']):
            message = f"{random.choice(casual_openers)} How's {latest_topic} going? Still keeping you busy?"
        elif any(term in latest_topic for term in ['food', 'diet', 'meal', 'nutrition']):
            message = f"{random.choice(casual_openers)} How's the {latest_topic} going? 💪"
        elif 'sleep' in latest_topic or 'rest' in latest_topic:
            message = f"{random.choice(casual_openers)} Getting better {latest_topic}?"
        elif any(term in latest_topic for term in ['injury', 'pain', 'hurt']):
            message = f"{random.choice(casual_openers)} How's the {latest_topic}? Feeling better?"
        elif 'day' in latest_topic:  # e.g., "leg day", "rest day"
            message = f"{random.choice(casual_openers)} How was {latest_topic}? 💪"
        else:
            # For any other topic, use a generic but contextual follow-up
            message = f"{random.choice(casual_openers)} How's the {latest_topic} going?"
    else:
        # Default message if no specific topics found
        message = f"{random.choice(casual_openers)} How's training been? 💪"

    return message


def load_analytics_data(file_path):
    """Loads analytics data directly from the JSON file."""
    data = {"global_metrics": {}, "conversations": {}}  # Default structure
    try:
        # Ensure the directory exists (optional, but good practice)
        # os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "r") as f:
            data = json.load(f)

            # --- REMOVED DEBUG ---
            # --- END REMOVED DEBUG ---

            # Use success only if data is actually loaded and valid
            if data and ("global_metrics" in data or "conversations" in data):
                # Use sidebar for less intrusive success msg
                st.sidebar.success(
                    f"Loaded data from {os.path.basename(file_path)}")
            # Ensure nested structure exists
            if "global_metrics" not in data:
                data["global_metrics"] = {}
            if "conversations" not in data:
                data["conversations"] = {}
            return data
    except FileNotFoundError:
        st.sidebar.warning(
            f"Analytics file not found at {file_path}. Displaying empty dashboard.")
        return data  # Return default structure
    except json.JSONDecodeError:
        st.sidebar.error(
            f"Error decoding JSON from {file_path}. File might be corrupted.")
        return data  # Return default structure
    except Exception as e:
        st.sidebar.error(f"An error occurred loading data: {e}")
        return data  # Return default structure


# Dashboard title
st.set_page_config(page_title="Shannon Bot Analytics", layout="wide")
st.title("Shannon Bot Analytics Dashboard")

# --- Configuration ---
# Path to the persistent data
ANALYTICS_FILE_PATH = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "analytics_data.json")

# --- Removed Server Settings ---
# server_url = st.sidebar.text_input("Server URL", "http://localhost:8000")
# st.sidebar.markdown("---")

# Refresh settings
auto_refresh = st.sidebar.checkbox("Auto refresh", value=False)
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 10, 300, 30)

# --- Data Loading Function ---


# --- Load Data ---
analytics_data = load_analytics_data(ANALYTICS_FILE_PATH)
global_metrics = analytics_data.get("global_metrics", {})
conversations = analytics_data.get("conversations", {})

# --- Process Data for Responder Categories ---
responder_counts = defaultdict(int)
responder_lists = defaultdict(list)
# Define display order and labels with ranges
responder_order = ["High Responder", "Medium Responder",
                   "Low Responder", "No Responder", "N/A"]
RESPONDER_LABELS_WITH_RANGE = {
    "No Responder": "No Responder (0 msgs)",
    "Low Responder": "Low Responder (1-10 msgs)",
    "Medium Responder": "Medium Responder (11-50 msgs)",
    "High Responder": "High Responder (51+ msgs)",
    "N/A": "N/A"  # Keep N/A as is
}

if conversations:
    # --- REMOVED DEBUG CONTAINER ---

    for sub_id, conv_data in conversations.items():
        metrics = conv_data.get("metrics", {})
        category = metrics.get("responder_category", "N/A")

        # --- REMOVED DEBUGGING USERNAME LOOKUP ---
        identifier = metrics.get("ig_username", sub_id)   # Get with fallback
        # --- END REMOVED DEBUGGING ---

        # Prefer username from metrics, fallback to subscriber ID
        # identifier = metrics.get("ig_username", sub_id)

        # Ensure the category is one we expect, otherwise default to N/A
        if category not in responder_order:
            category = "N/A"

        responder_counts[category] += 1
        responder_lists[category].append(identifier)  # Store username or ID

    # --- REMOVED DEBUG CONTAINER END MARKER ---

else:
    # Put this message in the main area if no conversations exist at all
    pass  # Handle display later if conversations is empty


# Main dashboard content
tabs = st.tabs(["Overview", "Conversations",
               "Daily Report", "Analytics Export"])

# Overview tab
with tabs[0]:
    st.header("Overview")

    # Global Metrics Section - Consolidate all stats here
    st.subheader("📊 Global Metrics")

    # Create columns for metrics display
    global_cols = st.columns([1, 1, 1])

    with global_cols[0]:
        # Conversation stats
        st.markdown("**Conversation Stats**")
        total_conversations = global_metrics.get("total_conversations", 0)
        st.metric("Total Conversations", total_conversations)

        # Combine bot and webhook message counts
        total_bot_msgs = global_metrics.get(
            "bot_message_stats", {}).get("total_messages_sent", 0)
        total_ai_msgs = global_metrics.get("total_ai_messages", 0)
        st.metric("Total Messages Sent", total_ai_msgs + total_bot_msgs)

        # User Messages
        total_user_msgs = global_metrics.get("total_user_messages", 0)
        st.metric("Total User Messages", total_user_msgs)

        # Bot Message Stats
        total_sent = global_metrics.get(
            "bot_message_stats", {}).get("total_messages_sent", 0)
        st.metric("Bot Messages Sent", total_sent)

        # Question Metrics
        question_stats = global_metrics.get("question_stats", {})
        ai_questions = question_stats.get("ai_questions_asked", 0)
        # Calculate AI statements
        ai_statements = global_metrics.get(
            "total_ai_messages", 0) - ai_questions if global_metrics.get("total_ai_messages", 0) >= ai_questions else 0
        st.metric("AI Questions Asked", ai_questions)
        st.metric("AI Statements Made", ai_statements)

    with global_cols[1]:
        # Response metrics
        st.markdown("**Response Metrics**")

        # Calculate total responses across systems
        bot_responses = global_metrics.get(
            "bot_message_stats", {}).get("total_messages_responded", 0)
        webhook_responses = global_metrics.get(
            "question_stats", {}).get("user_responses_to_questions", 0)
        total_responses = bot_responses + webhook_responses

        # Calculate overall response rate
        total_ai_questions = global_metrics.get(
            "question_stats", {}).get("ai_questions_asked", 0)
        total_bot_messages = global_metrics.get(
            "bot_message_stats", {}).get("total_messages_sent", 0) or 0
        total_messages_expecting_response = total_ai_questions + total_bot_messages

        if total_messages_expecting_response > 0:
            overall_response_rate = (
                total_responses / total_messages_expecting_response) * 100
        else:
            overall_response_rate = 0

        st.metric("Total Responses Received", total_responses)
        st.metric("Overall Response Rate", f"{overall_response_rate:.1f}%")

        # Bot Response Stats
        total_responded = global_metrics.get(
            "bot_message_stats", {}).get("total_messages_responded", 0)
        bot_response_rate = (total_responded / total_sent *
                             100) if total_sent > 0 else 0
        st.metric("Bot Messages Responded To", total_responded)

        # Add Question Response Rate to the main Global Metrics
        question_stats = global_metrics.get("question_stats", {})
        ai_questions = question_stats.get("ai_questions_asked", 0)
        user_responses = question_stats.get("user_responses_to_questions", 0)
        question_response_rate = (
            user_responses / ai_questions * 100) if ai_questions > 0 else 0
        st.metric("Question Response Rate", f"{question_response_rate:.1f}%")

        # Calculate follow-up metrics
        st.metric("Follow-up Messages Sent",
                  global_metrics.get("follow_up_messages_sent", 0))

    with global_cols[2]:
        # Engagement metrics
        st.markdown("**Engagement Insights**")
        st.metric("Coaching Inquiries", global_metrics.get(
            "coaching_inquiries", 0))
        st.metric("AI Detections", global_metrics.get("ai_detections", 0))

        # Calculate conversation success metrics
        active_convs = global_metrics.get("active_conversations", 0)
        ended_convs = total_conversations - active_convs
        st.metric("Conversations Ended", ended_convs)

        # Calculate conversion metrics if available
        conversion_rate = 0
        if global_metrics.get("coaching_inquiries", 0) > 0 and total_conversations > 0:
            conversion_rate = (global_metrics.get(
                "coaching_inquiries", 0) / total_conversations) * 100
        st.metric("Inquiry Conversion Rate", f"{conversion_rate:.1f}%")

    # Daily Bot Activity Stats in a new row
    st.subheader("📈 Daily Activity")
    daily_cols = st.columns(2)
    bot_stats = global_metrics.get("bot_message_stats", {})

    with daily_cols[0]:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        st.write("**Today's Bot Statistics:**")
        st.metric("Messages Sent Today",
                  bot_stats.get("daily_messages_sent", {}).get(today, 0))
        st.metric("Messages Responded Today",
                  bot_stats.get("daily_messages_responded", {}).get(today, 0))

    with daily_cols[1]:
        # Create a chart of the last 7 days
        st.write("**Last 7 Days Activity:**")
        dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(7)][::-1]
        sent_counts = [bot_stats.get("daily_messages_sent", {}).get(
            date, 0) for date in dates]
        responded_counts = [bot_stats.get(
            "daily_messages_responded", {}).get(date, 0) for date in dates]

        # Create the chart
        fig, ax = plt.subplots(figsize=(8, 4))
        x = range(len(dates))
        ax.bar([i - 0.2 for i in x], sent_counts,
               0.4, label='Sent', color='#66b3ff')
        ax.bar([i + 0.2 for i in x], responded_counts,
               0.4, label='Responded', color='#99ff99')

        plt.xticks(x, [date[5:] for date in dates], rotation=45)
        plt.legend()
        plt.title('Message Activity - Last 7 Days')
        st.pyplot(fig)

    # Add a section for key engagement metrics
    st.subheader("🔍 Engagement Analysis")

    # Create metrics for different engagement categories
    engagement_cols = st.columns(4)

    with engagement_cols[0]:
        # Get responder statistics
        no_responders = sum(1 for conv in conversations.values()
                            if conv.get("metrics", {}).get("responder_category", "") == "No Responder")
        low_responders = sum(1 for conv in conversations.values()
                             if conv.get("metrics", {}).get("responder_category", "") == "Low Responder")
        medium_responders = sum(1 for conv in conversations.values()
                                if conv.get("metrics", {}).get("responder_category", "") == "Medium Responder")
        high_responders = sum(1 for conv in conversations.values()
                              if conv.get("metrics", {}).get("responder_category", "") == "High Responder")

        st.metric("No Response Users", no_responders)
        st.metric("Low Responders (1-10 msgs)", low_responders)

    with engagement_cols[1]:
        st.metric("Medium Responders (11-50 msgs)", medium_responders)
        st.metric("High Responders (50+ msgs)", high_responders)

    with engagement_cols[2]:
        # Calculate average engagement metrics
        total_users_with_messages = sum(1 for conv in conversations.values()
                                        if conv.get("metrics", {}).get("user_messages", 0) > 0)

        total_user_messages = sum(conv.get("metrics", {}).get("user_messages", 0)
                                  for conv in conversations.values())

        avg_messages_per_user = total_user_messages / \
            total_users_with_messages if total_users_with_messages > 0 else 0

        st.metric("Avg Messages per User", f"{avg_messages_per_user:.1f}")

        # Calculate average response time if available
        # This would need to be implemented with proper tracking
        st.metric("Avg Response Time", "N/A")  # Placeholder

    with engagement_cols[3]:
        # Calculate engagement over time metrics
        # This would need more implementation
        multi_convo_users = sum(1 for conv in conversations.values()
                                if conv.get("metrics", {}).get("conversation_count", 0) > 1)

        st.metric("Users with Multiple Conversations", multi_convo_users)

        # Calculate retention rate if we have the data
        retention_rate = (multi_convo_users / total_conversations *
                          100) if total_conversations > 0 else 0
        st.metric("User Retention Rate", f"{retention_rate:.1f}%")

    st.divider()

    # --- Responder Analysis Section (Moved to Top) ---
    st.subheader("Responder Analysis")
    if conversations:
        resp_cols = st.columns(len(responder_order))
        for i, category in enumerate(responder_order):
            with resp_cols[i]:
                # Use the label with range for the metric header
                label_with_range = RESPONDER_LABELS_WITH_RANGE.get(
                    category, category)
                st.metric(label_with_range,
                          responder_counts.get(category, 0))

        st.markdown("---")  # Visual separator

        for category in responder_order:
            count = responder_counts.get(category, 0)
            users = responder_lists.get(category, [])
            # Only show expander if there are users in the category
            if count > 0:
                # Use the label with range for the expander title
                label_with_range = RESPONDER_LABELS_WITH_RANGE.get(
                    category, category)
                with st.expander(f"{label_with_range} ({count}) - Click to see list", expanded=False):
                    if users:
                        # Display as a scrollable list if long, filtering out None before sorting
                        filtered_users = [
                            u for u in users if u is not None]
                        user_list_str = "\n".join(
                            [f"- {user}" for user in sorted(filtered_users)])
                        # Ensure height is at least 68px
                        # Use length of filtered list
                        calculated_height = 35 * len(filtered_users)
                        display_height = max(
                            68, min(200, calculated_height))
                        st.text_area("Users", user_list_str,
                                     height=display_height, disabled=True)
                    else:  # Should not happen if count > 0, but good practice
                        st.write("No conversations in this category.")
    else:
        st.info("No conversation data available for responder analysis.")

    st.divider()

    # --- Analytics Charts ---
    st.subheader("Analytics Charts")
    chart_cols = st.columns(2)

    with chart_cols[0]:
        # Question response pie chart
        if ai_questions > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            labels = ['Responded', 'No Response']
            responses = question_stats.get(
                "user_responses_to_questions", 0)
            # Ensure non-negative
            no_responses = max(0, ai_questions - responses)
            sizes = [responses, no_responses]

            if sum(sizes) > 0:  # Avoid pie chart error if sizes are zero
                ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=[
                       '#66b3ff', '#ff9999'])  # Add colors
                ax.axis('equal')
                plt.title('Question Response Rate')
                st.pyplot(fig)
            else:
                st.info("No question responses recorded for chart")
        else:
            st.info("No AI questions asked for chart")

    with chart_cols[1]:
        # Message types bar chart
        metrics_for_chart = {  # Use dict for clarity
            'Coaching Inquiries': global_metrics.get("coaching_inquiries", 0),
            'AI Detections': global_metrics.get("ai_detections", 0),
            'AI Questions': question_stats.get("ai_questions_asked", 0)
        }
        labels = list(metrics_for_chart.keys())
        values = list(metrics_for_chart.values())

        if any(v > 0 for v in values):  # Only show if data exists
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.bar(labels, values, color=[
                   '#ff9999', '#66b3ff', '#99ff99'])  # Add colors
            plt.title('Global Event Counts')
            plt.ylabel('Count')
            plt.xticks(rotation=45, ha="right")
            st.pyplot(fig)
        else:
            st.info("No event data available for chart")

    # Topic Tracking Section
    st.divider()
    st.subheader("Topic Tracking")
    topic_cols = st.columns(3)  # Adjust columns if needed

    with topic_cols[0]:
        st.metric("Vegan/Vegetarian Topic Conversations", global_metrics.get(
            "vegan_topic_conversations", 0))
    with topic_cols[1]:
        st.metric("Weight Loss Topic Conversations", global_metrics.get(
            "weight_loss_conversations", 0))
    with topic_cols[2]:
        st.metric("Muscle Gain Topic Conversations", global_metrics.get(
            "muscle_gain_conversations", 0))

    # Topic Initiation & Funnel
    st.divider()
    st.subheader("Topic Initiation & Funnel")
    col_topic, col_funnel = st.columns(2)

    with col_topic:
        st.metric("AI Initiated Fitness Topics", global_metrics.get(
            "ai_initiated_fitness_topics", 0))
        st.metric("User Initiated Fitness Topics", global_metrics.get(
            "user_initiated_fitness_topics", 0))
    with col_funnel:
        st.metric("Offers Mentioned (by AI)", global_metrics.get(
            "offers_mentioned", 0))
        st.metric("Links Sent (by AI)", global_metrics.get(
            "links_sent", 0))

    # Go directly to Follow-up section
    st.divider()
    st.subheader("Follow-up Messages Overview")

    # Add Meal Plan Analytics Section
    st.divider()
    st.subheader("🍽️ Meal Plan Analytics")
    meal_cols = st.columns(3)

    with meal_cols[0]:
        st.metric("Total Meal Plans Offered",
                  global_metrics.get("meal_plan_stats", {}).get("total_meal_plans_offered", 0))
        st.metric("Meal Plans Accepted",
                  global_metrics.get("meal_plan_stats", {}).get("meal_plans_accepted", 0))

    with meal_cols[1]:
        st.write("**Meal Plan Types:**")
        meal_types = global_metrics.get(
            "meal_plan_stats", {}).get("meal_plan_types", {})
        for plan_type, count in meal_types.items():
            st.write(f"- {plan_type.title()}: {count}")

    with meal_cols[2]:
        st.write("**Meal Plan Goals:**")
        meal_goals = global_metrics.get(
            "meal_plan_stats", {}).get("meal_plan_goals", {})
        for goal, count in meal_goals.items():
            st.write(f"- {goal.replace('_', ' ').title()}: {count}")

    # Add visualization for meal plan metrics
    if any(global_metrics.get("meal_plan_stats", {}).get("meal_plan_types", {}).values()):
        st.write("\n**Meal Plan Distribution**")
        fig, ax = plt.subplots(figsize=(8, 4))
        meal_types = global_metrics.get(
            "meal_plan_stats", {}).get("meal_plan_types", {})
        plt.pie(meal_types.values(),
                labels=meal_types.keys(), autopct='%1.1f%%')
        plt.title('Meal Plan Type Distribution')
        st.pyplot(fig)


# Conversations tab
with tabs[1]:
    st.header("Conversation Details")

    # Populate dropdown with available subscriber IDs/Usernames
    available_display_names = []
    id_map = {}  # Map display name back to subscriber ID

    if conversations:
        for sub_id, conv_data in conversations.items():
            # Get username from metrics
            metrics = conv_data.get("metrics", {})
            username = metrics.get("ig_username", sub_id)

            # Determine if conversation is active or closed based on last message timestamp
            last_message_time = metrics.get("last_message_timestamp")
            status = "Closed"  # Default to closed
            status_icon = "🔴"  # Red circle for closed

            if last_message_time:
                # Try multiple timestamp formats - similar to follow-up section
                last_message_dt = None

                # First try ISO format (with various replacements for Z and timezone)
                try:
                    # Handle various ISO format variations
                    clean_timestamp = last_message_time
                    if isinstance(clean_timestamp, str) and clean_timestamp.endswith('Z'):
                        clean_timestamp = clean_timestamp.replace(
                            'Z', '+00:00')
                    last_message_dt = datetime.fromisoformat(clean_timestamp)
                except (ValueError, TypeError):
                    # Try standard format with explicit parsing
                    try:
                        from dateutil import parser
                        last_message_dt = parser.parse(last_message_time)
                    except (ImportError, ValueError):
                        # If dateutil not available, try common formats
                        formats_to_try = [
                            '%Y-%m-%dT%H:%M:%S',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y/%m/%d %H:%M:%S',
                            '%d-%m-%Y %H:%M:%S',
                            '%m/%d/%Y %H:%M:%S'
                        ]
                        for fmt in formats_to_try:
                            try:
                                last_message_dt = datetime.strptime(
                                    last_message_time, fmt)
                                break
                            except ValueError:
                                continue

                # If we successfully parsed the timestamp
                if last_message_dt:
                    # Remove timezone info for consistent comparison
                    now = datetime.now().replace(tzinfo=None)
                    last_dt = last_message_dt.replace(tzinfo=None)

                    # Calculate time difference
                    time_diff = now - last_dt
                    # Debug information for the first few conversations
                    if sub_id in list(conversations.keys())[:3]:
                        print(
                            f"DEBUG - ID: {sub_id}, Last Message: {last_dt}, Diff: {time_diff}, Active: {time_diff <= timedelta(days=1)}")

                    # If last message is within 24 hours, mark as active
                    if time_diff <= timedelta(days=1):
                        status = "Active"
                        status_icon = "🟢"  # Green circle for active

            # Only use username if it exists and is not None
            if username:
                # Add status indicator to display name with color icon
                display_name = f"{status_icon} {username} ({status})"
                # In case of duplicate usernames, append a number
                temp_display_name = display_name
                counter = 1
                while temp_display_name in id_map:
                    temp_display_name = f"{display_name} ({counter})"
                    counter += 1
                display_name = temp_display_name
            else:
                # If no username, use ID as fallback with status and color icon
                display_name = f"{status_icon} {sub_id} ({status})"

            available_display_names.append(display_name)
            id_map[display_name] = sub_id

        # Sort usernames alphabetically, keeping IDs at the bottom
        available_display_names = sorted(
            available_display_names,
            # Sort active first, then alphabetically
            key=lambda x: (not "Active" in x, x.lower())
        )

    # Use a select box instead of text input
    selected_display_name = st.selectbox(
        "Select Instagram Username", options=[""] + available_display_names
    )

    # Find the actual subscriber ID based on the selected identifier
    subscriber_id_to_lookup = id_map.get(selected_display_name)  # Use the map

    if subscriber_id_to_lookup:
        conv_data = conversations.get(subscriber_id_to_lookup, {})
        conv_metrics = conv_data.get("metrics", {})
        conv_metadata = conv_data.get("metadata", {})  # Get metadata too

        if conv_metrics:
            st.subheader(
                f"Metrics for {selected_display_name} (ID: {subscriber_id_to_lookup})")

            metrics_cols = st.columns(3)

            # --- Column 1: Basic Counts ---
            with metrics_cols[0]:
                st.metric("Total Messages", conv_metrics.get(
                    "total_messages", 0))
                st.metric("User Messages", conv_metrics.get(
                    "user_messages", 0))
                st.metric("AI Messages", conv_metrics.get("ai_messages", 0))
                st.metric("AI Questions", conv_metrics.get("ai_questions", 0))
                st.metric("AI Statements", conv_metrics.get(
                    "ai_statements", 0))

            # --- Column 2: Engagement & Response ---
            with metrics_cols[1]:
                user_responses_to_questions = conv_metrics.get(
                    "user_responses_to_questions", 0)
                ai_questions = conv_metrics.get("ai_questions", 0)
                response_rate = user_responses_to_questions / \
                    ai_questions if ai_questions > 0 else 0

                st.metric("User Responses to AI Q's",
                          user_responses_to_questions)
                st.metric("AI Question Response Rate",
                          f"{response_rate * 100:.1f}%" if ai_questions > 0 else "N/A")
                st.metric("Responder Category", conv_metrics.get(
                    "responder_category", "N/A"))

            # --- Column 3: Events & Milestones ---
            with metrics_cols[2]:
                st.metric("Coaching Inquiries", conv_metrics.get(
                    "coaching_inquiries", 0))
                st.metric("AI Detections", conv_metrics.get(
                    "ai_detections", 0))
                st.metric("Conversation Count (24h Gap)",
                          conv_metrics.get("conversation_count", 0))

            # --- Auto Follow-up for Closed Conversations ---
            # Check if conversation is closed (no activity in 24 hours)
            last_message_time = conv_metrics.get("last_message_timestamp")
            is_closed = True

            if last_message_time:
                # Try multiple timestamp formats
                last_message_dt = None

                # First try ISO format (with various replacements for Z and timezone)
                try:
                    # Handle various ISO format variations
                    clean_timestamp = last_message_time
                    if isinstance(clean_timestamp, str) and clean_timestamp.endswith('Z'):
                        clean_timestamp = clean_timestamp.replace(
                            'Z', '+00:00')
                    last_message_dt = datetime.fromisoformat(clean_timestamp)
                except (ValueError, TypeError):
                    # Try standard format with explicit parsing
                    try:
                        from dateutil import parser
                        last_message_dt = parser.parse(last_message_time)
                    except (ImportError, ValueError):
                        # If dateutil not available, try common formats
                        formats_to_try = [
                            '%Y-%m-%dT%H:%M:%S',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y/%m/%d %H:%M:%S',
                            '%d-%m-%Y %H:%M:%S',
                            '%m/%d/%Y %H:%M:%S'
                        ]
                        for fmt in formats_to_try:
                            try:
                                last_message_dt = datetime.strptime(
                                    last_message_time, fmt)
                                break
                            except ValueError:
                                continue

                # If we successfully parsed the timestamp
                if last_message_dt:
                    # Remove timezone info for consistent comparison
                    now = datetime.now().replace(tzinfo=None)
                    last_dt = last_message_dt.replace(tzinfo=None)

                    # Calculate time difference
                    time_diff = now - last_dt

                    # If last message is within 24 hours, it's still active
                    if time_diff <= timedelta(days=1):
                        is_closed = False
                        # Debug info
                        print(
                            f"Follow-up Debug - Conversation Active: {subscriber_id_to_lookup}, Last Message: {last_dt}, Diff: {time_diff}")

            if is_closed:
                st.divider()
                st.subheader("🔄 Auto Follow-up Message")

                # Check if we have 24+ hours of inactivity
                if last_message_time:
                    try:
                        # Try multiple timestamp formats
                        last_message_dt = None

                        # First try ISO format (with various replacements for Z and timezone)
                        try:
                            # Handle various ISO format variations
                            clean_timestamp = last_message_time
                            if clean_timestamp.endswith('Z'):
                                clean_timestamp = clean_timestamp.replace(
                                    'Z', '+00:00')
                            last_message_dt = datetime.fromisoformat(
                                clean_timestamp)
                        except ValueError:
                            # Try standard format with explicit parsing
                            try:
                                from dateutil import parser
                                last_message_dt = parser.parse(
                                    last_message_time)
                            except (ImportError, ValueError):
                                # If dateutil not available, try common formats
                                formats_to_try = [
                                    '%Y-%m-%dT%H:%M:%S',
                                    '%Y-%m-%d %H:%M:%S',
                                    '%Y/%m/%d %H:%M:%S',
                                    '%d-%m-%Y %H:%M:%S',
                                    '%m/%d/%Y %H:%M:%S'
                                ]
                                for fmt in formats_to_try:
                                    try:
                                        last_message_dt = datetime.strptime(
                                            last_message_time, fmt)
                                        break
                                    except ValueError:
                                        continue

                        # If we successfully parsed the timestamp
                        if last_message_dt:
                            # Calculate days inactive
                            inactive_days = (datetime.now().replace(tzinfo=None) -
                                             last_message_dt.replace(tzinfo=None)).days

                            # Generate follow-up message
                            follow_up_msg = generate_follow_up_message(
                                conv_data)

                            # Create function for enhanced follow-up
                            def generate_enhanced_followup(conv_data):
                                """Generate a more personalized follow-up based on conversation context"""
                                metrics = conv_data.get("metrics", {})
                                history = metrics.get(
                                    "conversation_history", [])

                                # Get username for personalization
                                username = metrics.get("ig_username", "")

                                # Extract recent topics and user messages
                                recent_topics = []
                                user_messages = []

                                # Collect recent user messages for context
                                for msg in history:
                                    if msg.get("type") != "ai":
                                        msg_text = msg.get("text", "").strip()
                                        if msg_text:
                                            user_messages.append(msg_text)

                                            # Extract potential topics
                                            if any(kw in msg_text.lower() for kw in ["workout", "gym", "train", "exercis", "fit"]):
                                                recent_topics.append("fitness")
                                            if any(kw in msg_text.lower() for kw in ["eat", "food", "diet", "meal", "nutrition"]):
                                                recent_topics.append(
                                                    "nutrition")
                                            if any(kw in msg_text.lower() for kw in ["weight", "fat", "thin", "slim", "tone"]):
                                                recent_topics.append(
                                                    "weight management")
                                            if any(kw in msg_text.lower() for kw in ["muscle", "strong", "strength", "bulk"]):
                                                recent_topics.append(
                                                    "muscle building")
                                            if any(kw in msg_text.lower() for kw in ["injur", "pain", "hurt", "recover"]):
                                                recent_topics.append(
                                                    "recovery")

                                # Get unique topics
                                unique_topics = list(set(recent_topics))

                                # Get the last 3 user messages for context
                                recent_messages = user_messages[-3:] if user_messages else [
                                ]

                                # Determine the focus of the follow-up
                                greeting = f"Hey{' ' + username if username else ''}!"

                                # Base the follow-up on the identified topics
                                if "fitness" in unique_topics:
                                    if "nutrition" in unique_topics:
                                        main_message = "How's your training and nutrition been going? Still sticking to the plan? 💪"
                                    else:
                                        main_message = "How's your training been going lately? Making progress? 💪"
                                elif "nutrition" in unique_topics:
                                    main_message = "How's your meal plan going? Keeping it clean? 🥗"
                                elif "weight management" in unique_topics:
                                    main_message = "How's the progress coming? Still staying consistent with everything? 📊"
                                elif "muscle building" in unique_topics:
                                    main_message = "Still hitting it hard in the gym? Making those gains? 💪"
                                elif "recovery" in unique_topics:
                                    main_message = "How's the recovery going? Feeling better? 🔄"
                                else:
                                    # If no specific topics identified, use a more generic follow-up
                                    main_message = "How's things been going lately? Still crushing it? 💪"

                                # Add personalized touch based on the most recent message
                                if recent_messages:
                                    last_msg = recent_messages[-1].lower()

                                    # Look for specific patterns to reference
                                    if any(day in last_msg for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                                        callback = " Still on that grind you mentioned?"
                                    elif "goal" in last_msg or "aim" in last_msg or "want to" in last_msg:
                                        callback = " How's that goal coming along?"
                                    elif any(feeling in last_msg for feeling in ["tired", "exhausted", "fatigue", "sore"]):
                                        callback = " Feeling any better?"
                                    elif any(positive in last_msg for positive in ["good", "great", "awesome", "amazing", "progress"]):
                                        callback = " Still crushing it?"
                                    else:
                                        callback = ""

                                    # Add the callback if we have one
                                    if callback:
                                        main_message += callback

                                # Combine to create the follow-up
                                followup = f"{greeting} {main_message}"

                                return followup

                            # Generate enhanced follow-up
                            enhanced_followup = generate_enhanced_followup(
                                conv_data)

                            # Display follow-up options with tabs
                            st.markdown("""
                                <style>
                                    .follow-up-card-enhanced {
                                        background-color: #f0fff5;
                                        border-left: 5px solid #2e8b57;
                                        padding: 15px;
                                        border-radius: 5px;
                                        margin: 10px 0;
                                    }
                                    .follow-up-title-enhanced {
                                        color: #2e8b57;
                                        font-weight: bold;
                                        margin-bottom: 10px;
                                    }
                                    .follow-up-message {
                                        font-size: 16px;
                                        line-height: 1.5;
                                    }
                                    .follow-up-info {
                                        color: #666;
                                        font-size: 14px;
                                        margin-top: 10px;
                                    }
                                </style>
                            """, unsafe_allow_html=True)

                            formatted_date = last_message_dt.strftime(
                                '%Y-%m-%d %H:%M') if last_message_dt else "unknown date"

                            # Display enhanced follow-up message with countdown timer
                            st.markdown(f"""
                                <div class="follow-up-card-enhanced">
                                    <div class="follow-up-title-enhanced">Follow-up Message:</div>
                                    <div class="follow-up-message">{enhanced_followup}</div>
                                    <div class="follow-up-info">Personalized based on conversation history. Inactive for {inactive_days} days. Last message: {formatted_date}</div>
                                </div>
                            """, unsafe_allow_html=True)

                            # Add editable text area to allow customization
                            st.subheader("Customize Message:")
                            edited_followup = st.text_area(
                                "Edit message before sending", enhanced_followup, height=150)

                            # Copy button for the edited message
                            if st.button("📋 Copy to Clipboard"):
                                st.code(edited_followup, language="")
                                st.success(
                                    "Message copied to clipboard! You can now paste it into your conversation.")
                        else:
                            # Failed to parse timestamp with all methods
                            st.warning(
                                "Unable to determine exact inactivity period due to timestamp format.")

                            # Still show the follow-up message but without time details
                            enhanced_followup = generate_enhanced_followup(
                                conv_data)

                            st.markdown("""
                                <style>
                                    .follow-up-card-enhanced {
                                        background-color: #f0fff5;
                                        border-left: 5px solid #2e8b57;
                                        padding: 15px;
                                        border-radius: 5px;
                                        margin: 10px 0;
                                    }
                                    .follow-up-title-enhanced {
                                        color: #2e8b57;
                                        font-weight: bold;
                                        margin-bottom: 10px;
                                    }
                                    .follow-up-message {
                                        font-size: 16px;
                                        line-height: 1.5;
                                    }
                                </style>
                            """, unsafe_allow_html=True)

                            st.markdown(f"""
                                <div class="follow-up-card-enhanced">
                                    <div class="follow-up-title-enhanced">Follow-up Message:</div>
                                    <div class="follow-up-message">{enhanced_followup}</div>
                                </div>
                            """, unsafe_allow_html=True)

                            # Calculate and display follow-up timing
                            timing = get_smart_follow_up_timing(conv_data)
                            engagement = analyze_engagement_level(conv_metrics)

                            # Create a countdown timer section
                            st.markdown("""
                                <style>
                                    .countdown-container {
                                        margin-top: 10px;
                                        padding: 10px;
                                        background-color: #f8f9fa;
                                        border-radius: 5px;
                                        border-left: 5px solid #ffc107;
                                    }
                                    .countdown-title {
                                        font-weight: bold;
                                        color: #6c757d;
                                        margin-bottom: 5px;
                                    }
                                    .countdown-timer {
                                        font-size: 18px;
                                        font-weight: bold;
                                        color: #dc3545;
                                    }
                                    .countdown-details {
                                        margin-top: 5px;
                                        font-size: 14px;
                                        color: #6c757d;
                                    }
                                </style>
                            """, unsafe_allow_html=True)

                            # Check if we have valid timing information
                            if timing and "follow_up_start" in timing and "follow_up_end" in timing:
                                now = datetime.now(timezone.utc)
                                follow_up_start = timing["follow_up_start"]
                                follow_up_end = timing["follow_up_end"]

                                # Calculate time until follow-up
                                if now < follow_up_start:
                                    # Follow-up is in the future
                                    time_until = follow_up_start - now
                                    days = time_until.days
                                    hours, remainder = divmod(
                                        time_until.seconds, 3600)
                                    minutes, _ = divmod(remainder, 60)

                                    st.markdown(f"""
                                        <div class="countdown-container">
                                            <div class="countdown-title">⏱️ Follow-up Countdown:</div>
                                            <div class="countdown-timer">{days}d {hours}h {minutes}m until follow-up window opens</div>
                                            <div class="countdown-details">
                                                <span>• Engagement Level: {engagement["level"]}</span><br>
                                                <span>• Follow-up Window: {follow_up_start.strftime('%Y-%m-%d %H:%M')} - {follow_up_end.strftime('%Y-%m-%d %H:%M')}</span><br>
                                                <span>• Waiting Period: {timing["days_after_end"]} days after conversation end</span>
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                                elif now <= follow_up_end:
                                    # Currently in the follow-up window
                                    time_remaining = follow_up_end - now
                                    hours, remainder = divmod(
                                        time_remaining.seconds, 3600)
                                    minutes, _ = divmod(remainder, 60)

                                    st.markdown(f"""
                                        <div class="countdown-container" style="border-left: 5px solid #28a745;">
                                            <div class="countdown-title">🟢 Follow-up Ready:</div>
                                            <div class="countdown-timer" style="color: #28a745;">Ready to send now! ({hours}h {minutes}m remaining in window)</div>
                                            <div class="countdown-details">
                                                <span>• Engagement Level: {engagement["level"]}</span><br>
                                                <span>• Follow-up Window Closes: {follow_up_end.strftime('%Y-%m-%d %H:%M')}</span><br>
                                                <span>• Message eligible for automated sending</span>
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    # Follow-up window has passed
                                    st.markdown(f"""
                                        <div class="countdown-container" style="border-left: 5px solid #dc3545;">
                                            <div class="countdown-title">⚠️ Follow-up Window Passed:</div>
                                            <div class="countdown-timer" style="color: #dc3545;">Original window has closed</div>
                                            <div class="countdown-details">
                                                <span>• Original Window: {follow_up_start.strftime('%Y-%m-%d %H:%M')} - {follow_up_end.strftime('%Y-%m-%d %H:%M')}</span><br>
                                                <span>• Consider manual follow-up or reset timing</span>
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                            else:
                                # No valid timing information
                                st.markdown(f"""
                                    <div class="countdown-container" style="border-left: 5px solid #6c757d;">
                                        <div class="countdown-title">ℹ️ Follow-up Timing:</div>
                                        <div class="countdown-timer" style="color: #6c757d;">Timing information unavailable</div>
                                        <div class="countdown-details">
                                            <span>• Engagement Level: {engagement["level"]}</span><br>
                                            <span>• Manual follow-up may be needed</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)

                            # Add copy button for enhanced message
                            if st.button("📋 Copy Message"):
                                st.code(enhanced_followup, language="")
                                st.success(
                                    "Message copied! You can now paste it into your messaging app.")
                        else:
                            # Failed to parse timestamp with all methods
                            st.warning(
                                "Unable to determine exact inactivity period due to timestamp format.")

                            # Still show the follow-up message but without time details
                            enhanced_followup = generate_enhanced_followup(
                                conv_data)

                            st.markdown("""
                                <style>
                                    .follow-up-card-enhanced {
                                        background-color: #f0fff5;
                                        border-left: 5px solid #2e8b57;
                                        padding: 15px;
                                        border-radius: 5px;
                                        margin: 10px 0;
                                    }
                                    .follow-up-title-enhanced {
                                        color: #2e8b57;
                                        font-weight: bold;
                                        margin-bottom: 10px;
                                    }
                                    .follow-up-message {
                                        font-size: 16px;
                                        line-height: 1.5;
                                    }
                                </style>
                            """, unsafe_allow_html=True)

                            st.markdown(f"""
                                <div class="follow-up-card-enhanced">
                                    <div class="follow-up-title-enhanced">Follow-up Message:</div>
                                    <div class="follow-up-message">{enhanced_followup}</div>
                                </div>
                            """, unsafe_allow_html=True)

                            # Calculate and display follow-up timing
                            timing = get_smart_follow_up_timing(conv_data)
                            engagement = analyze_engagement_level(conv_metrics)

                            # Create a countdown timer section
                            st.markdown("""
                                <style>
                                    .countdown-container {
                                        margin-top: 10px;
                                        padding: 10px;
                                        background-color: #f8f9fa;
                                        border-radius: 5px;
                                        border-left: 5px solid #ffc107;
                                    }
                                    .countdown-title {
                                        font-weight: bold;
                                        color: #6c757d;
                                        margin-bottom: 5px;
                                    }
                                    .countdown-timer {
                                        font-size: 18px;
                                        font-weight: bold;
                                        color: #dc3545;
                                    }
                                    .countdown-details {
                                        margin-top: 5px;
                                        font-size: 14px;
                                        color: #6c757d;
                                    }
                                </style>
                            """, unsafe_allow_html=True)

                            # Check if we have valid timing information
                            if timing and "follow_up_start" in timing and "follow_up_end" in timing:
                                now = datetime.now(timezone.utc)
                                follow_up_start = timing["follow_up_start"]
                                follow_up_end = timing["follow_up_end"]

                                # Calculate time until follow-up
                                if now < follow_up_start:
                                    # Follow-up is in the future
                                    time_until = follow_up_start - now
                                    days = time_until.days
                                    hours, remainder = divmod(
                                        time_until.seconds, 3600)
                                    minutes, _ = divmod(remainder, 60)

                                    st.markdown(f"""
                                        <div class="countdown-container">
                                            <div class="countdown-title">⏱️ Follow-up Countdown:</div>
                                            <div class="countdown-timer">{days}d {hours}h {minutes}m until follow-up window opens</div>
                                            <div class="countdown-details">
                                                <span>• Engagement Level: {engagement["level"]}</span><br>
                                                <span>• Follow-up Window: {follow_up_start.strftime('%Y-%m-%d %H:%M')} - {follow_up_end.strftime('%Y-%m-%d %H:%M')}</span><br>
                                                <span>• Waiting Period: {timing["days_after_end"]} days after conversation end</span>
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                                elif now <= follow_up_end:
                                    # Currently in the follow-up window
                                    time_remaining = follow_up_end - now
                                    hours, remainder = divmod(
                                        time_remaining.seconds, 3600)
                                    minutes, _ = divmod(remainder, 60)

                                    st.markdown(f"""
                                        <div class="countdown-container" style="border-left: 5px solid #28a745;">
                                            <div class="countdown-title">🟢 Follow-up Ready:</div>
                                            <div class="countdown-timer" style="color: #28a745;">Ready to send now! ({hours}h {minutes}m remaining in window)</div>
                                            <div class="countdown-details">
                                                <span>• Engagement Level: {engagement["level"]}</span><br>
                                                <span>• Follow-up Window Closes: {follow_up_end.strftime('%Y-%m-%d %H:%M')}</span><br>
                                                <span>• Message eligible for automated sending</span>
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    # Follow-up window has passed
                                    st.markdown(f"""
                                        <div class="countdown-container" style="border-left: 5px solid #dc3545;">
                                            <div class="countdown-title">⚠️ Follow-up Window Passed:</div>
                                            <div class="countdown-timer" style="color: #dc3545;">Original window has closed</div>
                                            <div class="countdown-details">
                                                <span>• Original Window: {follow_up_start.strftime('%Y-%m-%d %H:%M')} - {follow_up_end.strftime('%Y-%m-%d %H:%M')}</span><br>
                                                <span>• Consider manual follow-up or reset timing</span>
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                            else:
                                # No valid timing information
                                st.markdown(f"""
                                    <div class="countdown-container" style="border-left: 5px solid #6c757d;">
                                        <div class="countdown-title">ℹ️ Follow-up Timing:</div>
                                        <div class="countdown-timer" style="color: #6c757d;">Timing information unavailable</div>
                                        <div class="countdown-details">
                                            <span>• Engagement Level: {engagement["level"]}</span><br>
                                            <span>• Manual follow-up may be needed</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)

                            # Add copy button
                            if st.button("📋 Copy Message"):
                                st.code(enhanced_followup, language="")
                                st.success(
                                    "Message copied! You can now paste it into your messaging app.")
                    except Exception as e:
                        # Fall back to still showing a follow-up message even if there's an error
                        st.warning(f"Could not process timestamp: {str(e)}")

                        # Still generate and show follow-up message
                        enhanced_followup = generate_enhanced_followup(
                            conv_data)
                        st.markdown(
                            f"**Suggested follow-up message:**\n\n{enhanced_followup}")

                        # Simple copy button
                        if st.button("📋 Copy Message"):
                            st.code(enhanced_followup, language="")
                            st.success("Message copied!")
                else:
                    # Even without timestamp, still show a follow-up option
                    st.info(
                        "No message timestamp available, but you can still send a follow-up.")
                    enhanced_followup = generate_enhanced_followup(conv_data)
                    st.text_area("Suggested follow-up:",
                                 enhanced_followup, height=100)
                    if st.button("📋 Copy Follow-up Message"):
                        st.code(enhanced_followup, language="")
                        st.success("Message copied!")

            st.divider()

            # --- Conversation History Details ---
            st.subheader("Conversation History")
            history_cols = st.columns(2)
            with history_cols[0]:
                st.write("**Timing:**")
                first_ts = conv_metrics.get('first_message_timestamp')
                last_ts = conv_metrics.get('last_message_timestamp')
                try:
                    first_dt = datetime.fromisoformat(first_ts).strftime(
                        '%Y-%m-%d %H:%M') if first_ts else 'N/A'
                except ValueError:
                    first_dt = first_ts
                try:
                    last_dt = datetime.fromisoformat(last_ts).strftime(
                        '%Y-%m-%d %H:%M') if last_ts else 'N/A'
                except ValueError:
                    last_dt = last_ts

                st.write(f"- First Message: {first_dt}")
                st.write(f"- Last Message: {last_dt}")
                st.write(
                    f"- Duration: {conv_metrics.get('conversation_duration_str', 'N/A')}")

            with history_cols[1]:
                st.write("**Conversation Stats:**")
                conv_count = conv_metrics.get("conversation_count", 0)
                total_msgs = conv_metrics.get("total_messages", 0)
                avg_msgs = round(total_msgs / max(conv_count, 1), 1)

                st.write(f"- Total Distinct Conversations: {conv_count}")
                st.write(f"- Total Messages Exchanged: {total_msgs}")
                st.write(f"- Average Messages per Conversation: {avg_msgs}")

            st.divider()

            # --- Message Milestones ---
            st.write("**Message Milestones Achieved:**")
            achieved_milestones = conv_metrics.get(
                "achieved_message_milestones", [])
            if achieved_milestones:
                try:
                    sorted_milestones = sorted(
                        [int(m) for m in list(achieved_milestones)])
                    st.write(", ".join(map(str, sorted_milestones)))
                except (TypeError, ValueError):
                    st.write("(Error parsing)")
            else:
                st.write("None")

            st.divider()

            # --- Instagram Profile Analysis --- (NEW SECTION)
            st.subheader("Instagram Profile Analysis")

            # Extract profile analysis data
            post_analysis = conv_metrics.get("post_analysis", "")
            profile_conversation_topics = conv_metrics.get(
                "profile_conversation_topics", [])
            conversation_opener = conv_metrics.get("conversation_opener", "")

            # Check if we have any profile analysis data
            has_profile_data = bool(
                post_analysis or profile_conversation_topics or conversation_opener)

            if has_profile_data:
                analysis_cols = st.columns(2)

                with analysis_cols[0]:
                    # Show post analysis if available
                    if post_analysis:
                        with st.expander("Post Analysis", expanded=False):
                            st.write(post_analysis)

                    # Show initial message sent if available
                    if conversation_opener:
                        st.write("**Initial Message Sent:**")
                        st.markdown(f"""
                            <div style="background-color: #e6f3ff; padding: 10px; border-radius: 5px; border-left: 4px solid #2E86C1;">
                                {conversation_opener}
                            </div>
                        """, unsafe_allow_html=True)

                with analysis_cols[1]:
                    # Show conversation topics if available
                    if profile_conversation_topics:
                        st.write("**Conversation Topics Detected:**")
                        for i, topic in enumerate(profile_conversation_topics):
                            st.markdown(f"""
                                <div style="display: inline-block; background-color: #eaf7ff; 
                                     margin: 5px; padding: 5px 10px; border-radius: 15px; 
                                     border: 1px solid #add8e6;">
                                    {i+1}. {topic}
                                </div>
                            """, unsafe_allow_html=True)
            else:
                st.info(
                    "No Instagram profile analysis available for this conversation.")

            st.divider()

            # --- Message History ---
            st.subheader("Message History")

            # Read from conversation_history list in metrics
            conversation_history_list = conv_metrics.get(
                "conversation_history", [])

            if conversation_history_list:
                # Define CSS styles for the message container and messages
                st.markdown("""
                    <style>
                    .message-container {
                        max-height: 400px;
                        overflow-y: auto;
                        border: 1px solid #ddd;
                        padding: 10px;
                        border-radius: 5px;
                        margin-bottom: 10px;
                    }
                    .message {
                        padding: 5px 10px;
                        margin: 5px 0;
                        border-radius: 5px;
                        display: flex;
                        justify-content: space-between;
                        align-items: baseline;
                    }
                    .ai-message {
                        background-color: #E8F6F3;
                        color: #2E86C1;
                    }
                    .user-message {
                        background-color: #F8F9F9;
                        color: #424949;
                    }
                    .timestamp {
                        font-size: 0.75em;
                        color: #95A5A6;
                        margin-right: 10px;
                        white-space: nowrap;
                        min-width: 130px;
                        text-align: left;
                    }
                    .message-text {
                        flex-grow: 1;
                        word-wrap: break-word;
                        overflow-wrap: break-word;
                        text-align: left;
                        margin-left: 10px;
                    }
                    </style>
                    """, unsafe_allow_html=True)

                # Create the scrollable container
                st.markdown('<div class="message-container">',
                            unsafe_allow_html=True)

                # Iterate through the message history
                for message_data in conversation_history_list:
                    msg_timestamp_str = "N/A"
                    try:
                        # Parse and format timestamp, assuming UTC
                        msg_timestamp_dt = datetime.fromisoformat(
                            message_data.get("timestamp", "")).astimezone(timezone.utc)
                        msg_timestamp_str = msg_timestamp_dt.strftime(
                            '%Y-%m-%d %H:%M:%S Z')
                    except (ValueError, TypeError):
                        msg_timestamp_str = message_data.get(
                            "timestamp", "Invalid Date")

                    msg_type = message_data.get("type", "unknown")
                    msg_text = message_data.get("text", "")

                    if msg_text:  # Display only if text exists
                        css_class = "ai-message" if msg_type == "ai" else "user-message"
                        # Display formatted message
                        st.markdown(
                            f'<div class="message {css_class}">'
                            f'<span class="timestamp">{msg_timestamp_str}</span>'
                            f'<span class="message-text">{msg_text}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                # Close the container
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("No message history available.")
            # --- End Message History Section ---

            st.divider()

            # --- Topic & Funnel Correlation ---
            st.subheader("Conversation Topics & Funnel")
            topic_funnel_cols = st.columns(3)
            with topic_funnel_cols[0]:
                st.write("**Topics Mentioned:**")
                # Use icons
                st.write(
                    f"- Vegan/Vegetarian: {'✅ Yes' if conv_metrics.get('vegan_topic_mentioned', False) else '❌ No'}")
                st.write(
                    f"- Weight Loss: {'✅ Yes' if conv_metrics.get('weight_loss_mentioned', False) else '❌ No'}")
                st.write(
                    f"- Muscle Gain: {'✅ Yes' if conv_metrics.get('muscle_gain_mentioned', False) else '❌ No'}")
                st.write(
                    f"- Fitness (User Init.): {'✅ Yes' if conv_metrics.get('fitness_topic_user_initiated', False) else '❌ No'}")
                st.write(
                    f"- Fitness (AI Init.): {'✅ Yes' if conv_metrics.get('fitness_topic_ai_initiated', False) else '❌ No'}")

            with topic_funnel_cols[1]:
                st.write("**Funnel Actions (AI):**")
                st.write(
                    f"- Offer Mentioned: {'✅ Yes' if conv_metrics.get('offer_mentioned_in_conv', False) else '❌ No'}")
                st.write(
                    f"- Link Sent: {'✅ Yes' if conv_metrics.get('link_sent_in_conv', False) else '❌ No'}")

            with topic_funnel_cols[2]:
                st.write("**Timestamps & Duration:**")
                # Format timestamps nicely if they exist
                first_ts = conv_metrics.get('first_message_timestamp')
                last_ts = conv_metrics.get('last_message_timestamp')
                try:
                    first_dt = datetime.fromisoformat(first_ts).strftime(
                        '%Y-%m-%d %H:%M') if first_ts else 'N/A'
                except ValueError:
                    first_dt = first_ts  # Keep original if not ISO format
                try:
                    last_dt = datetime.fromisoformat(last_ts).strftime(
                        '%Y-%m-%d %H:%M') if last_ts else 'N/A'
                except ValueError:
                    last_dt = last_ts  # Keep original if not ISO format

                st.write(f"- First Message: {first_dt}")
                st.write(f"- Last Message: {last_dt}")
                st.write(
                    f"- Duration: {conv_metrics.get('conversation_duration_str', 'N/A')}")

            # Optionally display raw metrics & metadata in expanders
            with st.expander("Show Raw Conversation Metrics"):
                st.json(conv_metrics)
            with st.expander("Show Conversation Metadata"):
                st.json(conv_metadata)

            # --- Follow-up Status ---
            st.subheader("Follow-up Status")

            status_cols = st.columns(2)

            with status_cols[0]:
                st.write("**Current Status:**")

                # Check if we should follow up
                should_follow = should_follow_up(conv_data)
                timing = get_smart_follow_up_timing(conv_data)

                # Add manual override section
                st.write("\n**Follow-up Controls:**")
                override_container = st.container()

                with override_container:
                    # Manual override toggle
                    has_override = conv_metrics.get("manual_override", False)
                    enable_override = st.toggle(
                        "Enable Manual Override", value=has_override)

                    if enable_override:
                        # Date picker for custom follow-up date
                        st.write("Set Custom Follow-up Date:")
                        current_date = datetime.now()
                        # At least 1 hour in future
                        min_date = current_date + timedelta(hours=1)
                        max_date = current_date + \
                            timedelta(days=14)  # Max 2 weeks ahead

                        custom_date = st.date_input(
                            "Date",
                            value=current_date.date(),
                            min_value=min_date.date(),
                            max_value=max_date.date()
                        )

                        # Time picker
                        current_time = datetime.now()
                        custom_time = st.time_input(
                            "Time",
                            value=current_time.time()
                        )

                        # Combine date and time
                        custom_datetime = datetime.combine(
                            custom_date, custom_time)

                        # Save button
                        if st.button("Save Custom Timing"):
                            try:
                                # Load current analytics data
                                with open("C:\\Users\\Shannon\\analytics_data.json", 'r') as f:
                                    analytics_data = json.load(f)

                                # Update the override settings
                                if subscriber_id_to_lookup in analytics_data["conversations"]:
                                    metrics = analytics_data["conversations"][subscriber_id_to_lookup]["metrics"]
                                    metrics["manual_override"] = True
                                    metrics["manual_follow_up_date"] = custom_datetime.isoformat(
                                    )

                                    # Save back to file
                                    with open("C:\\Users\\Shannon\\analytics_data.json", 'w') as f:
                                        json.dump(analytics_data, f, indent=2)

                                    st.success(
                                        "✅ Custom follow-up time saved!")

                            except Exception as e:
                                st.error(f"Error saving override: {e}")

                        # Reset button
                        if st.button("Reset to Automatic Timing"):
                            try:
                                with open("C:\\Users\\Shannon\\analytics_data.json", 'r') as f:
                                    analytics_data = json.load(f)

                                if subscriber_id_to_lookup in analytics_data["conversations"]:
                                    metrics = analytics_data["conversations"][subscriber_id_to_lookup]["metrics"]
                                    metrics["manual_override"] = False
                                    if "manual_follow_up_date" in metrics:
                                        del metrics["manual_follow_up_date"]

                                    with open("C:\\Users\\Shannon\\analytics_data.json", 'w') as f:
                                        json.dump(analytics_data, f, indent=2)

                                    st.success("✅ Reset to automatic timing!")

                            except Exception as e:
                                st.error(f"Error resetting override: {e}")

                # Show timing status
                st.write("\n**Follow-up Timing:**")
                if enable_override:
                    manual_date = conv_metrics.get("manual_follow_up_date")
                    if manual_date:
                        manual_dt = datetime.fromisoformat(manual_date)
                        st.info(
                            f"🕒 Manually scheduled for: {manual_dt.strftime('%Y-%m-%d %H:%M')}")
                else:
                    if should_follow:
                        st.success("✅ Ready for follow-up!")
                        st.write("**Automatic Schedule:**")
                        st.write(
                            f"- Start: {timing.get('follow_up_start', 'N/A')}")
                        st.write(
                            f"- End: {timing.get('follow_up_end', 'N/A')}")
                    else:
                        if conv_metrics.get("follow_ups_sent", 0) >= 3:
                            st.warning("🚫 Maximum follow-ups sent")
                        elif conv_metrics.get("last_follow_up_date"):
                            last_dt = datetime.fromisoformat(
                                conv_metrics["last_follow_up_date"].replace('Z', '+00:00'))
                            next_possible = last_dt + timedelta(days=3)
                            st.info(
                                f"⏳ Next automatic follow-up after: {next_possible}")
                        else:
                            st.info("⏳ Waiting for initial conversation to end")

            with status_cols[1]:
                st.write("**Follow-up History:**")
                st.write(
                    f"- Follow-ups sent: {conv_metrics.get('follow_ups_sent', 0)}")
                if conv_metrics.get("last_follow_up_date"):
                    st.write(
                        f"- Last follow-up: {conv_metrics['last_follow_up_date']}")
                st.write(
                    f"- Responses to follow-ups: {conv_metrics.get('follow_up_responses', 0)}")

            # Preview the next follow-up message
            st.write("\n**Next Follow-up Message Preview:**")
            if should_follow:
                # Generate the message (reuse the function from followersbot.py)
                next_message = generate_follow_up_message(conv_data)

                # Create a message preview box with styling
                st.markdown("""
                    <style>
                        .message-preview {
                            background-color: #f0f2f6;
                            border-radius: 10px;
                            padding: 15px;
                            margin: 10px 0;
                            border-left: 4px solid #2E86C1;
                        }
                    </style>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                    <div class="message-preview">
                        {next_message}
                    </div>
                """, unsafe_allow_html=True)

                # Show what triggered this message
                engagement = analyze_engagement_level(conv_metrics)
                st.write("\n**Message Context:**")
                st.write(f"- Engagement Level: {engagement['level']}")
                st.write("- Factors Considered:")
                for factor in engagement['factors']:
                    st.write(f"  • {factor}")
            else:
                st.info("No follow-up message scheduled yet")

            st.divider()

            st.subheader("Follow-up Message History")
            if conv_data.get("follow_up_history"):
                for idx, follow_up in enumerate(conv_data["follow_up_history"], 1):
                    with st.expander(f"Follow-up #{idx} - {follow_up['date'][:16]}", expanded=False):
                        st.write("**Message Sent:**")
                        st.write(follow_up["message"])
                        st.write("\n**Context:**")
                        st.write(
                            f"- Engagement Level: {follow_up['engagement_level']}")
                        if follow_up.get("post_analysis"):
                            st.write("**Post Analysis:**")
                            st.write(follow_up["post_analysis"])
                        st.write(f"- Sent at: {follow_up['date']}")

                        # Check if there was a response
                        response_date = conv_metrics.get(
                            f"follow_up_{idx}_response_date")
                        if response_date:
                            st.write("✅ **Got Response**")
                        else:
                            st.write("⏳ **Awaiting Response**")

            # Add Meal Plan Information
            st.divider()
            st.subheader("🍽️ Meal Plan Information")
            meal_plan_cols = st.columns(2)

            with meal_plan_cols[0]:
                st.write("**Meal Plan Status:**")
                if conv_metrics.get("meal_plan_offered"):
                    st.write("✅ Meal plan has been offered")
                    if conv_metrics.get("meal_plan_accepted"):
                        st.write("✅ Meal plan was accepted")
                    else:
                        st.write("❌ Meal plan not yet accepted")
                else:
                    st.write("❌ No meal plan offered yet")

            with meal_plan_cols[1]:
                if conv_metrics.get("meal_plan_offered"):
                    st.write("**Meal Plan Details:**")
                    st.write(
                        f"- Type: {conv_metrics.get('meal_plan_type', 'Not specified').title()}")
                    st.write(
                        f"- Goal: {conv_metrics.get('meal_plan_goal', 'Not specified').replace('_', ' ').title()}")

                    if conv_metrics.get("meal_plan_customizations"):
                        st.write("**Customizations:**")
                        for custom in conv_metrics.get("meal_plan_customizations", []):
                            st.write(f"- {custom}")

                    if conv_metrics.get("meal_plan_feedback"):
                        st.write("**Feedback:**")
                        st.write(conv_metrics.get("meal_plan_feedback"))
        else:
            st.warning(
                f"No metric data found for subscriber {selected_display_name} ({subscriber_id_to_lookup}) in the loaded file.")
    elif selected_display_name == "":
        st.info(
            "Select a User/Subscriber ID from the dropdown to see conversation details.")
    else:
        # This case should be less likely with the id_map, but handle defensively
        st.error(
            f"Could not find subscriber ID for selected user: {selected_display_name}")


# Daily Report tab
with tabs[2]:
    st.header("Daily Conversation Report")

    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")

    # Create columns for statistics
    stat_cols = st.columns(3)

    # Track statistics
    total_analyzed = 0
    ended_conversations = 0
    potential_followups = 0

    # Create containers for different conversation states
    active_convs = []
    ended_convs = []
    followup_convs = []

    if conversations:
        for subscriber_id, conv_data in conversations.items():
            metrics = conv_data.get("metrics", {})
            username = metrics.get("ig_username", subscriber_id)

            # Only analyze conversations with activity in the last 24 hours
            last_message_time = metrics.get("last_message_timestamp")
            if not last_message_time:
                continue

            try:
                last_message_dt = datetime.fromisoformat(last_message_time)
                if (datetime.now() - last_message_dt) > timedelta(days=1):
                    continue
            except (ValueError, TypeError):
                continue

            total_analyzed += 1

            # Get conversation history
            history = metrics.get("conversation_history", [])
            if not history:
                continue

            # Analyze message patterns
            user_messages = [msg for msg in history if msg.get("type") != "ai"]
            ai_messages = [msg for msg in history if msg.get("type") == "ai"]

            # Count questions asked
            questions_asked = sum(
                1 for msg in ai_messages if "?" in msg.get("text", ""))

            # Analyze user engagement
            avg_response_length = sum(len(msg.get("text", "").split(
            )) for msg in user_messages) / len(user_messages) if user_messages else 0

            # Check conversation end pattern
            last_messages = history[-3:]  # Look at last 3 messages
            short_responses = sum(1 for msg in last_messages if msg.get(
                "type") != "ai" and len(msg.get("text", "").split()) < 3)

            # Get topics discussed
            topics = []
            if metrics.get("fitness_topic_user_initiated"):
                topics.append("fitness (user initiated)")
            if metrics.get("fitness_topic_ai_initiated"):
                topics.append("fitness (AI initiated)")
            if metrics.get("vegan_topic_mentioned"):
                topics.append("nutrition")
            if metrics.get("weight_loss_mentioned"):
                topics.append("weight loss")
            if metrics.get("muscle_gain_mentioned"):
                topics.append("muscle gain")

            # Create conversation summary
            conv_summary = {
                "username": username,
                "messages": f"{len(history)} (User: {len(user_messages)}, AI: {len(ai_messages)})",
                "questions": questions_asked,
                "avg_response": f"{avg_response_length:.1f}",
                "topics": topics,
                "last_message": history[-1].get("text", "") if history else "",
                "last_sender": "You" if history and history[-1].get("type") == "ai" else "They"
            }

            # Determine conversation status
            needs_followup = should_follow_up(conv_data)
            if needs_followup:
                potential_followups += 1
                timing = get_smart_follow_up_timing(conv_data)
                conv_summary["follow_up_time"] = timing.get(
                    'follow_up_start', 'Unknown')
                followup_convs.append(conv_summary)

            if short_responses >= 2 or (history and ("bye" in history[-1].get("text", "").lower() or "thank" in history[-1].get("text", "").lower())):
                ended_conversations += 1
                ended_convs.append(conv_summary)
            else:
                active_convs.append(conv_summary)

        # Display statistics
        with stat_cols[0]:
            st.metric("Total Conversations", total_analyzed)
        with stat_cols[1]:
            st.metric("Ended Conversations", ended_conversations)
        with stat_cols[2]:
            st.metric("Need Follow-up", potential_followups)

        # Display conversation sections
        if active_convs:
            st.subheader("🟢 Active Conversations")
            for conv in active_convs:
                with st.expander(f"{conv['username']} - {conv['messages']} messages"):
                    st.write(f"**Questions Asked:** {conv['questions']}")
                    st.write(
                        f"**Avg Response Length:** {conv['avg_response']} words")
                    if conv['topics']:
                        st.write(f"**Topics:** {', '.join(conv['topics'])}")
                    st.write(
                        f"**Last Message ({conv['last_sender']}):** {conv['last_message']}")

        if followup_convs:
            st.subheader("⏰ Ready for Follow-up")
            for conv in followup_convs:
                with st.expander(f"{conv['username']} - Follow-up at {conv['follow_up_time']}"):
                    st.write(f"**Messages:** {conv['messages']}")
                    st.write(f"**Questions Asked:** {conv['questions']}")
                    if conv['topics']:
                        st.write(f"**Topics:** {', '.join(conv['topics'])}")
                    st.write(
                        f"**Last Message ({conv['last_sender']}):** {conv['last_message']}")

        if ended_convs:
            st.subheader("✅ Recently Ended Conversations")
            for conv in ended_convs:
                with st.expander(f"{conv['username']} - {conv['messages']} messages"):
                    st.write(f"**Questions Asked:** {conv['questions']}")
                    st.write(
                        f"**Avg Response Length:** {conv['avg_response']} words")
                    if conv['topics']:
                        st.write(f"**Topics:** {', '.join(conv['topics'])}")
                    st.write(
                        f"**Last Message ({conv['last_sender']}):** {conv['last_message']}")

        # Add Prompt Analysis section
        st.subheader("🤖 Prompt Analysis & Suggestions")

        # Analyze AI message patterns
        total_ai_messages = sum(len([msg for msg in conv_data.get("metrics", {}).get("conversation_history", [])
                                     if msg.get("type") == "ai"])
                                for conv_data in conversations.values())

        # Track patterns that might need prompt improvement
        prompt_issues = []
        prompt_successes = []

        for conv_data in conversations.values():
            metrics = conv_data.get("metrics", {})
            history = metrics.get("conversation_history", [])

            if not history:
                continue

            # Get username for context
            username = metrics.get("ig_username", "Unknown")

            # Analyze conversation flow
            for i, msg in enumerate(history):
                if msg.get("type") == "ai":
                    ai_text = msg.get("text", "").lower()

                    # Check for consecutive questions
                    if i > 0 and history[i-1].get("type") == "ai" and "?" in ai_text and "?" in history[i-1].get("text", ""):
                        prompt_issues.append({
                            "type": "consecutive_questions",
                            "context": f"With {username}: Asked multiple questions in a row",
                            "suggestion": "Update prompt to limit to one question per message"
                        })

                    # Check for generic responses
                    generic_phrases = ["how's things",
                                       "that's good", "nice one", "awesome"]
                    if any(phrase in ai_text for phrase in generic_phrases) and len(ai_text.split()) < 5:
                        prompt_issues.append({
                            "type": "generic_response",
                            "context": f"With {username}: Used generic response '{ai_text}'",
                            "suggestion": "Add more context-specific response templates to prompt"
                        })

                    # Check for Shannon's style consistency
                    non_shannon_phrases = [
                        "thank you", "please", "would you like", "I apologize", "sorry about that"]
                    if any(phrase in ai_text for phrase in non_shannon_phrases):
                        prompt_issues.append({
                            "type": "style_mismatch",
                            "context": f"With {username}: Used formal/non-Shannon phrase '{[p for p in non_shannon_phrases if p in ai_text][0]}'",
                            "suggestion": "Reinforce casual, direct communication style in prompt"
                        })

                    # Check for emoji overuse
                    emoji_count = len(re.findall(
                        r'[\U0001F300-\U0001F9FF]', ai_text))
                    if emoji_count > 2:
                        prompt_issues.append({
                            "type": "emoji_overuse",
                            "context": f"With {username}: Used {emoji_count} emojis in one message",
                            "suggestion": "Limit to 1-2 emojis per message maximum"
                        })

                    # Check for response timing context
                    if i > 0 and history[i-1].get("type") != "ai":
                        try:
                            current_time = datetime.fromisoformat(
                                msg.get("timestamp", "")).time()
                            if "night" in ai_text.lower() and current_time.hour < 17:
                                prompt_issues.append({
                                    "type": "time_context_mismatch",
                                    "context": f"With {username}: Mentioned night at {current_time.hour}:00",
                                    "suggestion": "Better use of time context in responses"
                                })
                        except (ValueError, TypeError):
                            pass

                    # Check for conversation flow breaks
                    if i > 0 and history[i-1].get("type") != "ai":
                        prev_msg = history[i-1].get("text", "").lower()
                        # If user shares personal info but response doesn't acknowledge
                        personal_indicators = [
                            "i feel", "i think", "i'm", "im ", "i am", "my"]
                        if any(indicator in prev_msg for indicator in personal_indicators) and not any(indicator in ai_text for indicator in ["you", "your", "that's"]):
                            prompt_issues.append({
                                "type": "missed_personal_context",
                                "context": f"With {username}: Didn't acknowledge personal share: '{prev_msg[:30]}...'",
                                "suggestion": "Enhance prompt to acknowledge personal shares before moving conversation forward"
                            })

                    # Check for abrupt topic changes
                    if i > 1:
                        prev_user_msg = history[i-1].get("text", "").lower(
                        ) if history[i-1].get("type") != "ai" else ""
                        prev_topic_words = set(prev_user_msg.split())
                        current_topic_words = set(ai_text.split())
                        common_words = prev_topic_words.intersection(
                            current_topic_words)
                        if prev_user_msg and len(common_words) == 0 and "?" in ai_text:
                            prompt_issues.append({
                                "type": "abrupt_topic_change",
                                "context": f"With {username}: Abrupt topic change from '{prev_user_msg[:30]}...' to '{ai_text[:30]}...'",
                                "suggestion": "Add transition phrases or acknowledgments before changing topics"
                            })

                    # Identify successful patterns
                    if i > 0 and history[i-1].get("type") != "ai":
                        user_msg = history[i-1].get("text", "").lower()

                        # Good engagement patterns
                        if any(phrase in ai_text for phrase in ["that's solid", "hell yeah", "lets get it"]):
                            prompt_successes.append({
                                "type": "authentic_engagement",
                                "context": f"With {username}: Used Shannon's authentic phrases",
                                "example": ai_text
                            })

                        # Good follow-up questions
                        if "?" in ai_text and any(word in ai_text for word in user_msg.split()):
                            prompt_successes.append({
                                "type": "contextual_question",
                                "context": f"With {username}: Asked relevant follow-up based on their response",
                                "example": ai_text
                            })

                        # Good emotional mirroring
                        user_excitement = any(phrase in user_msg for phrase in [
                                              "!", "excited", "happy", "love"])
                        ai_excitement = any(phrase in ai_text for phrase in [
                                            "!", "lets go", "awesome"])
                        if user_excitement and ai_excitement:
                            prompt_successes.append({
                                "type": "emotion_matching",
                                "context": f"With {username}: Matched user's excitement level",
                                "example": ai_text
                            })

                    # Track conversation endings
                    if i == len(history) - 1:  # If this is the last message
                        if len(ai_text) > 20 and "?" in ai_text and history[i-1].get("type") != "ai":
                            prompt_issues.append({
                                "type": "ending_with_question",
                                "context": f"With {username}: Conversation ended with a long question",
                                "suggestion": "Add rule to recognize conversation end signals and close naturally"
                            })

        # Display Prompt Analysis
        col1, col2 = st.columns(2)

        with col1:
            st.write("⚠️ **Areas for Improvement**")
            if prompt_issues:
                # Group similar issues
                issues_by_type = {}
                for issue in prompt_issues:
                    if issue["type"] not in issues_by_type:
                        issues_by_type[issue["type"]] = []
                    issues_by_type[issue["type"]].append(issue)

                for issue_type, issues in issues_by_type.items():
                    with st.expander(f"{issue_type.replace('_', ' ').title()} ({len(issues)})"):
                        for issue in issues:
                            st.write(f"**Context:** {issue['context']}")
                            st.write(f"**Suggestion:** {issue['suggestion']}")
            else:
                st.info("No major issues detected in recent conversations")

        with col2:
            st.write("✅ **What's Working Well**")
            if prompt_successes:
                # Group successful patterns
                successes_by_type = {}
                for success in prompt_successes:
                    if success["type"] not in successes_by_type:
                        successes_by_type[success["type"]] = []
                    successes_by_type[success["type"]].append(success)

                for success_type, successes in successes_by_type.items():
                    with st.expander(f"{success_type.replace('_', ' ').title()} ({len(successes)})"):
                        for success in successes[:3]:  # Show top 3 examples
                            st.write(f"**Context:** {success['context']}")
                            if "example" in success:
                                st.write(f"**Example:** {success['example']}")
            else:
                st.info("No notable successes in recent conversations")

        # Prompt Improvement Suggestions
        st.write("\n**🔄 Suggested Prompt Updates**")

        # Generate specific suggestions based on patterns
        suggestions = []

        if any(i["type"] == "consecutive_questions" for i in prompt_issues):
            suggestions.append({
                "priority": "High",
                "area": "Question Management",
                "suggestion": "Add explicit rule: 'Wait for user's response before asking another question. If multiple questions are needed, combine them naturally in one message.'"
            })

        if any(i["type"] == "generic_response" for i in prompt_issues):
            suggestions.append({
                "priority": "Medium",
                "area": "Response Specificity",
                "suggestion": "Add to prompt: 'Always reference specific details from the user's message or conversation history. Avoid generic acknowledgments unless user's message is very brief.'"
            })

        if any(i["type"] == "missed_context" for i in prompt_issues):
            suggestions.append({
                "priority": "High",
                "area": "Context Tracking",
                "suggestion": "Enhance prompt with: 'Before responding, review the last 3 messages for key topics. If user mentions specific activities or goals, acknowledge and build upon them.'"
            })

        # Display suggestions in a table
        if suggestions:
            suggestion_df = pd.DataFrame(suggestions)
            st.table(suggestion_df)
        else:
            st.info("No specific prompt improvements needed at this time")

        # After the Prompt Analysis section in the Daily Report tab
        st.divider()
        st.subheader("💰 Sales Conversion Analysis")

        # Track successful conversions
        successful_conversions = []
        potential_leads = []

        for subscriber_id, conv_data in conversations.items():
            metrics = conv_data.get("metrics", {})
            history = metrics.get("conversation_history", [])

            if not history:
                continue

            # Get username for context
            username = metrics.get("ig_username", "Unknown")

            # Check if they signed up
            signed_up = metrics.get("signup_recorded", False)

            # Analyze conversation patterns
            conversation_data = {
                "username": username,
                "total_messages": len(history),
                "user_messages": len([msg for msg in history if msg.get("type") != "ai"]),
                "conversation_duration": metrics.get("conversation_duration_str", "N/A"),
                "topics_discussed": [],
                "key_moments": []
            }

            # Track when fitness was first mentioned
            fitness_first_mentioned = None
            messages_before_fitness = 0

            for i, msg in enumerate(history):
                msg_text = msg.get("text", "").lower()

                # Track fitness topic emergence
                if not fitness_first_mentioned:
                    if any(word in msg_text for word in ["fitness", "workout", "training", "exercise", "gym"]):
                        fitness_first_mentioned = i + 1
                        messages_before_fitness = i

                # Track key conversion moments
                if msg.get("type") != "ai":  # Only analyze user messages
                    msg_text = msg.get("text", "").lower()

                    # Create sets to track unique moments
                    if "key_moments" not in conversation_data:
                        conversation_data["key_moments"] = []

                    # Check for struggle mentions - be more specific
                    struggle_words = ["struggle", "hard", "difficult", "cant", "stuck", "frustrated",
                                      "having trouble", "not working", "failing", "giving up"]
                    if any(word in msg_text for word in struggle_words) and not any(existing_moment.startswith("Mentioned struggle:") for existing_moment in conversation_data["key_moments"]):
                        # Don't include Shannon's responses in the key moment
                        user_part = msg_text.split(
                            "+")[0] if "+" in msg_text else msg_text
                        conversation_data["key_moments"].append(
                            f"Mentioned struggle: '{user_part.strip()}'")

                    # Check for goal mentions - be more specific
                    goal_words = ["goal", "want to", "trying to", "hope to", "aiming for", "looking to",
                                  "would like to", "planning to", "need to"]
                    if any(word in msg_text for word in goal_words) and not any(existing_moment.startswith("Mentioned goal:") for existing_moment in conversation_data["key_moments"]):
                        user_part = msg_text.split(
                            "+")[0] if "+" in msg_text else msg_text
                        conversation_data["key_moments"].append(
                            f"Mentioned goal: '{user_part.strip()}'")

                    # Check for timing/life event mentions - be more specific
                    event_words = ["holiday", "wedding", "summer", "event", "trip", "vacation",
                                   "coming up", "next month", "planning", "birthday"]
                    if any(word in msg_text for word in event_words) and not any(existing_moment.startswith("Mentioned timing:") for existing_moment in conversation_data["key_moments"]):
                        user_part = msg_text.split(
                            "+")[0] if "+" in msg_text else msg_text
                        conversation_data["key_moments"].append(
                            f"Mentioned timing: '{user_part.strip()}'")

                    # Add fitness-specific mentions
                    fitness_words = ["gym", "workout", "training", "exercise", "fitness", "diet",
                                     "nutrition", "weight", "muscle", "strength"]
                    if any(word in msg_text for word in fitness_words) and not any(existing_moment.startswith("Fitness mention:") for existing_moment in conversation_data["key_moments"]):
                        user_part = msg_text.split(
                            "+")[0] if "+" in msg_text else msg_text
                        conversation_data["key_moments"].append(
                            f"Fitness mention: '{user_part.strip()}'")

                    # Track questions about coaching/programs
                    coaching_words = ["coach", "program", "membership", "sign up", "join", "cost",
                                      "price", "how much", "what do you offer"]
                    if any(word in msg_text for word in coaching_words) and not any(existing_moment.startswith("Asked about coaching:") for existing_moment in conversation_data["key_moments"]):
                        user_part = msg_text.split(
                            "+")[0] if "+" in msg_text else msg_text
                        conversation_data["key_moments"].append(
                            f"Asked about coaching: '{user_part.strip()}'")

            conversation_data["messages_before_fitness"] = messages_before_fitness

            if signed_up:
                successful_conversions.append(conversation_data)
            elif fitness_first_mentioned:  # They discussed fitness but haven't signed up
                potential_leads.append(conversation_data)

        # Display Conversion Insights
        conv_cols = st.columns(2)

        with conv_cols[0]:
            st.write("✅ **Recent Successful Conversions**")
            if successful_conversions:
                for conv in successful_conversions:
                    with st.expander(f"{conv['username']} - Converted"):
                        st.write(
                            f"**Messages Exchanged:** {conv['total_messages']}")
                        st.write(
                            f"**Conversation Duration:** {conv['conversation_duration']}")
                        if conv['messages_before_fitness'] > 0:
                            st.write(
                                f"**Messages Before Fitness Topic:** {conv['messages_before_fitness']}")
                        if conv['key_moments']:
                            st.write("**Key Moments:**")
                            for moment in conv['key_moments']:
                                st.write(f"- {moment}")
            else:
                st.info("No recent conversions to analyze")

        with conv_cols[1]:
            st.write("🎯 **Active Potential Leads**")
            if potential_leads:
                for lead in potential_leads:
                    with st.expander(f"{lead['username']} - Potential"):
                        st.write(
                            f"**Messages Exchanged:** {lead['total_messages']}")
                        st.write(
                            f"**Conversation Duration:** {lead['conversation_duration']}")
                        if lead['messages_before_fitness'] > 0:
                            st.write(
                                f"**Messages Before Fitness Topic:** {lead['messages_before_fitness']}")
                        if lead['key_moments']:
                            st.write("**Key Moments:**")
                            for moment in lead['key_moments']:
                                st.write(f"- {moment}")
            else:
                st.info("No active potential leads identified")

        # Conversion Pattern Insights
        if successful_conversions:
            st.write("\n**🔍 Conversion Pattern Insights**")

            # Calculate average messages before fitness topic
            avg_msgs_before_fitness = sum(c['messages_before_fitness']
                                          for c in successful_conversions) / len(successful_conversions)

            # Identify common key moments
            all_key_moments = [
                moment for conv in successful_conversions for moment in conv['key_moments']]
            moment_types = {
                "struggle": len([m for m in all_key_moments if "struggle" in m.lower()]),
                "goal": len([m for m in all_key_moments if "goal" in m.lower()]),
                "timing": len([m for m in all_key_moments if "timing" in m.lower()])
            }

            st.write(
                f"- Average messages before fitness discussion: {avg_msgs_before_fitness:.1f}")
            st.write("- Common conversion triggers:")
            for moment_type, count in moment_types.items():
                if count > 0:
                    st.write(f"  • {moment_type.title()}: {count} occurrences")

            # Suggest optimization opportunities
            st.write("\n**💡 Optimization Opportunities**")
            suggestions = []

            if avg_msgs_before_fitness > 10:
                suggestions.append(
                    "Consider ways to naturally bring up fitness topics earlier in conversations")

            most_common_trigger = max(
                moment_types.items(), key=lambda x: x[1])[0]
            suggestions.append(
                f"Focus on identifying and engaging with {most_common_trigger}-related comments")

            for suggestion in suggestions:
                st.write(f"- {suggestion}")

        # Add to the Daily Report section
        st.divider()
        st.subheader("🤖 Bot Activity Today")
        daily_cols = st.columns(3)

        with daily_cols[0]:
            messages_sent_today = bot_stats.get(
                "daily_messages_sent", {}).get(today, 0)
            messages_responded_today = bot_stats.get(
                "daily_messages_responded", {}).get(today, 0)

            st.metric("Messages Sent", messages_sent_today)
            st.metric("Messages Responded To", messages_responded_today)

            if messages_sent_today > 0:
                response_rate = (messages_responded_today /
                                 messages_sent_today) * 100
                st.metric("Today's Response Rate", f"{response_rate:.1f}%")

        with daily_cols[1]:
            # Compare with yesterday
            yesterday = (datetime.now() - timedelta(days=1)
                         ).strftime("%Y-%m-%d")
            yesterday_sent = bot_stats.get(
                "daily_messages_sent", {}).get(yesterday, 0)
            yesterday_responded = bot_stats.get(
                "daily_messages_responded", {}).get(yesterday, 0)

            sent_change = messages_sent_today - yesterday_sent
            responded_change = messages_responded_today - yesterday_responded

            st.metric("Change in Messages Sent",
                      sent_change,
                      delta_color="normal")
            st.metric("Change in Responses",
                      responded_change,
                      delta_color="normal")

        with daily_cols[2]:
            # Calculate peak hours
            if messages_sent_today > 0:
                st.write("**Peak Activity Hours:**")
                # This would require adding hour tracking to the bot message stats
                st.info("Hour tracking will be implemented in future updates")

    else:
        st.info("No conversations to analyze in the last 24 hours.")


# Analytics Export tab
with tabs[3]:
    st.header("Export Analytics Data")
    st.write(
        f"This will export the currently loaded data from {os.path.basename(ANALYTICS_FILE_PATH)}.")

    # Default export path in the same directory as the script or a subfolder
    default_export_filename = f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    default_export_path = os.path.join(os.path.dirname(
        __file__) if "__file__" in locals() else ".", default_export_filename)

    export_file = st.text_input("Export File Path", default_export_path)

    if st.button("Export Current Data"):
        # Check if data isn't empty
        if analytics_data and (analytics_data["global_metrics"] or analytics_data["conversations"]):
            try:
                # Ensure directory exists before writing
                abs_export_path = os.path.abspath(export_file)
                os.makedirs(os.path.dirname(abs_export_path), exist_ok=True)
                with open(abs_export_path, "w") as f:
                    json.dump(analytics_data, f, indent=2)
                st.success(
                    f"Current analytics data exported successfully to {abs_export_path}")
            except IOError as e:
                st.error(f"Error writing file: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred during export: {e}")
        else:
            st.error(
                "No analytics data loaded to export. Ensure the source file exists and contains data.")


# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# Auto-refresh logic
if auto_refresh:
    # Rerun the script after the interval
    time.sleep(refresh_interval)
    st.rerun()
