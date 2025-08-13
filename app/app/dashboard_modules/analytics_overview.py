"""
Analytics & Overview Module
Handles metrics calculations, overview display, and recent interactions analytics
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
import json
import pandas as pd
import sqlite3
import os

# Import the conversion stats functions
from overview import get_challenge_offered_count, get_trial_started_count, get_conversion_stats

# Configure logging
logger = logging.getLogger(__name__)


def get_follow_back_stats(start_date: datetime, end_date: datetime) -> dict:
    """
    Retrieves follow and follow-back stats for a given time period.
    'Followed' is based on when the action was taken.
    'Followed Back' is based on when the follow-back was detected.
    'Unfollowed' is based on when users didn't follow back and were unfollowed.
    """
    stats = {'followed_count': 0, 'followed_back_count': 0,
             'unfollowed_count': 0, 'follow_back_rate': 0.0}
    try:
        db_path = os.path.join(os.path.dirname(
            __file__), '..', 'analytics_data_good.sqlite')
        if not os.path.exists(db_path):
            logger.error(f"Database not found at {db_path}")
            return stats

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # --- 1. Get People Followed in the time period ---
        if start_date and end_date:
            # For specific date ranges
            followed_query = """
                SELECT COUNT(username) FROM processing_queue
                WHERE followed_at BETWEEN ? AND ?
            """
            cursor.execute(followed_query, (
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            ))
        else:
            # For "All Time"
            followed_query = "SELECT COUNT(username) FROM processing_queue WHERE followed_at IS NOT NULL"
            cursor.execute(followed_query)

        stats['followed_count'] = cursor.fetchone()[0] or 0

        # --- 2. Get People who Followed Back in the time period ---
        if start_date and end_date:
            # Count follow backs that were detected in the time period
            followed_back_query = """
                SELECT COUNT(username) FROM processing_queue
                WHERE follow_back_status = 'yes'
                AND follow_back_checked_at BETWEEN ? AND ?
            """
            cursor.execute(followed_back_query, (
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            ))
        else:
            # For "All Time" - all users who have followed back
            followed_back_query = """
                SELECT COUNT(username) FROM processing_queue
                WHERE follow_back_status = 'yes'
            """
            cursor.execute(followed_back_query)

        stats['followed_back_count'] = cursor.fetchone()[0] or 0

        # --- 3. Get People who were Unfollowed in the time period ---
        if start_date and end_date:
            # Count unfollows that happened in the time period
            unfollowed_query = """
                SELECT COUNT(username) FROM processing_queue
                WHERE follow_back_status IN ('no', 'no_unfollow_failed', 'no_unfollow_limit_reached')
                AND follow_back_checked_at BETWEEN ? AND ?
            """
            cursor.execute(unfollowed_query, (
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            ))
        else:
            # For "All Time" - all users who were unfollowed
            unfollowed_query = """
                SELECT COUNT(username) FROM processing_queue
                WHERE follow_back_status IN ('no', 'no_unfollow_failed', 'no_unfollow_limit_reached')
            """
            cursor.execute(unfollowed_query)

        stats['unfollowed_count'] = cursor.fetchone()[0] or 0

        # --- 4. Calculate Follow Back Rate ---
        if stats['followed_count'] > 0:
            stats['follow_back_rate'] = (
                stats['followed_back_count'] / stats['followed_count']) * 100
        else:
            stats['follow_back_rate'] = 0.0

        conn.close()
        logger.info(f"Follow stats: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error getting follow back stats: {e}", exc_info=True)
        return stats


def get_date_range(period: str) -> tuple[datetime, datetime]:
    """Return start_date, end_date for the given period"""
    now = datetime.now()

    if period == "All Time":
        return None, None  # No date filtering
    elif period == "Today":
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_today, now
    elif period == "Last 7 Days":
        return now - timedelta(days=7), now
    elif period == "Last 30 Days":
        return now - timedelta(days=30), now
    elif period == "This Week":
        days_since_monday = now.weekday()
        start_of_week = now - timedelta(days=days_since_monday)
        start_of_week = start_of_week.replace(
            hour=0, minute=0, second=0, microsecond=0)
        return start_of_week, now
    elif period == "This Month":
        start_of_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_of_month, now
    else:
        return None, None  # Default to all time


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string into datetime object"""
    if not timestamp_str:
        return None

    try:
        # Handle various timestamp formats
        timestamp_str = timestamp_str.split('+')[0]  # Remove timezone info
        timestamp_str = timestamp_str.split(
            '.')[0]  # Remove microseconds if present

        # Try different formats
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d'
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # Try ISO format
        return datetime.fromisoformat(timestamp_str)
    except Exception as e:
        logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
        return None


def is_user_in_date_range(user_container: dict, start_date: datetime, end_date: datetime) -> bool:
    """Check if user activity falls within the specified date range"""
    if start_date is None and end_date is None:
        return True  # All time filter

    user_metrics = user_container.get('metrics', {})
    if not user_metrics:
        return False

    # Try multiple timestamp fields to determine user activity
    timestamp_fields = [
        'last_interaction_timestamp',
        'last_updated',
        'timestamp',
        'updated_at',
        'last_message_time'
    ]

    user_timestamps = []

    # Check direct timestamp fields
    for field in timestamp_fields:
        timestamp_str = user_metrics.get(field)
        if timestamp_str:
            parsed_time = parse_timestamp(timestamp_str)
            if parsed_time:
                user_timestamps.append(parsed_time)

    # Check conversation history for message timestamps
    conversation_history = user_metrics.get('conversation_history', [])
    for message in conversation_history:
        timestamp_str = message.get('timestamp', '')
        if timestamp_str:
            parsed_time = parse_timestamp(timestamp_str)
            if parsed_time:
                user_timestamps.append(parsed_time)

    # Check client analysis timestamp
    client_analysis = user_metrics.get('client_analysis', {})
    if isinstance(client_analysis, dict):
        analysis_timestamp = client_analysis.get('timestamp')
        if analysis_timestamp:
            parsed_time = parse_timestamp(analysis_timestamp)
            if parsed_time:
                user_timestamps.append(parsed_time)

    # If no timestamps found, exclude user from filtered results
    if not user_timestamps:
        return False

    # Check if any timestamp falls within range
    for user_time in user_timestamps:
        if start_date is None or user_time >= start_date:
            if end_date is None or user_time <= end_date:
                return True

    return False


def get_stage_metrics(data, time_period="All Time"):
    """Calculate metrics for each stage of the client journey from loaded data."""
    try:
        conversations_data = data.get('conversations', {})
        if not conversations_data:
            logger.warning(
                "No conversations data available to calculate stage metrics.")
            return {
                'total_users': 0, 'engaged_users': 0, 'analyzed_profiles': 0,
                'total_messages': 0, 'response_rate': 0, 'avg_messages': 0,
                'avg_posts_per_profile': 0, 'paying_clients': 0, 'trial_clients': 0,
                'active_conversations': 0, 'bot_messages_sent_that_could_be_replied_to': 0,
                'user_replies_to_bot_messages': 0
            }

        # Get date range for filtering
        start_date, end_date = get_date_range(time_period)

        # NEW: Get follow back stats for the period
        follow_stats = get_follow_back_stats(start_date, end_date)

        # Filter users based on time period
        if time_period != "All Time":
            filtered_conversations = {}
            for username, user_container in conversations_data.items():
                if is_user_in_date_range(user_container, start_date, end_date):
                    filtered_conversations[username] = user_container
            conversations_data = filtered_conversations

        metrics_summary = {
            'total_users': len(conversations_data),
            'engaged_users': 0,
            'analyzed_profiles': 0,
            'total_messages': 0,
            # This will be (user_replies_to_bot / bot_messages_sent_could_be_replied_to)
            'response_rate': 0,
            'avg_messages': 0,
            'paying_clients': 0,
            'trial_clients': 0,
            'active_conversations': 0,  # Users with messages in last 7 days
            # NEW fields for new response rate: "What percentage of messages sent by the bot receive a reply from the user?"
            'bot_messages_sent_that_could_be_replied_to': 0,
            'user_replies_to_bot_messages': 0
        }

        # Add follow stats to the main metrics summary
        metrics_summary.update(follow_stats)

        analyzed_user_count = 0
        total_analyzed_posts_sum = 0

        for username, user_container in conversations_data.items():
            user_metrics_data = user_container.get('metrics', {})
            if not user_metrics_data:
                continue

            # --- Calculate new response rate based on conversation history ---
            conversation_history = user_metrics_data.get(
                'conversation_history', [])
            last_message_type = None
            for message in conversation_history:
                current_message_type = message.get('type')
                if current_message_type == 'ai':  # Message from bot/AI
                    metrics_summary['bot_messages_sent_that_could_be_replied_to'] += 1
                elif current_message_type == 'user' and last_message_type == 'ai':  # User message following a bot message
                    metrics_summary['user_replies_to_bot_messages'] += 1

                if current_message_type in ['ai', 'user']:
                    last_message_type = current_message_type
            # --- End new response rate calculation for this user ---

            # Check for paying clients and trial clients
            journey_stage = user_metrics_data.get('journey_stage', {})
            if isinstance(journey_stage, dict):
                if journey_stage.get('is_paying_client', False):
                    metrics_summary['paying_clients'] += 1
                elif journey_stage.get('trial_start_date'):
                    metrics_summary['trial_clients'] += 1

            # Check for active conversations (messages in last 7 days)
            seven_days_ago = datetime.now() - timedelta(days=7)
            conversation_history = user_metrics_data.get(
                'conversation_history', [])
            has_recent_activity = False

            for message in conversation_history:
                message_timestamp = parse_timestamp(
                    message.get('timestamp', ''))
                if message_timestamp and message_timestamp >= seven_days_ago:
                    has_recent_activity = True
                    break

            if has_recent_activity:
                metrics_summary['active_conversations'] += 1

            client_analysis_data = user_metrics_data.get('client_analysis', {})
            if not isinstance(client_analysis_data, dict):
                client_analysis_data = {}

            if client_analysis_data and client_analysis_data.get('posts_analyzed', 0) > 0:
                analyzed_user_count += 1
                total_analyzed_posts_sum += client_analysis_data.get(
                    'posts_analyzed', 0)

            current_user_messages = user_metrics_data.get('user_messages', 0)
            current_total_messages_for_user = user_metrics_data.get(
                'total_messages', 0)

            if current_user_messages > 0:
                metrics_summary['engaged_users'] += 1
            metrics_summary['total_messages'] += current_total_messages_for_user

        # Calculate NEW response rate: (user_replies_to_bot_messages / bot_messages_sent_that_could_be_replied_to) * 100
        if metrics_summary['bot_messages_sent_that_could_be_replied_to'] > 0:
            metrics_summary['response_rate'] = (
                metrics_summary['user_replies_to_bot_messages'] /
                metrics_summary['bot_messages_sent_that_could_be_replied_to']
            ) * 100
        else:
            # No bot messages to reply to
            metrics_summary['response_rate'] = 0.0

        # Calculate averages for other metrics AND FIX SYNTAX ERROR
        if metrics_summary['engaged_users'] > 0:
            metrics_summary['avg_messages'] = metrics_summary['total_messages'] / \
                metrics_summary['engaged_users']  # Fixed line continuation

        metrics_summary['analyzed_profiles'] = analyzed_user_count
        metrics_summary['avg_posts_per_profile'] = total_analyzed_posts_sum / \
            analyzed_user_count if analyzed_user_count > 0 else 0  # Fixed line continuation

        logger.info(
            f"Calculated stage metrics for {time_period}: {metrics_summary}")
        return metrics_summary
    except Exception as e:
        logger.error(f"Error calculating stage metrics: {e}", exc_info=True)
        return {
            'total_users': 0, 'engaged_users': 0, 'analyzed_profiles': 0, 'total_messages': 0,
            'response_rate': 0, 'avg_messages': 0, 'avg_posts_per_profile': 0,
            'paying_clients': 0, 'trial_clients': 0, 'active_conversations': 0,
            'bot_messages_sent_that_could_be_replied_to': 0,
            'user_replies_to_bot_messages': 0
        }


def display_overview_tab(analytics_data_dict):
    """
    Display the main overview tab with key metrics and visualizations.
    """
    st.header("📈 Overview")

    # Time period selector
    time_period = st.selectbox(
        "Time Period",
        ["Today", "Last 7 Days", "Last 30 Days",
            "This Week", "This Month", "All Time"],
        index=2  # Default to "Last 30 Days"
    )

    # Get metrics for the selected time period
    metrics = get_stage_metrics(analytics_data_dict, time_period)

    start_date, end_date = get_date_range(time_period)
    if start_date and end_date:
        st.caption(
            f"Showing data from {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}")

    # Display key metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Users", f"{metrics.get('total_users', 0)}")
        st.metric("Engaged Users", f"{metrics.get('engaged_users', 0)}")

    with col2:
        st.metric("Total Messages", f"{metrics.get('total_messages', 0)}")
        st.metric("Avg Messages per User",
                  f"{metrics.get('avg_messages', 0):.1f}")

    with col3:
        st.metric("Response Rate",
                  f"{metrics.get('response_rate', 0):.1f}%")
        st.metric("Analyzed Profiles",
                  f"{metrics.get('analyzed_profiles', 0)}")

    with col4:
        st.metric("🆓 Trial Clients",
                  f"{metrics.get('trial_clients', 0)}")
        st.metric("Active Conversations",
                  f"{metrics.get('active_conversations', 0)}")

    st.divider()

    # --- Display Challenge & Conversion Stats ---
    st.subheader("🎯 Challenge & Conversion Metrics")
    col_challenge1, col_challenge2, col_challenge3 = st.columns(3)

    with col_challenge1:
        challenge_offered = get_challenge_offered_stats(
            analytics_data_dict, time_period)
        if st.button(f"🎁 Challenge Offered\n{challenge_offered}",
                     key="btn_challenge_offered",
                     use_container_width=True,
                     help="Click to see conversations where challenges were offered"):
            st.session_state.show_challenge_offered = True
            st.session_state.show_challenge_accepted = False
            st.session_state.show_paying_clients = False
        elif not hasattr(st.session_state, 'show_challenge_offered'):
            st.metric("🎁 Challenge Offered", f"{challenge_offered}")

    with col_challenge2:
        challenge_accepted = get_challenge_accepted_stats(
            analytics_data_dict, time_period)
        if st.button(f"✅ Challenge Accepted\n{challenge_accepted}",
                     key="btn_challenge_accepted",
                     use_container_width=True,
                     help="Click to see conversations where challenges were accepted"):
            st.session_state.show_challenge_accepted = True
            st.session_state.show_challenge_offered = False
            st.session_state.show_paying_clients = False
        elif not hasattr(st.session_state, 'show_challenge_accepted'):
            st.metric("✅ Challenge Accepted", f"{challenge_accepted}")

    with col_challenge3:
        paying_clients = get_paying_clients_stats(
            analytics_data_dict, time_period)
        if st.button(f"💰 Paying Clients\n{paying_clients}",
                     key="btn_paying_clients",
                     use_container_width=True,
                     help="Click to see paying client conversations"):
            st.session_state.show_paying_clients = True
            st.session_state.show_challenge_offered = False
            st.session_state.show_challenge_accepted = False
        elif not hasattr(st.session_state, 'show_paying_clients'):
            st.metric("💰 Paying Clients", f"{paying_clients}")

    # Calculate conversion rates
    if challenge_offered > 0:
        acceptance_rate = (challenge_accepted / challenge_offered) * 100
        conversion_rate = (paying_clients / challenge_offered) * 100

        col_rate1, col_rate2, col_rate3 = st.columns(3)
        with col_rate1:
            st.metric("📈 Acceptance Rate", f"{acceptance_rate:.1f}%",
                      help="% of people who accepted after being offered the challenge")
        with col_rate2:
            st.metric("💫 Conversion Rate", f"{conversion_rate:.1f}%",
                      help="% of people who became paying clients after being offered")
        with col_rate3:
            if challenge_accepted > 0:
                payment_rate = (paying_clients / challenge_accepted) * 100
                st.metric("💎 Payment Rate", f"{payment_rate:.1f}%",
                          help="% of people who became paying after accepting challenge")

    # --- Display Conversation Details Based on Button Clicks ---
    display_conversation_details(analytics_data_dict, time_period)

    st.divider()

    # --- Display Follow Stats ---
    st.subheader("👥 Follow & Engagement Stats")
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("People Followed", f"{metrics.get('followed_count', 0)}")
    with col6:
        st.metric("Followed Back", f"{metrics.get('followed_back_count', 0)}")
    with col7:
        st.metric("Unfollowed", f"{metrics.get('unfollowed_count', 0)}")
    with col8:
        st.metric("Follow Back Rate",
                  f"{metrics.get('follow_back_rate', 0.0):.1f}%")

    # Removed Recent Interactions section as requested


def get_users_from_time_period(analytics_data_dict, time_period="Last 30 Days"):
    """
    Get a list of users who were active within a specific time period.
    DEPRECATED: is_user_in_date_range is now used for filtering.
    """
    # This function is kept for any potential legacy calls but should be refactored out.
    logger.warning(
        "get_users_from_time_period is deprecated and should be removed.")
    active_users = []
    start_date, end_date = get_date_range(time_period)

    if not start_date or not end_date:
        return list(analytics_data_dict.get('conversations', {}).keys())

    for username, user_container in analytics_data_dict.get('conversations', {}).items():
        if is_user_in_date_range(user_container, start_date, end_date):
            active_users.append(username)

    return active_users


def get_users_from_last_30_days(analytics_data_dict):
    """Get all users who have had an interaction in the last 30 days."""
    # This is a specific use-case of the more general function.
    return get_users_from_time_period(analytics_data_dict, "Last 30 Days")


def display_recent_interactions(analytics_data_dict):
    """Display recent messages and user interactions in a formatted way."""
    all_interactions = []

    start_date, end_date = get_date_range("Last 7 Days")  # Hardcoded for now

    for username, user_container in analytics_data_dict.get('conversations', {}).items():
        user_metrics = user_container.get('metrics', {})
        if not user_metrics:
            continue

        # Filter by date range
        if not is_user_in_date_range(user_container, start_date, end_date):
            continue

        conversation_history = user_metrics.get('conversation_history', [])
        for message in conversation_history:
            timestamp_str = message.get('timestamp')
            parsed_time = parse_timestamp(timestamp_str)

            if parsed_time:
                interaction = {
                    'Timestamp': parsed_time,
                    'User': user_metrics.get('ig_username', username),
                    'Type': message.get('type', 'Unknown').capitalize(),
                    'Message': message.get('text', '')
                }
                all_interactions.append(interaction)

    if not all_interactions:
        st.info("No recent interactions to display for the selected period.")
        return

    # Create DataFrame and sort by timestamp
    interactions_df = pd.DataFrame(all_interactions)
    interactions_df.sort_values(by='Timestamp', ascending=False, inplace=True)

    # Format for display
    interactions_df['Timestamp'] = interactions_df['Timestamp'].dt.strftime(
        '%Y-%m-%d %H:%M')

    # Truncate long messages
    interactions_df['Message'] = interactions_df['Message'].str.slice(0, 150)

    # Select and rename columns for the final display
    display_df = interactions_df[['Timestamp', 'User', 'Type', 'Message']]

    st.dataframe(display_df)


def get_challenge_offered_stats(analytics_data_dict, time_period="All Time") -> int:
    """
    Count users who were offered the 28-Day Challenge based on specific phrases from prompts.py
    Looks for Shannon's offer messages containing challenge-related keywords.
    Now checks BOTH JSON data AND SQLite messages table.
    """
    try:
        start_date, end_date = get_date_range(time_period)
        offered_count = 0

        # Challenge offer phrases from prompts.py
        offer_phrases = [
            "28-Day Winter Challenge",
            "28-Day Winter Vegan Challenge",
            "free 28-Day Winter Challenge",
            "free 28-Day Winter Vegan Challenge",
            "free 28-Day",
            "reckon you'd be perfect for my",
            "I'm taking on a small group for my",
            "something that might be perfect for someone with your",
            # Additional phrases found in actual messages
            "28-day",
            "coaching"
        ]

        users_offered = set()  # Track unique users to avoid double counting

        # Method 1: Check JSON analytics data (existing method)
        conversations_data = analytics_data_dict.get('conversations', {})

        for username, user_container in conversations_data.items():
            if not isinstance(user_container, dict) or 'metrics' not in user_container:
                continue

            metrics = user_container['metrics']
            if not isinstance(metrics, dict):
                continue

            # Check if user falls within date range
            if not is_user_in_date_range(user_container, start_date, end_date):
                continue

            conversation_history = metrics.get('conversation_history', [])

            # Look for Shannon's messages containing offer phrases
            for message in conversation_history:
                if message.get('type') == 'ai':  # Shannon's messages
                    message_text = message.get('text', '').lower()

                    # Check for any offer phrase
                    if any(phrase.lower() in message_text for phrase in offer_phrases):
                        users_offered.add(username)
                        logger.info(
                            f"Challenge offered detected (JSON) for {username}")
                        break  # Count once per user

        # Method 2: Check SQLite messages table (NEW!)
        try:
            import sqlite3
            from datetime import datetime

            conn = sqlite3.connect('app/analytics_data_good.sqlite')
            cursor = conn.cursor()

            # Format dates for SQLite
            if time_period == "Today":
                start_date_str = start_date.strftime('%Y-%m-%d')
                end_date_str = end_date.strftime('%Y-%m-%d')
                date_filter = "DATE(timestamp) = ?"
                date_params = (start_date_str,)
            elif time_period == "All Time":
                date_filter = "1=1"
                date_params = ()
            else:
                start_date_str = start_date.strftime('%Y-%m-%d')
                end_date_str = end_date.strftime('%Y-%m-%d')
                date_filter = "DATE(timestamp) BETWEEN ? AND ?"
                date_params = (start_date_str, end_date_str)

            # Query messages table for bot messages in date range
            query = f"""
                SELECT DISTINCT ig_username, text, timestamp 
                FROM messages 
                WHERE type = 'bot' AND {date_filter}
            """

            cursor.execute(query, date_params)
            bot_messages = cursor.fetchall()

            # Check each message for offer phrases
            for username, text, timestamp in bot_messages:
                if text and username not in users_offered:  # Avoid double counting
                    text_lower = text.lower()
                    if any(phrase.lower() in text_lower for phrase in offer_phrases):
                        users_offered.add(username)
                        logger.info(
                            f"Challenge offered detected (SQLite) for {username}")

            conn.close()

        except Exception as sqlite_error:
            logger.warning(
                f"SQLite challenge offer check failed: {sqlite_error}")

        offered_count = len(users_offered)
        logger.info(
            f"Challenge offered count for {time_period}: {offered_count}")
        return offered_count

    except Exception as e:
        logger.error(
            f"Error calculating challenge offered stats: {e}", exc_info=True)
        return 0


def get_challenge_accepted_stats(analytics_data_dict, time_period="All Time") -> int:
    """
    Count users who accepted the challenge by looking for positive responses 
    followed by Shannon's onboarding trigger phrase from prompts.py
    """
    try:
        start_date, end_date = get_date_range(time_period)
        accepted_count = 0

        # Positive response phrases from prompts.py
        positive_responses = [
            "that sounds good",
            "i'm interested",
            "tell me more",
            "okay, i'd like to try that",
            "yes",
            "yeah",
            "sounds great",
            "keen",
            "interested"
        ]

        # Shannon's onboarding trigger phrase from prompts.py
        onboarding_trigger = "awesome, lets get you onboarded"

        conversations_data = analytics_data_dict.get('conversations', {})

        for username, user_container in conversations_data.items():
            if not isinstance(user_container, dict) or 'metrics' not in user_container:
                continue

            metrics = user_container['metrics']
            if not isinstance(metrics, dict):
                continue

            # Check if user falls within date range
            if not is_user_in_date_range(user_container, start_date, end_date):
                continue

            conversation_history = metrics.get('conversation_history', [])

            # Look for pattern: user positive response -> Shannon's onboarding trigger
            for i, message in enumerate(conversation_history):
                if message.get('type') == 'user':  # User message
                    user_text = message.get('text', '').lower()

                    # Check if user gave positive response
                    if any(response in user_text for response in positive_responses):
                        # Check if Shannon responded with onboarding trigger in next few messages
                        for j in range(i + 1, min(i + 4, len(conversation_history))):
                            next_message = conversation_history[j]
                            if next_message.get('type') == 'ai':  # Shannon's response
                                shannon_text = next_message.get(
                                    'text', '').lower()
                                if onboarding_trigger in shannon_text:
                                    accepted_count += 1
                                    logger.info(
                                        f"Challenge accepted detected for {username}")
                                    break
                        break  # Count once per user

        logger.info(
            f"Challenge accepted count for {time_period}: {accepted_count}")
        return accepted_count

    except Exception as e:
        logger.error(
            f"Error calculating challenge accepted stats: {e}", exc_info=True)
        return 0


def get_paying_clients_stats(analytics_data_dict, time_period="All Time") -> int:
    """
    Count users who became paying clients by looking for completed onboarding 
    (reached Shannon's final onboarding phrase from prompts.py)
    """
    try:
        start_date, end_date = get_date_range(time_period)
        paying_count = 0

        # Shannon's final onboarding phrase from prompts.py
        final_onboarding_phrase = "no worries! ill let you know when your set up"

        conversations_data = analytics_data_dict.get('conversations', {})

        for username, user_container in conversations_data.items():
            if not isinstance(user_container, dict) or 'metrics' not in user_container:
                continue

            metrics = user_container['metrics']
            if not isinstance(metrics, dict):
                continue

            # Check if user falls within date range
            if not is_user_in_date_range(user_container, start_date, end_date):
                continue

            # Method 1: Check journey_stage for paying client status
            journey_stage = metrics.get('journey_stage', {})
            if isinstance(journey_stage, dict) and journey_stage.get('is_paying_client'):
                paying_count += 1
                logger.info(
                    f"Paying client detected via journey_stage for {username}")
                continue

            # Method 2: Check conversation for completed onboarding
            conversation_history = metrics.get('conversation_history', [])
            for message in conversation_history:
                if message.get('type') == 'ai':  # Shannon's messages
                    message_text = message.get('text', '').lower()
                    if final_onboarding_phrase in message_text:
                        paying_count += 1
                        logger.info(
                            f"Paying client detected via onboarding completion for {username}")
                        break  # Count once per user

        logger.info(f"Paying clients count for {time_period}: {paying_count}")
        return paying_count

    except Exception as e:
        logger.error(
            f"Error calculating paying clients stats: {e}", exc_info=True)
        return 0


def display_conversation_details(analytics_data_dict, time_period):
    """Display conversation details based on which metric button was clicked"""

    # Check which button was clicked and display accordingly
    if hasattr(st.session_state, 'show_challenge_offered') and st.session_state.show_challenge_offered:
        st.subheader("🎁 Conversations with Challenge Offers")

        # Add close button
        if st.button("❌ Close Details", key="close_offered"):
            st.session_state.show_challenge_offered = False
            st.rerun()

        display_challenge_offered_conversations(
            analytics_data_dict, time_period)

    elif hasattr(st.session_state, 'show_challenge_accepted') and st.session_state.show_challenge_accepted:
        st.subheader("✅ Conversations with Challenge Acceptance")

        # Add close button
        if st.button("❌ Close Details", key="close_accepted"):
            st.session_state.show_challenge_accepted = False
            st.rerun()

        display_challenge_accepted_conversations(
            analytics_data_dict, time_period)

    elif hasattr(st.session_state, 'show_paying_clients') and st.session_state.show_paying_clients:
        st.subheader("💰 Paying Client Conversations")

        # Add close button
        if st.button("❌ Close Details", key="close_paying"):
            st.session_state.show_paying_clients = False
            st.rerun()

        display_paying_client_conversations(analytics_data_dict, time_period)


def display_challenge_offered_conversations(analytics_data_dict, time_period):
    """Display conversations where challenges were offered"""
    try:
        start_date, end_date = get_date_range(time_period)

        # Challenge offer phrases from prompts.py
        offer_phrases = [
            "28-Day Winter Challenge",
            "28-Day Winter Vegan Challenge",
            "free 28-Day Winter Challenge",
            "free 28-Day Winter Vegan Challenge",
            "free 28-Day",
            "reckon you'd be perfect for my",
            "I'm taking on a small group for my",
            "something that might be perfect for someone with your"
        ]

        conversations_data = analytics_data_dict.get('conversations', {})
        offered_conversations = []

        for username, user_container in conversations_data.items():
            if not isinstance(user_container, dict) or 'metrics' not in user_container:
                continue

            metrics = user_container['metrics']
            if not isinstance(metrics, dict):
                continue

            # Check if user falls within date range
            if not is_user_in_date_range(user_container, start_date, end_date):
                continue

            conversation_history = metrics.get('conversation_history', [])
            ig_username = metrics.get('ig_username', username)

            # Look for Shannon's messages containing offer phrases
            for message in conversation_history:
                if message.get('type') == 'ai':  # Shannon's messages
                    message_text = message.get('text', '').lower()

                    # Check for any offer phrase
                    if any(phrase.lower() in message_text for phrase in offer_phrases):
                        offered_conversations.append({
                            'username': ig_username,
                            'offer_message': message.get('text', ''),
                            'timestamp': message.get('timestamp', ''),
                            'conversation_history': conversation_history
                        })
                        break  # Count once per user

        if not offered_conversations:
            st.info(f"No challenge offers found for {time_period}")
            return

        st.write(
            f"Found {len(offered_conversations)} conversations with challenge offers:")

        for conv in offered_conversations:
            with st.expander(f"🎁 {conv['username']} - Challenge Offered", expanded=False):
                st.write("**Offer Message:**")
                st.info(conv['offer_message'])

                st.write("**Full Conversation:**")
                display_conversation_history(conv['conversation_history'])

    except Exception as e:
        logger.error(
            f"Error displaying challenge offered conversations: {e}", exc_info=True)
        st.error("Error loading challenge offer conversations")


def display_challenge_accepted_conversations(analytics_data_dict, time_period):
    """Display conversations where challenges were accepted"""
    try:
        start_date, end_date = get_date_range(time_period)

        # Positive response phrases from prompts.py
        positive_responses = [
            "that sounds good",
            "i'm interested",
            "tell me more",
            "okay, i'd like to try that",
            "yes",
            "yeah",
            "sounds great",
            "keen",
            "interested"
        ]

        # Shannon's onboarding trigger phrase from prompts.py
        onboarding_trigger = "awesome, lets get you onboarded"

        conversations_data = analytics_data_dict.get('conversations', {})
        accepted_conversations = []

        for username, user_container in conversations_data.items():
            if not isinstance(user_container, dict) or 'metrics' not in user_container:
                continue

            metrics = user_container['metrics']
            if not isinstance(metrics, dict):
                continue

            # Check if user falls within date range
            if not is_user_in_date_range(user_container, start_date, end_date):
                continue

            conversation_history = metrics.get('conversation_history', [])
            ig_username = metrics.get('ig_username', username)

            # Look for acceptance pattern
            for i, message in enumerate(conversation_history):
                if message.get('type') == 'user':  # User's messages
                    message_text = message.get('text', '').lower()

                    # Check if user message contains positive response
                    if any(phrase.lower() in message_text for phrase in positive_responses):
                        # Look for Shannon's onboarding trigger in next few messages
                        for j in range(i+1, min(i+4, len(conversation_history))):
                            next_msg = conversation_history[j]
                            if (next_msg.get('type') == 'ai' and
                                    onboarding_trigger.lower() in next_msg.get('text', '').lower()):

                                accepted_conversations.append({
                                    'username': ig_username,
                                    'acceptance_message': message.get('text', ''),
                                    'onboarding_message': next_msg.get('text', ''),
                                    'timestamp': message.get('timestamp', ''),
                                    'conversation_history': conversation_history
                                })
                                break
                        break

        if not accepted_conversations:
            st.info(f"No challenge acceptances found for {time_period}")
            return

        st.write(
            f"Found {len(accepted_conversations)} conversations with challenge acceptance:")

        for conv in accepted_conversations:
            with st.expander(f"✅ {conv['username']} - Challenge Accepted", expanded=False):
                st.write("**User's Acceptance Message:**")
                st.success(conv['acceptance_message'])

                st.write("**Shannon's Onboarding Response:**")
                st.info(conv['onboarding_message'])

                st.write("**Full Conversation:**")
                display_conversation_history(conv['conversation_history'])

    except Exception as e:
        logger.error(
            f"Error displaying challenge accepted conversations: {e}", exc_info=True)
        st.error("Error loading challenge acceptance conversations")


def display_paying_client_conversations(analytics_data_dict, time_period):
    """Display conversations with paying clients"""
    try:
        start_date, end_date = get_date_range(time_period)

        conversations_data = analytics_data_dict.get('conversations', {})
        paying_conversations = []

        for username, user_container in conversations_data.items():
            if not isinstance(user_container, dict) or 'metrics' not in user_container:
                continue

            metrics = user_container['metrics']
            if not isinstance(metrics, dict):
                continue

            # Check if user falls within date range
            if not is_user_in_date_range(user_container, start_date, end_date):
                continue

            # Check if user is a paying client
            journey_stage = metrics.get('journey_stage', {})
            if isinstance(journey_stage, dict) and journey_stage.get('is_paying_client', False):
                conversation_history = metrics.get('conversation_history', [])
                ig_username = metrics.get('ig_username', username)

                paying_conversations.append({
                    'username': ig_username,
                    'current_stage': journey_stage.get('current_stage', 'Unknown'),
                    'conversation_history': conversation_history,
                    'first_name': metrics.get('first_name', ''),
                    'last_name': metrics.get('last_name', '')
                })

        if not paying_conversations:
            st.info(f"No paying clients found for {time_period}")
            return

        st.write(f"Found {len(paying_conversations)} paying clients:")

        for conv in paying_conversations:
            full_name = f"{conv['first_name']} {conv['last_name']}".strip()
            display_name = f"{conv['username']} ({full_name})" if full_name else conv['username']

            with st.expander(f"💰 {display_name} - Paying Client", expanded=False):
                st.write(f"**Current Stage:** {conv['current_stage']}")

                if conv['conversation_history']:
                    st.write("**Recent Conversation:**")
                    # Show last 10 messages for paying clients
                    recent_history = conv['conversation_history'][-10:]
                    display_conversation_history(recent_history)
                else:
                    st.info("No conversation history available")

    except Exception as e:
        logger.error(
            f"Error displaying paying client conversations: {e}", exc_info=True)
        st.error("Error loading paying client conversations")


def display_conversation_history(conversation_history):
    """Helper function to display conversation history in a formatted way"""
    if not conversation_history:
        st.info("No conversation history available")
        return

    # Create a container for the conversation
    with st.container():
        for message in conversation_history[-15:]:  # Show last 15 messages
            timestamp = message.get('timestamp', '')
            message_type = message.get('type', 'unknown')
            text = message.get('text', '')

            # Format timestamp
            try:
                from datetime import datetime
                if timestamp:
                    dt = datetime.fromisoformat(timestamp.split('+')[0])
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_time = 'Unknown time'
            except:
                formatted_time = timestamp

            # Display message based on type
            if message_type == 'user':
                st.write(f"👤 **User** ({formatted_time}): {text}")
            elif message_type == 'ai':
                st.write(f"🤖 **Shannon** ({formatted_time}): {text}")
            else:
                st.write(f"❓ **{message_type}** ({formatted_time}): {text}")
