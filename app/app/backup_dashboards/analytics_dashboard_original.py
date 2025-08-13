import streamlit as st
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import random
import re
from wordcloud import WordCloud
import seaborn as sns

# Add this new function to deduplicate conversation history for display


def deduplicate_message_content(message_list):
    """Remove duplicate content from a list of messages to avoid repeating content in display."""
    if not message_list:
        return []

    # Sort by timestamp if available
    sorted_messages = sorted(message_list, key=lambda x: x.get(
        'timestamp', ''), reverse=False)

    # Process messages
    deduplicated = []
    seen_texts = set()

    for msg in sorted_messages:
        current_text = msg.get('text', '')

        # Check if we should extract only new content from this message
        new_text = current_text

        # For each previous message, check if it's contained in this one
        for prev_text in seen_texts:
            if prev_text in current_text and prev_text != current_text:
                # Remove the previous text from current to avoid duplication
                new_text = current_text.replace(prev_text, '').strip()
                # If multiple replacements happen, use the last result
                current_text = new_text

        # Only add if we have non-empty text after deduplication
        if new_text.strip():
            dedup_msg = msg.copy()
            dedup_msg['text'] = new_text
            deduplicated.append(dedup_msg)
            seen_texts.add(new_text)

    return deduplicated


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
ANALYTICS_FILE_PATH = "C:\\Users\\Shannon\\analytics_data.json"

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

    if not global_metrics and not conversations:
        st.warning(
            f"No analytics data loaded from {ANALYTICS_FILE_PATH}. Ensure the file exists and the webhook server is running and saving data.")
    else:
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

        # --- Display Global Metrics ---
        st.subheader("Global Metrics")
        if global_metrics:
            col1, col2 = st.columns(2)
            with col1:
                # st.subheader("Conversation Metrics")  # Subheader removed, covered by Global Metrics
                st.metric("Total Conversations Tracked", global_metrics.get(
                    "total_conversations", 0))
                # Display User/AI message counts if available
                total_user_messages = global_metrics.get(
                    "total_user_messages", 0)
                total_ai_messages = global_metrics.get("total_ai_messages", 0)
                st.metric("Total User Messages", total_user_messages)
                st.metric("Total AI Messages", total_ai_messages)
                st.metric("Coaching Inquiries", global_metrics.get(
                    "coaching_inquiries", 0))
                st.metric("AI Detections", global_metrics.get(
                    "ai_detections", 0))

            with col2:
                # st.subheader("Question Metrics")  # Subheader removed
                question_stats = global_metrics.get("question_stats", {})
                ai_questions = question_stats.get("ai_questions_asked", 0)
                # Use total AI messages if statement count isn't tracked globally
                ai_statements = global_metrics.get(
                    "ai_statements_total", total_ai_messages - ai_questions if total_ai_messages >= ai_questions else 0)

                q_s_cols = st.columns(2)
                with q_s_cols[0]:
                    st.metric("AI Questions Asked", ai_questions)
                with q_s_cols[1]:
                    st.metric("AI Statements Made", ai_statements)

                user_responses_count = question_stats.get(
                    "user_responses_to_questions", 0)
                st.metric("User Responses to Questions", user_responses_count)

                # Use calculated response rate if available, otherwise calculate
                response_rate_metric = question_stats.get("response_rate", 0)
                if ai_questions > 0 and response_rate_metric == 0:  # Recalculate if needed and not already calculated
                    calculated_rate = user_responses_count / ai_questions
                    st.metric("Question Response Rate",
                              f"{calculated_rate * 100:.1f}%")
                elif ai_questions == 0:
                    st.metric("Question Response Rate", "N/A (0 AI Q's)")
                else:  # Use the value from metrics if present and valid
                    st.metric("Question Response Rate",
                              f"{response_rate_metric * 100:.1f}%")

            st.divider()
            # --- Display Fitness Topic Initiation ---
            st.subheader("Topic Initiation & Funnel")  # Combined headers
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

            st.divider()
            # --- Display Topic Tracking ---
            st.subheader("Specific Topic Tracking")
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

            st.divider()
            # Display some charts
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
        else:
            st.info("No global metrics found in the analytics file.")

        st.divider()
        st.subheader("Follow-up Messages Overview")
        if global_metrics:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Follow-ups Sent",
                          global_metrics.get("total_follow_ups_sent", 0))
            with col2:
                # Calculate response rate to follow-ups
                total_responses = sum(1 for conv in conversations.values()
                                      if conv.get("metrics", {}).get("follow_up_responses", 0) > 0)
                if global_metrics.get("total_follow_ups_sent", 0) > 0:
                    response_rate = (
                        total_responses / global_metrics["total_follow_ups_sent"]) * 100
                    st.metric("Follow-up Response Rate",
                              f"{response_rate:.1f}%")
                else:
                    st.metric("Follow-up Response Rate", "N/A")

        st.divider()
        # --- Initial Contact Analysis ---
        st.subheader("Initial Contact & Post Analysis")

        # Create columns for the metrics
        contact_cols = st.columns(2)

        with contact_cols[0]:
            st.write("**First Contact Stats**")
            # Count users with post analysis
            users_with_analysis = sum(1 for conv in conversations.values()
                                      if conv.get("metadata", {}).get("post_analysis"))

            # Count successful first contacts (where there's at least one response)
            successful_contacts = sum(1 for conv in conversations.values()
                                      if conv.get("metrics", {}).get("user_messages", 0) > 0)

            # Calculate response rate
            if users_with_analysis > 0:
                response_rate = (successful_contacts /
                                 users_with_analysis) * 100
            else:
                response_rate = 0

            st.metric("Users Contacted", users_with_analysis)
            st.metric("Got Responses", successful_contacts)
            st.metric("Response Rate", f"{response_rate:.1f}%")

        with contact_cols[1]:
            st.write("**Post Analysis Overview**")
            # Get average time to first response
            response_times = []
            for conv in conversations.values():
                metrics = conv.get("metrics", {})
                history = metrics.get("conversation_history", [])

                first_contact = None
                first_response = None

                for msg in history:
                    if msg["type"] == "ai" and not first_contact:
                        try:
                            first_contact = datetime.fromisoformat(
                                msg["timestamp"])
                        except (ValueError, KeyError):
                            continue
                    elif msg["type"] == "user" and not first_response:
                        try:
                            first_response = datetime.fromisoformat(
                                msg["timestamp"])
                            if first_contact:
                                response_times.append(
                                    (first_response - first_contact).total_seconds())
                            break
                        except (ValueError, KeyError):
                            continue

            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                st.metric("Avg. Response Time",
                          f"{avg_response_time/3600:.1f} hours")

            # Show post analysis samples
            with st.expander("Recent Post Analyses"):
                recent_analyses = []
                for username, conv in conversations.items():
                    analysis = conv.get("metadata", {}).get(
                        "post_analysis", {})
                    if analysis and analysis.get("description"):
                        recent_analyses.append({
                            "username": username,
                            "description": analysis["description"],
                            "timestamp": analysis.get("timestamp", "Unknown")
                        })

                # Sort by timestamp and take most recent
                recent_analyses.sort(
                    key=lambda x: x["timestamp"], reverse=True)
                for analysis in recent_analyses[:5]:  # Show 5 most recent
                    st.write(f"**{analysis['username']}**")
                    st.write(f"{analysis['description'][:200]}...")
                    st.write(f"*Analyzed: {analysis['timestamp']}*")
                    st.write("---")

        st.divider()
        # --- Conversation Flow Analysis ---
        st.subheader("Conversation Flow Analysis")

        flow_cols = st.columns(2)
        with flow_cols[0]:
            st.write("**Message Patterns**")
            # Analyze typical conversation flows
            total_conversations = len(conversations)
            conversations_with_responses = sum(1 for conv in conversations.values()
                                               if conv.get("metrics", {}).get("user_messages", 0) > 0)

            if total_conversations > 0:
                engagement_rate = (
                    conversations_with_responses / total_conversations) * 100
                st.metric("Engagement Rate", f"{engagement_rate:.1f}%")

            # Calculate average messages before user mentions fitness
            fitness_mentions = []
            for conv in conversations.values():
                history = conv.get("metrics", {}).get(
                    "conversation_history", [])
                found_fitness = False
                messages_before = 0

                for msg in history:
                    if msg["type"] == "user" and any(word in msg["text"].lower()
                                                     for word in ["fitness", "workout", "gym", "training", "exercise"]):
                        found_fitness = True
                        fitness_mentions.append(messages_before)
                        break
                    messages_before += 1

            if fitness_mentions:
                avg_msgs_before_fitness = sum(
                    fitness_mentions) / len(fitness_mentions)
                st.metric("Avg Messages Before Fitness Topic",
                          f"{avg_msgs_before_fitness:.1f}")

        with flow_cols[1]:
            st.write("**Response Quality**")
            # Analyze message lengths and response times
            all_user_msgs = []
            all_ai_msgs = []

            for conv in conversations.values():
                history = conv.get("metrics", {}).get(
                    "conversation_history", [])
                for msg in history:
                    if msg["type"] == "user":
                        all_user_msgs.append(len(msg["text"].split()))
                    else:
                        all_ai_msgs.append(len(msg["text"].split()))

            if all_user_msgs:
                avg_user_msg_length = sum(all_user_msgs) / len(all_user_msgs)
                st.metric("Avg User Message Length",
                          f"{avg_user_msg_length:.1f} words")

            if all_ai_msgs:
                avg_ai_msg_length = sum(all_ai_msgs) / len(all_ai_msgs)
                st.metric("Avg AI Message Length",
                          f"{avg_ai_msg_length:.1f} words")

            # Add visualization of conversation flows
            st.write("\n**Conversation Flow Visualization**")
            if conversations:
                # Create a line chart showing message counts over time
                flow_data = []
                for conv in conversations.values():
                    history = conv.get("metrics", {}).get(
                        "conversation_history", [])
                    if history:
                        try:
                            # Group messages by day
                            daily_counts = defaultdict(
                                lambda: {"user": 0, "ai": 0})
                            for msg in history:
                                day = datetime.fromisoformat(
                                    msg["timestamp"]).date()
                                if msg["type"] == "user":
                                    daily_counts[day]["user"] += 1
                                else:
                                    daily_counts[day]["ai"] += 1

                            # Convert to dataframe format
                            for day, counts in daily_counts.items():
                                flow_data.append({
                                    "Date": day,
                                    "User Messages": counts["user"],
                                    "AI Messages": counts["ai"]
                                })
                        except (ValueError, KeyError):
                            continue

                if flow_data:
                    flow_df = pd.DataFrame(flow_data)
                    flow_df = flow_df.groupby("Date").sum().reset_index()

                    # Create the line chart
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.plot(flow_df["Date"], flow_df["User Messages"],
                            label="User Messages", marker='o')
                    ax.plot(flow_df["Date"], flow_df["AI Messages"],
                            label="AI Messages", marker='o')

                    plt.title("Daily Message Volume")
                    plt.xlabel("Date")
                    plt.ylabel("Number of Messages")
                    plt.legend()
                    plt.xticks(rotation=45)
                    plt.tight_layout()

                    st.pyplot(fig)
            else:
                st.info("No conversation data available for visualization")

        st.divider()
        st.subheader("Follow-up Message History")
        if conversations:
            for idx, conv in enumerate(conversations.values()):
                with st.expander(f"Conversation {idx + 1} - {conv['metrics'].get('ig_username', 'Unnamed User')}"):
                    st.write("**Conversation History:**")
                    history = conv['metrics'].get('conversation_history', [])
                    for msg in history:
                        st.write(f"- {msg.get('text', 'No message text')}")
                    st.write("**Conversation Metrics:**")
                    for metric, value in conv['metrics'].items():
                        if metric not in ['conversation_history', 'responder_category', 'ig_username']:
                            st.write(f"- {metric}: {value}")
                    st.write("**Conversation Metadata:**")
                    for meta_key, meta_value in conv['metadata'].items():
                        st.write(f"- {meta_key}: {meta_value}")


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
            username = metrics.get("ig_username")

            # Only use username if it exists and is not None
            if username:
                display_name = username
                # In case of duplicate usernames, append a number
                temp_display_name = display_name
                counter = 1
                while temp_display_name in id_map:
                    temp_display_name = f"{display_name} ({counter})"
                    counter += 1
                display_name = temp_display_name
            else:
                # If no username, use ID as fallback
                display_name = sub_id

            available_display_names.append(display_name)
            id_map[display_name] = sub_id

        # Sort usernames alphabetically, keeping IDs at the bottom
        available_display_names = sorted(
            available_display_names,
            # Sort numbers last, rest alphabetically
            key=lambda x: (x.isdigit(), x.lower())
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

        # After the Conversion Pattern Insights section in the Daily Report tab
        st.divider()
        st.subheader("📊 Additional Conversation Insights")

        insight_cols = st.columns(2)

        with insight_cols[0]:
            # Word Cloud of Common Topics
            st.write("**🔤 Common Topics Word Cloud**")

            # Collect all message text
            all_text = []
            for conv_data in conversations.values():
                history = conv_data.get("metrics", {}).get(
                    "conversation_history", [])
                for msg in history:
                    if msg.get("type") == "user":  # Only analyze user messages
                        text = msg.get("text", "").lower()
                        # Remove common words and punctuation
                        text = re.sub(r'[^\w\s]', '', text)
                        stop_words = {'the', 'and', 'is', 'in', 'it', 'to', 'i', 'you', 'that', 'was', 'for', 'on', 'are', 'like',
                                      'just', 'but', 'have', 'with', 'what', 'about', 'when', 'can', 'so', 'this', 'your', 'would', 'could', 'how'}
                        words = [word for word in text.split()
                                 if word not in stop_words]
                        all_text.extend(words)

            if all_text:
                # Generate word cloud
                wordcloud = WordCloud(width=800, height=400, background_color='white',
                                      colormap='viridis').generate(' '.join(all_text))

                # Display word cloud
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis('off')
                st.pyplot(fig)
            else:
                st.info("Not enough conversation data for word cloud")

        with insight_cols[1]:
            # Success Rate by Time of Day
            st.write("**⏰ Best Engagement Times**")

            # Collect message timestamps and responses
            time_responses = defaultdict(lambda: {"total": 0, "responses": 0})

            for conv_data in conversations.values():
                history = conv_data.get("metrics", {}).get(
                    "conversation_history", [])
                for i, msg in enumerate(history):
                    if msg.get("type") == "ai" and i < len(history) - 1:
                        try:
                            msg_time = datetime.fromisoformat(
                                msg.get("timestamp")).hour
                            hour_block = f"{msg_time:02d}:00"
                            time_responses[hour_block]["total"] += 1
                            # Check if user responded
                            if history[i + 1].get("type") != "ai":
                                time_responses[hour_block]["responses"] += 1
                        except (ValueError, TypeError):
                            continue

            if time_responses:
                # Calculate response rates
                hours = sorted(time_responses.keys())
                response_rates = [time_responses[h]["responses"] /
                                  time_responses[h]["total"] *
                                  100 if time_responses[h]["total"] > 0 else 0
                                  for h in hours]

                # Create bar chart
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.bar(hours, response_rates)
                plt.xticks(rotation=45)
                plt.title("Response Rate by Time of Day")
                plt.ylabel("Response Rate (%)")
                st.pyplot(fig)
            else:
                st.info("Not enough timing data for engagement analysis")

        # New row for additional charts
        insight_cols2 = st.columns(2)

        with insight_cols2[0]:
            # Message Length Analysis
            st.write("**📏 Message Length Patterns**")

            user_lengths = []
            ai_lengths = []

            for conv_data in conversations.values():
                history = conv_data.get("metrics", {}).get(
                    "conversation_history", [])
                for msg in history:
                    text = msg.get("text", "")
                    if msg.get("type") == "ai":
                        ai_lengths.append(len(text.split()))
                    else:
                        user_lengths.append(len(text.split()))

            if user_lengths and ai_lengths:
                # Create violin plot
                fig, ax = plt.subplots(figsize=(10, 5))
                data = [user_lengths, ai_lengths]
                sns.violinplot(data=data, ax=ax)
                plt.xticks([0, 1], ['User Messages', 'AI Messages'])
                plt.title("Message Length Distribution")
                plt.ylabel("Words per Message")
                st.pyplot(fig)
            else:
                st.info("Not enough message data for length analysis")

        with insight_cols2[1]:
            # Conversion Funnel
            st.write("**🔄 Conversation Flow**")

            # Track conversation stages
            funnel_stages = {
                "Initial Contact": 0,
                "Engaged (2+ msgs)": 0,
                "Discussed Fitness": 0,
                "Asked Questions": 0,
                "Showed Interest": 0
            }

            for conv_data in conversations.values():
                metrics = conv_data.get("metrics", {})
                history = metrics.get("conversation_history", [])

                # Count stages
                funnel_stages["Initial Contact"] += 1

                if len(history) >= 2:
                    funnel_stages["Engaged (2+ msgs)"] += 1

                if metrics.get("fitness_topic_user_initiated") or metrics.get("fitness_topic_ai_initiated"):
                    funnel_stages["Discussed Fitness"] += 1

                if metrics.get("user_responses_to_questions", 0) > 0:
                    funnel_stages["Asked Questions"] += 1

                if metrics.get("coaching_inquiries", 0) > 0:
                    funnel_stages["Showed Interest"] += 1

            if any(funnel_stages.values()):
                # Create funnel chart
                fig, ax = plt.subplots(figsize=(10, 5))
                stages = list(funnel_stages.keys())
                values = list(funnel_stages.values())

                # Calculate percentages
                percentages = [v / values[0] * 100 for v in values]

                # Create bars with decreasing width
                max_width = 0.8
                width_reduction = max_width / len(stages)

                for i, (pct, val) in enumerate(zip(percentages, values)):
                    width = max_width - (i * width_reduction)
                    x = (1 - width) / 2
                    # Removed width parameter
                    ax.barh(i, pct, left=x, height=0.5)
                    # Add value labels
                    ax.text(x + pct + 1, i, f"{val} ({pct:.1f}%)", va='center')

                plt.yticks(range(len(stages)), stages)
                plt.xlabel("Percentage of Initial Contacts")
                plt.title("Conversation Funnel")
                st.pyplot(fig)
            else:
                st.info("Not enough conversion data for funnel analysis")

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
