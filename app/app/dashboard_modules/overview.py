import streamlit as st


def display_overview():
    """Display the overview page with global metrics"""
    # Global Metrics Header with icon
    st.header("📊 Global Metrics")

    # Create three columns for the metrics sections
    col1, col2, col3 = st.columns(3)

    # Conversation Stats
    with col1:
        st.subheader("Conversation Stats")
        st.metric("Total Conversations", "188")
        st.metric("Total Messages", "911")
        st.metric("User Messages", "491")
        st.metric("Bot Messages", "419")

    # Response Metrics
    with col2:
        st.subheader("Response Metrics")
        st.metric("Total Responses", "170")
        st.metric("Response Rate", "40.6%")

    # Engagement Overview
    with col3:
        st.subheader("Engagement Overview")
        st.metric("Total Messages", "911")
        st.metric("User Messages", "491")
        st.metric("Response Rate", "53.8%")

# Add these new tracking functions at the end of the file


def get_challenge_offered_count() -> int:
    """
    Count users who have been offered the 28-Day Challenge.
    Detects by:
    1. Conversation history containing challenge offer phrases
    2. Journey stage with trial_offer_made = True
    3. Onboarding trigger phrase in conversation
    """
    import sqlite3
    import json
    import logging

    logger = logging.getLogger(__name__)
    db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        offered_users = set()

        # Method 1: Check journey_stage for trial_offer_made
        cursor.execute(
            "SELECT ig_username, metrics_json FROM users WHERE metrics_json IS NOT NULL")
        users_data = cursor.fetchall()

        for ig_username, metrics_json in users_data:
            if metrics_json:
                try:
                    metrics = json.loads(metrics_json)
                    journey_stage = metrics.get('journey_stage', {})

                    # Check if trial offer was made
                    if journey_stage.get('trial_offer_made') is True:
                        offered_users.add(ig_username)
                        continue

                except json.JSONDecodeError:
                    continue

        # Method 2: Check conversation history for challenge offer phrases
        challenge_phrases = [
            "28-Day Winter Challenge",
            "28-Day Winter Vegan Challenge",
            "free 28-Day",
            "Reckon you'd be interested?",
            "Awesome, lets get you onboarded, ill just need to grab some information off you if thats all g?"
        ]

        for phrase in challenge_phrases:
            cursor.execute("""
                SELECT DISTINCT ig_username 
                FROM conversation_history 
                WHERE message_type = 'ai' 
                AND message_text LIKE ?
            """, (f"%{phrase}%",))

            phrase_results = cursor.fetchall()
            for (username,) in phrase_results:
                offered_users.add(username)

        conn.close()
        return len(offered_users)

    except Exception as e:
        logger.error(f"Error counting challenge offers: {e}")
        return 0


def get_trial_started_count() -> int:
    """
    Count users who have started their trial period.
    Detects by:
    1. trial_start_date is set in journey_stage
    2. Any trial_week_X flags are True
    3. Current stage contains "Trial Week"
    """
    import sqlite3
    import json
    import logging

    logger = logging.getLogger(__name__)
    db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        trial_users = set()

        cursor.execute(
            "SELECT ig_username, metrics_json FROM users WHERE metrics_json IS NOT NULL")
        users_data = cursor.fetchall()

        for ig_username, metrics_json in users_data:
            if metrics_json:
                try:
                    metrics = json.loads(metrics_json)
                    journey_stage = metrics.get('journey_stage', {})

                    # Check for trial_start_date
                    if journey_stage.get('trial_start_date'):
                        trial_users.add(ig_username)
                        continue

                    # Check for trial week flags
                    trial_week_flags = [
                        'trial_week_1', 'trial_week_2', 'trial_week_3', 'trial_week_4'
                    ]

                    for flag in trial_week_flags:
                        if metrics.get(flag) is True:
                            trial_users.add(ig_username)
                            break

                    # Check current stage
                    current_stage = journey_stage.get('current_stage', '')
                    if 'Trial Week' in current_stage:
                        trial_users.add(ig_username)

                except json.JSONDecodeError:
                    continue

        conn.close()
        return len(trial_users)

    except Exception as e:
        logger.error(f"Error counting trial starts: {e}")
        return 0


def get_signed_up_count() -> int:
    """
    Count users who have completed the signup/onboarding process.
    Detects by:
    1. Users who have trial_start_date set (completed onboarding)
    2. Users who have completed the onboarding information sequence
    3. Users with sufficient profile information filled out
    """
    import sqlite3
    import json
    import logging

    logger = logging.getLogger(__name__)
    db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        signed_up_users = set()

        cursor.execute(
            "SELECT ig_username, metrics_json FROM users WHERE metrics_json IS NOT NULL")
        users_data = cursor.fetchall()

        for ig_username, metrics_json in users_data:
            if metrics_json:
                try:
                    metrics = json.loads(metrics_json)
                    journey_stage = metrics.get('journey_stage', {})

                    # Primary indicator: has trial_start_date (means they completed onboarding)
                    if journey_stage.get('trial_start_date'):
                        signed_up_users.add(ig_username)
                        continue

                    # Secondary indicator: has completed onboarding info
                    # Check for key onboarding fields
                    required_fields = ['email', 'first_name',
                                       'last_name', 'phone_number']
                    completed_fields = 0

                    for field in required_fields:
                        if metrics.get(field):
                            completed_fields += 1

                    # If they have most required fields, consider them signed up
                    if completed_fields >= 3:  # At least 3 out of 4 fields
                        signed_up_users.add(ig_username)
                        continue

                    # Tertiary indicator: paying client (definitely signed up)
                    if journey_stage.get('is_paying_client') is True:
                        signed_up_users.add(ig_username)

                except json.JSONDecodeError:
                    continue

        conn.close()
        return len(signed_up_users)

    except Exception as e:
        logger.error(f"Error counting signups: {e}")
        return 0


def get_conversion_stats() -> dict:
    """
    Get all three conversion statistics in one function call.
    Returns dict with challenge_offered, trial_started, signed_up counts.
    """
    return {
        'challenge_offered': get_challenge_offered_count(),
        'trial_started': get_trial_started_count(),
        'signed_up': get_signed_up_count()
    }
