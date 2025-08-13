import random
import threading
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
# Keep direct import for analytics.export_analytics() if used directly
from conversation_analytics_integration import analytics
import sys
import subprocess
import logging  # <-- Add logging import


# Import utilities using absolute paths from the project root
from app.dashboard_utils import (
    ensure_timezone, parse_timestamp, is_user_active,
    should_follow_up, analyze_engagement_level, get_smart_follow_up_timing,
    generate_follow_up_message,  # Basic one
    get_retry_delay, call_gemini_with_retries,
    ACTIVE_WINDOW  # Import constant
)

# Import follow-up service functions using absolute paths
from app.followup_service import (
    generate_ai_follow_up_message,
    schedule_automatic_followup,
    process_scheduled_followups,
    save_scheduled_followups,
    load_scheduled_followups,
    log_followup_success,
    log_followup_failure,
    toggle_auto_followup
    # Need reference to AUTO_FOLLOWUP_ENABLED state from service?
    # AUTO_FOLLOWUP_ENABLED as followup_auto_enabled_state
)

# Import analytics functions using absolute paths
from app.analytics_module import (
    load_analytics_data,
    get_responder_category,
    run_conversation_analysis
)

# Import user profile display function using absolute paths
from app.user_profiles import display_conversation

# Import AI assistant display function using absolute paths
from app.ai_assistant import display_ai_assistant_page

# Set up logging for this specific module if needed, or use root logger
logger = logging.getLogger(__name__)  # <-- Initialize logger

# --- Testing Tools in Sidebar ---
# The "Analyze Inactive Conversations (48h+)" button is already present above.

# Analytics file path (might move to config)
# Use double backslashes
ANALYTICS_FILE_PATH = "C:\\Users\\Shannon\\analytics_data.json"

# --- Session State Initialization ---
if 'global_metrics' not in st.session_state:
    # Initialize with empty dicts temporarily, load_analytics_data will populate
    st.session_state.global_metrics = {}
    st.session_state.conversation_metrics = {}
    # Trigger initial data load
    try:
        st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
        logger.info("Initial analytics data loaded into session state.")
    except Exception as e:
        st.error(f"Failed to load initial analytics data: {e}")
        logger.exception("Failed initial analytics data load.")
        # Keep empty dicts so app doesn't crash immediately

if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60  # Default 60 seconds
if 'view_profile' not in st.session_state:
    st.session_state.view_profile = None
if 'followup_manager_loaded' not in st.session_state:
    # Track if selenium manager is loaded
    st.session_state.followup_manager_loaded = False

# --- Sidebar Controls ---
st.sidebar.title("Shanbot Analytics")

# Add refresh controls
col1, col2 = st.sidebar.columns(2)
with col1:
    st.session_state.auto_refresh = st.checkbox(
        "Auto Refresh", value=st.session_state.get('auto_refresh', False))  # Use .get for safety
with col2:
    if st.session_state.auto_refresh:
        st.session_state.refresh_interval = st.number_input("Interval (s)",
                                                            min_value=10,
                                                            max_value=300,
                                                            value=st.session_state.get('refresh_interval', 60))  # Use .get

# Add manual refresh button
if st.sidebar.button("🔄 Refresh Data"):
    try:
        st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
        st.success("Data refreshed successfully!")
        logger.info("Manual data refresh triggered.")
    except Exception as e:
        st.error(f"Failed to refresh data: {e}")
        logger.exception("Manual data refresh failed.")


# --- Sidebar Navigation ---
# Determine default page based on view_profile state
default_nav_index = 0  # Default to Overview
if st.session_state.get('view_profile'):  # Use .get for safety
    default_nav_index = 1  # Switch to User Profiles if a profile is selected

# Add "AI Data Assistant" to the list of pages
nav_options = ["Overview", "User Profiles", "Analysis Results",
               "Batch Follow-up", "Scheduled Follow-ups", "AI Data Assistant"]
selected_page = st.sidebar.radio(
    "Navigation",
    nav_options,
    index=default_nav_index,  # Set index based on whether a profile is being viewed
    key='navigation_radio'  # Add a key for stability
)

# If user manually selected User Profiles, clear any previous selection (optional logic)
# if selected_page == "User Profiles" and not st.session_state.view_profile:
#     pass # Or clear view_profile? Depends on desired flow.

# If user selects a page other than User Profiles, clear view_profile
if selected_page != "User Profiles" and st.session_state.view_profile is not None:
    st.session_state.view_profile = None
    # No rerun here, let the page render based on the new selection

# Show data loading status
st.sidebar.markdown("---")
st.sidebar.info(f"Analytics data loaded.")  # Simpler message

# --- Main Content Area ---
st.title(f"Shanbot Analytics - {selected_page}")  # Dynamic title

if selected_page == "Overview":
    st.header("📊 Global Metrics")
    if not st.session_state.conversation_metrics:
        st.warning(
            "Conversation metrics data is not available. Check data loading.")
    else:
        # Calculate user metrics
        total_users = len(st.session_state.conversation_metrics)

        # Calculate active/inactive users using last_message_timestamp
        now = datetime.now(timezone.utc)  # Use UTC for consistency
        active_users = 0
        inactive_users = 0

        for user_id, user_data in st.session_state.conversation_metrics.items():
            # Use last_message_timestamp as the indicator of recent activity
            last_active_timestamp = user_data.get("last_message_timestamp")
            if is_user_active(last_active_timestamp, now):  # Use utility function
                active_users += 1
            else:
                inactive_users += 1

        # Create three columns for metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("User Stats")
            st.metric("Total Users", total_users)
            st.metric("Active Users (1h)", active_users,
                      help=f"Users active within the last {ACTIVE_WINDOW // 3600} hours")
            st.metric("Inactive Users", inactive_users,
                      help=f"Users inactive for more than {ACTIVE_WINDOW // 3600} hours")

        with col2:
            st.subheader("Conversion Metrics")
            # Get total signups and inquiries
            total_signups = sum(1 for data in st.session_state.conversation_metrics.values(
            ) if data.get("signup_recorded", False))
            total_inquiries = sum(1 for data in st.session_state.conversation_metrics.values(
            ) if data.get("coaching_inquiry_count", 0) > 0)
            total_offers = sum(1 for data in st.session_state.conversation_metrics.values(
            ) if data.get("offer_mentioned_in_conv", False))

            st.metric("Total Memberships Sold", total_signups,
                      help="Number of users who have signed up for membership")
            st.metric("Coaching Inquiries", total_inquiries,
                      help="Number of users who have inquired about coaching")

            # --- Expander for Inquiring Users ---
            with st.expander(f"View {total_inquiries} Users Who Inquired"):
                inquiring_users_list = []
                for user_id, user_data in st.session_state.conversation_metrics.items():
                    if user_data.get('coaching_inquiry_count', 0) > 0:
                        username = user_data.get("ig_username") or user_id
                        active = is_user_active(user_data.get(
                            "last_message_timestamp"), now)
                        status_indicator = "🟢" if active else "🔴"
                        inquiring_users_list.append({
                            "id": user_id,
                            "username": username,
                            "status_indicator": status_indicator
                        })

                inquiring_users_list.sort(key=lambda x: x["username"])

                if inquiring_users_list:
                    for user in inquiring_users_list:
                        cols_exp = st.columns([3, 1])
                        with cols_exp[0]:
                            st.write(
                                f"{user['status_indicator']} {user['username']}")
                        with cols_exp[1]:
                            if st.button("View Profile", key=f"view_inquiry_{user['id']}", use_container_width=True):
                                st.session_state.view_profile = user['id']
                                st.rerun()
                else:
                    st.info("No users found who have made inquiries.")

            conversion_rate = (total_signups / total_offers *
                               100) if total_offers > 0 else 0
            st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                      help="Percentage of users who signed up after seeing an offer")

        with col3:
            st.subheader("Engagement Overview")
            global_total = st.session_state.global_metrics.get(
                "total_messages", 0)
            global_user = st.session_state.global_metrics.get(
                "total_user_messages", 0)
            global_ai = st.session_state.global_metrics.get(
                "total_ai_messages", 0)
            response_rate = (global_ai / global_user *
                             100) if global_user > 0 else 0

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
        responder_tabs = st.tabs(
            ["High Responders", "Medium Responders", "Low Responders"])
        high_responders, medium_responders, low_responders = [], [], []

        for user_id, user_data in st.session_state.conversation_metrics.items():
            username = user_data.get("ig_username") or user_id
            active = is_user_active(user_data.get(
                "last_message_timestamp"), now)
            status_indicator = "🟢" if active else "🔴"
            total_message_count = user_data.get("total_messages", 0)
            user_message_count = user_data.get("user_messages", 0)

            user_info = {
                "id": user_id, "username": username,
                "total_message_count": total_message_count,
                "user_message_count": user_message_count,
                "is_active": active, "status_indicator": status_indicator
            }
            category = get_responder_category(
                user_data)  # Use imported function
            if category == "High":
                high_responders.append(user_info)
            elif category == "Medium":
                medium_responders.append(user_info)
            elif category == "Low":
                low_responders.append(user_info)

        for responder_list in [high_responders, medium_responders, low_responders]:
            responder_list.sort(key=lambda x: (
                x["is_active"], x["total_message_count"]), reverse=True)

        def display_responder_list(tab, users, category_key):
            with tab:
                st.subheader(
                    f"{category_key.replace('_',' ')} Responders ({len(users)})")
                if users:
                    selected_index = st.selectbox(
                        "Select User", options=list(range(len(users))),
                        format_func=lambda i: f"{users[i]['status_indicator']} {users[i]['username']} - {users[i]['user_message_count']} user msgs",
                        key=f"{category_key}_responder_select"
                    )
                    if st.button("View Profile", key=f"view_{category_key}_button"):
                        st.session_state.view_profile = users[selected_index]['id']
                        st.rerun()
                else:
                    st.info(
                        f"No {category_key.lower().replace('_',' ')} responders found")

        display_responder_list(responder_tabs[0], high_responders, "High")
        display_responder_list(responder_tabs[1], medium_responders, "Medium")
        display_responder_list(responder_tabs[2], low_responders, "Low")

        # Add Lead Analysis Dashboard
        st.header("🎯 Lead & Topic Analysis")
        # (Simplified Lead/Topic analysis section - can be expanded later if needed)
        lead_counts = defaultdict(int)
        needs_response_count = 0
        needs_response_users = []

        for user_id, user_data in st.session_state.conversation_metrics.items():
            rating = user_data.get("conversation_rating", "Not Analyzed")
            lead_counts[rating] += 1
            history = user_data.get("conversation_history", [])
            if history and history[-1].get("type") != "ai":
                needs_response_count += 1
                username = user_data.get("ig_username", user_id)
                needs_response_users.append(
                    {"id": user_id, "username": username})

        lead_tabs = st.tabs(["Lead Categories", "Messages Needing Response"])
        with lead_tabs[0]:
            st.subheader("Lead Category Distribution")
            # Display simple counts for now
            for category, count in sorted(lead_counts.items()):
                if count > 0:
                    st.write(f"{category}: {count}")
            # Add expander for priority leads
            priority_leads = [
                {"id": uid, "username": ud.get(
                    "ig_username", uid), "rating": ud.get("conversation_rating")}
                for uid, ud in st.session_state.conversation_metrics.items()
                if ud.get("conversation_rating") in ["Hot Lead", "Warm Lead"]
            ]
            if priority_leads:
                with st.expander("View Priority Leads"):
                    for lead in priority_leads:
                        if st.button(f"View {lead['username']} ({lead['rating']})", key=f"view_prio_{lead['id']}"):
                            st.session_state.view_profile = lead['id']
                            st.rerun()

        with lead_tabs[1]:
            st.subheader(f"Messages Needing Response ({needs_response_count})")
            if needs_response_count == 0:
                st.success("All messages have been responded to!")
            else:
                st.info(
                    f"{needs_response_count} conversations have unresponded user messages.")
                for user in needs_response_users:
                    if st.button(f"Respond to {user['username']}", key=f"respond_{user['id']}"):
                        st.session_state.view_profile = user['id']
                        st.rerun()

elif selected_page == "User Profiles":
    st.header("👥 User Profiles")
    selected_user_id = st.session_state.view_profile
    user_list = []
    now = datetime.now(timezone.utc)

    # Create sorted user list for dropdown
    for user_id, user_data in st.session_state.conversation_metrics.items():
        username = user_data.get("ig_username") or user_id
        active = is_user_active(user_data.get("last_message_timestamp"), now)
        status_indicator = "🟢" if active else "🔴"
        message_count = user_data.get("total_messages", 0)
        user_list.append({
            "id": user_id, "username": username, "message_count": message_count,
            "is_active": active, "status_indicator": status_indicator
        })
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

    selected_user = None
    if selected_user_id:
        # Find the full user object if an ID is selected
        selected_user = next(
            (user for user in user_list if user["id"] == selected_user_id), None)
        if selected_user:
            st.info(
                f"Viewing profile for: {selected_user['status_indicator']} {selected_user['username']}")
            if st.button("← Back to User List"):
                st.session_state.view_profile = None
                st.rerun()
        else:
            # If ID is invalid (shouldn't happen), clear it
            st.session_state.view_profile = None
            st.warning("Selected user profile not found. Displaying list.")

    if not selected_user:  # Show dropdown if no valid user is selected via ID
        selected_user_from_dropdown = st.selectbox(
            "Select User", options=user_list,
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages",
            key='user_profile_select'  # Add key
        )
        # We use the selected object directly if chosen from dropdown
        selected_user = selected_user_from_dropdown

    # Display conversation if a user is selected (either via ID or dropdown)
    if selected_user:
        display_conversation(selected_user)  # Call imported function
    # Only show if not attempting to view a specific (but invalid) profile
    elif not selected_user_id:
        st.info("Select a user from the dropdown to view their profile.")


elif selected_page == "Analysis Results":
    st.header("🔍 Conversation Analysis Results")
    st.info("This page shows all conversations that have been analyzed.")
    analyzed_conversations = []
    for user_id, user_data in st.session_state.conversation_metrics.items():
        if "conversation_rating" in user_data:
            username = user_data.get("ig_username") or user_id
            analyzed_conversations.append({
                "id": user_id, "username": username,
                "rating": user_data.get("conversation_rating", "Not Analyzed"),
                "summary": user_data.get("conversation_summary", "No summary available"),
                "user_messages": user_data.get("user_messages", 0)
            })

    if not analyzed_conversations:
        st.warning(
            "No analyzed conversations found. Run analysis from the sidebar.")
    else:
        # Add filtering/sorting (simplified)
        ratings = sorted(list(set(conv["rating"]
                         for conv in analyzed_conversations)))
        selected_ratings = st.multiselect("Filter by Rating:", options=[
                                          "All"] + ratings, default=["All"])

        filtered_convs = analyzed_conversations
        if selected_ratings and "All" not in selected_ratings:
            filtered_convs = [
                conv for conv in analyzed_conversations if conv["rating"] in selected_ratings]

        sort_key = st.selectbox(
            "Sort by:", ["Username (A-Z)", "Rating", "Message Count (High-Low)"])

        if sort_key == "Username (A-Z)":
            filtered_convs.sort(key=lambda x: x["username"])
        elif sort_key == "Rating":
            filtered_convs.sort(key=lambda x: x["rating"])
        else:
            filtered_convs.sort(key=lambda x: -x["user_messages"])

        st.write(f"Showing {len(filtered_convs)} analyzed conversations")
        for i, conv in enumerate(filtered_convs):
            # Expand first 5
            with st.expander(f"{conv['username']} - {conv['rating']}", expanded=i < 5):
                st.write(f"**Summary:** {conv['summary']}")
                st.metric("Messages", conv["user_messages"])
                if st.button("View Profile", key=f"view_analysis_{conv['id']}"):
                    st.session_state.view_profile = conv['id']
                    st.rerun()

elif selected_page == "Batch Follow-up":
    st.header("✉️ Batch Follow-up (Placeholder)")
    st.warning(
        "Batch Follow-up functionality is not yet fully implemented in this refactored version.")
    # Placeholder logic - maybe load followup_manager here if needed
    # if not st.session_state.followup_manager_loaded:
    #     if load_followup_manager(): # Define this function if needed
    #         st.session_state.followup_manager_loaded = True
    #     else:
    #         st.error("Failed to load the follow-up manager required for this page.")


elif selected_page == "Scheduled Follow-ups":
    st.header("⏰ Scheduled Follow-ups (Placeholder)")
    st.warning(
        "Scheduled Follow-ups functionality is not yet fully implemented in this refactored version.")
    # Display loaded scheduled followups (if available)
    # scheduled = load_scheduled_followups() # Assumes function exists
    # st.write(scheduled)
    # Add button to process?


elif selected_page == "AI Data Assistant":
    # Call the imported function to display this page
    display_ai_assistant_page()

# --- Footer ---
st.markdown("---")
st.markdown(
    f"Analytics Dashboard | Reading from: {os.path.abspath(ANALYTICS_FILE_PATH)}")
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# --- Auto-refresh Logic ---
# Check if auto-refresh is enabled and we're not already in a refresh cycle
if st.session_state.get('auto_refresh', False) and not st.session_state.get('_refreshing', False):
    st.session_state._refreshing = True  # Mark that we are starting a refresh cycle
    interval = st.session_state.get('refresh_interval', 60)
    time.sleep(interval)
    st.session_state._refreshing = False  # Mark that the sleep is over
    st.rerun()  # Trigger the rerun
# Ensure _refreshing is False if auto_refresh is off
elif not st.session_state.get('auto_refresh', False):
    st.session_state._refreshing = False


# --- Testing Tools (Button defined earlier) ---
# Define the function it calls
def add_test_user():
    try:
        test_user_id = f"test_user_{random.randint(1000, 9999)}"
        test_username = f"TestUser{random.randint(100,999)}"
        analytics.add_conversation_metric(
            test_user_id, {"ig_username": test_username})  # Use analytics object method
        analytics.add_message(test_user_id, "user", "This is a test message.")
        analytics.add_message(test_user_id, "ai", "This is a test response.")
        analytics.update_conversation_metric(
            test_user_id, "last_message_timestamp", datetime.now(timezone.utc).isoformat())
        analytics.export_analytics()  # Save changes
        logger.info(f"Added test user: {test_user_id} ({test_username})")
        return "Test user added successfully!"
    except Exception as e:
        logger.exception(f"Failed to add test user.")
        st.error(f"Failed to add test user: {e}")
        return None


st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    if result:
        st.sidebar.success(result)
        # Refresh the data using imported function
        try:
            st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
            logger.info("Refreshed data after adding test user.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to refresh data after adding test user: {e}")
            logger.exception("Failed data refresh after test user add.")


# --- Follow-up Management Sidebar (Defined Separately) ---
# The "Analyze Inactive Conversations" button is already added near the top of the sidebar section.
st.sidebar.header("Follow-up Management")

# Auto follow-up toggle (simplified - assumes followup_service manages state)
auto_followup_enabled = st.sidebar.checkbox(
    "Enable Automatic Follow-ups", value=True)  # Placeholder default
toggle_auto_followup(auto_followup_enabled)  # Call function from service

# Display scheduled count (placeholder)
# scheduled_count = len(load_scheduled_followups()) # Assumes function exists
# st.sidebar.text(f"Scheduled follow-ups: {scheduled_count}")

# Button to process scheduled messages
if st.sidebar.button("Process Scheduled Messages"):
    with st.spinner("Processing..."):
        try:
            result = process_scheduled_followups()  # Assumes function exists
            sent = result.get('sent', 0)
            failed = result.get('failed', 0)
            st.sidebar.success(
                f"Processing complete. Sent: {sent}, Failed: {failed}")
            logger.info(
                f"Processed scheduled follow-ups. Sent: {sent}, Failed: {failed}")
            # Consider refreshing data if processing affects metrics
            # st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
            # st.rerun()
        except Exception as e:
            st.error(f"Failed to process scheduled follow-ups: {e}")
            logger.exception("Failed processing scheduled follow-ups.")

# Final separator
st.sidebar.markdown("---")

# --- End of Regenerated Code ---
