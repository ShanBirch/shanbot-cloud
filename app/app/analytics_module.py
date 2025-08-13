import streamlit as st
import logging
import json
import time
from datetime import datetime, timedelta, timezone

# Assuming the conversation_analytics_integration module is accessible
from conversation_analytics_integration import analytics

# Import necessary utilities from dashboard_utils
from .dashboard_utils import (
    parse_timestamp,
    call_gemini_with_retries,
    BASE_RETRY_DELAY  # Used in run_conversation_analysis
)

# Import google.generativeai, needed for run_conversation_analysis
import google.generativeai as genai

# Set up logging for this module
logger = logging.getLogger(__name__)

# --- Analytics Data Loading ---


def load_analytics_data():
    """Loads analytics data using the conversation_analytics_integration module."""
    try:
        # Ensure the analytics object has the latest data
        analytics.load_analytics()
        # Return copies or manage state carefully if modifying these dicts elsewhere
        global_metrics = analytics.global_metrics.copy() if analytics.global_metrics else {}
        conversation_metrics = analytics.conversation_metrics.copy(
        ) if analytics.conversation_metrics else {}
        logger.info(
            f"Loaded analytics data: {len(global_metrics)} global keys, {len(conversation_metrics)} conversations.")
        return global_metrics, conversation_metrics
    except Exception as e:
        st.error(f"Error loading analytics data: {e}")
        logger.exception("Failed to load analytics data.")
        return {}, {}

# --- User Categorization ---


def get_responder_category(user_data):
    """Categorizes a user based on their message count."""
    # This function was originally in analytics_dashboard.py
    # Ensure user_data is the dictionary for a single user
    user_message_count = user_data.get("user_messages", 0)
    if user_message_count >= 51:
        return "High"
    elif user_message_count >= 11:  # 11 to 50
        return "Medium"
    elif user_message_count >= 1:  # 1 to 10
        return "Low"
    else:  # 0 messages
        return "No Responder"

# --- Conversation Analysis ---


def run_conversation_analysis(conversation_metrics):
    """Analyzes inactive conversations older than a threshold using Gemini."""
    # This function was originally in analytics_dashboard.py
    # Takes conversation_metrics dict as input, returns count of analyzed conversations

    ANALYSIS_INACTIVITY_THRESHOLD = timedelta(hours=48)
    now = datetime.now(timezone.utc)
    conversations_to_analyze = []
    updated_metrics = conversation_metrics.copy()  # Work on a copy

    st.info("Identifying inactive conversations older than 48 hours...")

    # Identify conversations needing analysis
    for user_id, user_data in conversation_metrics.items():
        # Check if already analyzed (e.g., by checking for 'conversation_summary')
        # Check the fields populated by this analysis run
        if user_data.get("conversation_rating") is not None or user_data.get("conversation_summary") is not None:
            # logger.debug(f"Skipping already analyzed user {user_id}")
            continue

        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                last_active_dt = parse_timestamp(last_active_timestamp)
                if last_active_dt and (now - last_active_dt) > ANALYSIS_INACTIVITY_THRESHOLD:
                    conversations_to_analyze.append(user_id)
                    # logger.debug(f"User {user_id} marked for analysis (inactive since {last_active_dt}).")
                # else:
                    # logger.debug(f"User {user_id} not analyzed: Active recently or timestamp invalid.")
            except Exception as e:
                logger.warning(
                    f"Could not parse timestamp for analysis check on user {user_id}: {e}")
        # else:
             # logger.debug(f"User {user_id} not analyzed: No last_message_timestamp.")

    if not conversations_to_analyze:
        st.success("No new inactive conversations found needing analysis.")
        return 0, updated_metrics  # Return 0 analyzed and the original metrics

    st.info(
        f"Found {len(conversations_to_analyze)} conversations to analyze. Processing...")
    progress_bar = st.progress(0)
    analyzed_count = 0

    # Configure Gemini once (ensure API key is handled by call_gemini_with_retries)
    # try:
    #     genai.configure(api_key="YOUR_API_KEY") # Handled by utility
    # except Exception as e:
    #     st.error(f"Failed to configure Gemini API: {e}")
    #     return 0, conversation_metrics # Return original metrics on config failure

    # Process conversations in smaller batches to potentially avoid quota issues
    BATCH_SIZE = 3  # Process a few conversations at a time
    conversation_batches = [conversations_to_analyze[i:i + BATCH_SIZE]
                            for i in range(0, len(conversations_to_analyze), BATCH_SIZE)]

    total_conversations = len(conversations_to_analyze)
    processed_count = 0

    for batch_index, batch in enumerate(conversation_batches):
        st.info(
            f"Processing batch {batch_index+1}/{len(conversation_batches)} ({len(batch)} conversations)")

        # Optional delay between batches
        if batch_index > 0:
            batch_delay = BASE_RETRY_DELAY * 2  # Example: Longer delay between batches
            logger.info(
                f"Waiting {batch_delay} seconds before processing next batch...")
            time.sleep(batch_delay)

        # Process each conversation in the batch
        for user_id in batch:
            user_data = conversation_metrics.get(
                user_id, {})  # Get original data
            if not user_data:
                logger.warning(
                    f"User ID {user_id} not found in provided metrics for analysis. Skipping.")
                processed_count += 1  # Count as processed for progress bar
                continue

            try:
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
                    [f"{msg.get('type','unknown').capitalize()}: {msg.get('text','')}" for msg in history[-20:]])  # Limit history length for prompt
                profile_text = json.dumps(profile_bio, indent=2)
                metrics_text = json.dumps(key_metrics, indent=2)

                prompt = f"""
You are a conversation analyst reviewing interactions between a fitness coach (AI) and a potential client (User) on Instagram.
Analyze the provided conversation history, user profile, and key metrics.

**Conversation History (Last 20 messages):**
{history_text}

**User Profile Bio:**
{profile_text}

**Key Metrics:**
{metrics_text}

**Your Task:**
Provide a concise analysis of this conversation in two parts, separated by '***':
1.  **Rating:** Assign ONE category that best describes the conversation's outcome or potential: [Hot Lead, Warm Lead, Nurture, Signup, General Chat, Stalled, Inquiry Only]. Choose 'Nurture' if unsure but interaction was positive. Choose 'Stalled' if conversation died off without clear resolution. Choose 'General Chat' for non-goal-oriented talk.
2.  **Summary:** Briefly explain your rating (1-2 sentences), mentioning key interaction points or lack thereof.

**Example Output:**
Warm Lead***User showed interest in fitness goals and asked about programs, but didn't commit. Good potential for follow-up.

**Analysis:**
"""

                # Call Gemini with retries using our helper function
                logger.debug(
                    f"Calling Gemini for conversation analysis for user {user_id}")
                analysis_text = call_gemini_with_retries(
                    prompt=prompt,
                    purpose=f"conversation analysis for user {user_id}"
                )

                # If all attempts failed, set default values
                rating = "Analysis Failed"
                summary = "API call failed or quota exceeded."  # Default summary
                if analysis_text is not None:
                    # Parse rating and summary
                    if '***' in analysis_text:
                        parts = analysis_text.split('***', 1)
                        # Assign default if empty
                        rating = parts[0].strip() or "Analysis Error"
                        # Assign default if empty
                        summary = parts[1].strip(
                        ) or "Could not parse summary."
                        # Basic validation for rating categories
                        valid_ratings = ["Hot Lead", "Warm Lead", "Nurture",
                                         "Signup", "General Chat", "Stalled", "Inquiry Only"]
                        if rating not in valid_ratings:
                            logger.warning(
                                f"Invalid rating '{rating}' received for user {user_id}. Defaulting to Nurture.")
                            # Keep original rating info
                            summary = f"(Original Rating: {rating}) {summary}"
                            rating = "Nurture"
                    elif analysis_text:  # Use whole response as summary if split fails but text exists
                        logger.warning(
                            f"Could not parse rating/summary separator for user {user_id}. Using full response as summary.")
                        summary = analysis_text
                        rating = "Analysis Error"  # Mark rating as error if structure is wrong
                    else:  # Handle empty but not None response
                        logger.warning(
                            f"Empty analysis response received for user {user_id}.")
                        rating = "Analysis Error"
                        summary = "Empty analysis response received."
                else:
                    logger.error(
                        f"Gemini call returned None for user {user_id}. Setting status to Failed.")
                    # Keep rating = "Analysis Failed", summary already set

                # Store results in the copied dictionary
                updated_metrics[user_id]['conversation_rating'] = rating
                updated_metrics[user_id]['conversation_summary'] = summary
                logger.info(
                    f"Analyzed user {user_id}: Rating={rating}, Summary='{summary[:50]}...'")
                analyzed_count += 1

            except Exception as e:
                logger.exception(  # Log full traceback for unexpected errors
                    f"Error analyzing conversation for user {user_id}: {e}")
                # Update the copied dictionary with failure status
                if user_id in updated_metrics:
                    updated_metrics[user_id]['conversation_rating'] = "Analysis Failed"
                    updated_metrics[user_id][
                        'conversation_summary'] = f"Error during analysis: {e}"
                else:
                    logger.error(
                        f"User ID {user_id} not found in updated_metrics during exception handling.")

            # Update processed count and progress bar regardless of success/failure
            processed_count += 1
            progress_bar.progress(processed_count / total_conversations)

            # Optional small delay between individual API calls within a batch
            # if user_id != batch[-1]: # Don't delay after the last item in batch
            #     time.sleep(0.5) # Shorter delay within batch

    # Save updated analytics (this should happen outside this function, after getting the results)
    if analyzed_count > 0:
        # st.info("Saving analysis results...") # UI feedback should be in main app
        try:
            # This module should NOT directly save. Return the updated data.
            # analytics.export_analytics(updated_metrics) # Pass data to save func if needed
            st.success(  # UI feedback belongs in the main app script
                f"Analysis complete. Analyzed {analyzed_count} conversations.")
        except Exception as e:
            # UI feedback in main app
            st.error(f"Error during final reporting/saving step: {e}")
    else:
        # UI feedback in main app
        st.warning("No conversations were successfully analyzed in this run.")

    # Return the count and the updated metrics dictionary
    return analyzed_count, updated_metrics
