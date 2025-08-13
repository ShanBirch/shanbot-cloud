"""
User Management & Daily Report Module
Handles daily reports, bulk user updates, and user profile management
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
import json

# Configure logging
logger = logging.getLogger(__name__)


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
                ts = datetime.fromisoformat(
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
                ts = datetime.fromisoformat(
                    ts_str_raw.replace("Z", "+00:00"))
                ts_str_formatted = ts.strftime("%Y-%m-%d %H:%M UTC")
            except ValueError:
                ts_str_formatted = item.get("timestamp", "Invalid Date")
            # Use st.markdown for consistency, could use st.write too
            st.markdown(
                f"- **{item.get('client_name', 'Unknown')}** ({ts_str_formatted}): {item.get('task_description', 'No description')}")


def bulk_update_leads_journey_stage(data: dict) -> tuple[dict, int]:
    """
    Update journey stages for leads (pre-trial/non-paying) based on conversation analysis.
    Assumes 'data' contains 'conversations' loaded from SQLite.
    Saves changes per user to SQLite directly.
    """
    # Import locally to avoid circular dependencies
    from dashboard_sqlite_utils import save_metrics_to_sqlite
    from shared_utils import get_user_topics

    try:
        updated_count = 0
        conversations = data.get('conversations', {})
        logger.info(
            f"Starting bulk update for {len(conversations)} leads' journey stages.")
        current_time = datetime.now()

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
                            last_shannon_topic_msg_ts = datetime.fromisoformat(
                                last_shannon_topic_msg_ts_str.split('+')[0])

                            # Find user responses after Shannon mentioned the topic
                            user_responses_after_topic = [
                                msg for msg in conversation_history
                                if msg.get('type') == 'user' and
                                datetime.fromisoformat(
                                    msg.get('timestamp', '').split('+')[0]) > last_shannon_topic_msg_ts
                            ]

                            if user_responses_after_topic:
                                last_user_response_ts_str = user_responses_after_topic[-1].get(
                                    'timestamp')
                                last_user_response_ts = datetime.fromisoformat(
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
                            last_shannon_trial_offer_ts = datetime.fromisoformat(
                                last_shannon_trial_offer_ts_str.split('+')[0])
                            user_responses_after_trial_offer = [
                                msg for msg in conversation_history
                                if msg.get('type') == 'user' and
                                datetime.fromisoformat(
                                    msg.get('timestamp', '').split('+')[0]) > last_shannon_trial_offer_ts
                            ]
                            if user_responses_after_trial_offer:
                                last_user_response_trial_ts_str = user_responses_after_trial_offer[-1].get(
                                    'timestamp')
                                last_user_response_trial_ts = datetime.fromisoformat(
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
    # Import locally to avoid circular dependencies
    from dashboard_sqlite_utils import save_metrics_to_sqlite
    from scheduled_followups import get_user_sheet_details as get_checkin_data

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
                    metrics['last_updated'] = datetime.now().isoformat()
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

                        # NEW: Remove from fresh vegan auto mode (now paying client)
                        try:
                            from conversation_strategy import check_and_cleanup_vegan_eligibility
                            check_and_cleanup_vegan_eligibility(ig_username)
                        except ImportError:
                            logger.warning(
                                "Could not import vegan cleanup function")

                        # NEW: Clean up from ad flow if they were in it
                        try:
                            from paying_client_cleanup import cleanup_paying_client_from_ad_flow
                            cleanup_paying_client_from_ad_flow(ig_username)
                        except ImportError:
                            logger.warning(
                                "Could not import paying client cleanup function")

                    # Example column name
                    elif sheet_data.get('Trial Status') == 'Active':
                        trial_start_str = sheet_data.get(
                            'Trial Start Date')  # Example column name
                        if trial_start_str:
                            try:
                                logger.info(
                                    f"Setting trial dates for {ig_username} based on sheet.")
                                start_date = datetime.strptime(
                                    trial_start_str, '%Y-%m-%d')  # Adjust format if needed
                                journey_stage['trial_start_date'] = start_date.isoformat(
                                )
                                journey_stage['trial_end_date'] = (
                                    start_date + timedelta(days=28)).isoformat()
                                # Ensure not marked as paying if in trial
                                journey_stage['is_paying_client'] = False

                                # Calculate trial week
                                days_in_trial = (
                                    datetime.now() - start_date).days
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

                                # NEW: Remove from fresh vegan auto mode (now trial member)
                                try:
                                    from conversation_strategy import check_and_cleanup_vegan_eligibility
                                    check_and_cleanup_vegan_eligibility(
                                        ig_username)
                                except ImportError:
                                    logger.warning(
                                        "Could not import vegan cleanup function")

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
    """Display user profiles section."""
    # Import locally to avoid circular dependencies
    from user_profiles import display_user_profiles

    # Use the imported display_user_profiles function
    display_user_profiles(st.session_state.analytics_data)
