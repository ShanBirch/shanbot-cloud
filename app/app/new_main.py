import random
import threading
import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import re
from typing import Dict, Any
import numpy as np
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from conversation_analytics_integration import analytics
import sys
import subprocess
import logging

# Import utilities using absolute paths from the project root
from app.dashboard_utils import (
    ensure_timezone, parse_timestamp, is_user_active,
    should_follow_up, analyze_engagement_level, get_smart_follow_up_timing,
    generate_follow_up_message,
    get_retry_delay, call_gemini_with_retries,
    ACTIVE_WINDOW
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
    toggle_auto_followup,
    AUTO_FOLLOWUP_ENABLED
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
logger = logging.getLogger(__name__)

# Analytics file path (might move to config)
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
        "Auto Refresh", value=st.session_state.get('auto_refresh', False))
with col2:
    if st.session_state.auto_refresh:
        st.session_state.refresh_interval = st.number_input("Interval (s)",
                                                            min_value=10,
                                                            max_value=300,
                                                            value=st.session_state.get('refresh_interval', 60))

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
            if is_user_active(last_active_timestamp):  # Use utility function
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
                        active = is_user_active(
                            user_data.get("last_message_timestamp"))
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
            active = is_user_active(user_data.get("last_message_timestamp"))
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
        active = is_user_active(user_data.get("last_message_timestamp"))
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
    st.header("⏰ Scheduled Follow-ups")

    # Load scheduled follow-ups
    try:
        scheduled_followups = load_scheduled_followups()
    except Exception as e:
        st.error(f"Error loading scheduled follow-ups: {e}")
        scheduled_followups = {}

    # Display controls and status
    st.write("This page allows you to view and manage scheduled follow-up messages.")

    auto_followup_status = "Enabled" if AUTO_FOLLOWUP_ENABLED else "Disabled"
    st.info(f"Automatic follow-ups are currently **{auto_followup_status}**.")

    # Display scheduled follow-ups
    if not scheduled_followups:
        st.warning("No scheduled follow-ups found.")
    else:
        st.success(f"Found {len(scheduled_followups)} scheduled follow-ups.")

        # Sort follow-ups by scheduled time
        sorted_followups = sorted(
            scheduled_followups.items(),
            key=lambda x: x[1].get('scheduled_time', '2099-01-01')
        )

        for user_id, followup_data in sorted_followups:
            username = followup_data.get('username', user_id)
            scheduled_time = followup_data.get('scheduled_time', 'Unknown')
            message = followup_data.get(
                'message', 'No message content available')

            # Format the scheduled time
            try:
                dt = datetime.fromisoformat(
                    scheduled_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_time = scheduled_time

            # Create an expander for each follow-up
            with st.expander(f"{username} - Due: {formatted_time}"):
                st.text_area("Message", message, height=100, disabled=True)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("View Profile", key=f"view_profile_{user_id}"):
                        st.session_state.view_profile = user_id
                        st.rerun()
                with col2:
                    if st.button("Delete Follow-up", key=f"delete_{user_id}"):
                        # Remove from scheduled follow-ups
                        if user_id in scheduled_followups:
                            del scheduled_followups[user_id]
                            try:
                                save_scheduled_followups(scheduled_followups)
                                st.success(f"Deleted follow-up for {username}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting follow-up: {e}")

    # Add button to process all scheduled follow-ups
    if st.button("Process All Scheduled Follow-ups"):
        with st.spinner("Processing scheduled follow-ups..."):
            try:
                result = process_scheduled_followups()
                if result:
                    st.success(
                        f"Processing complete. Sent: {result.get('sent', 0)}, Failed: {result.get('failed', 0)}")
                else:
                    st.error("Error processing follow-ups")
                st.rerun()
            except Exception as e:
                st.error(f"Error processing follow-ups: {e}")

    # Add a separator
    st.markdown("---")

    # Add button to create a test follow-up
    st.subheader("Create Test Follow-up")
    st.write("Create a test follow-up message for an existing user.")

    # Get list of user IDs
    user_ids = list(st.session_state.conversation_metrics.keys())

    if user_ids:
        # Sample a few users for the dropdown
        sample_size = min(10, len(user_ids))
        sample_user_ids = random.sample(user_ids, sample_size)

        # Create a format function to show username
        def format_user_option(user_id):
            user_data = st.session_state.conversation_metrics.get(user_id, {})
            username = user_data.get("ig_username", user_id)
            return f"{username} ({user_id})"

        # Create dropdown
        selected_user_id = st.selectbox(
            "Select User",
            options=sample_user_ids,
            format_func=format_user_option
        )

        # Get user data
        selected_user_data = st.session_state.conversation_metrics.get(
            selected_user_id, {})
        username = selected_user_data.get("ig_username", selected_user_id)

        # Input for hours to delay
        hours_delay = st.number_input(
            "Schedule in how many hours?", min_value=0.1, max_value=72.0, value=1.0, step=0.5)

        # Generate a test message or allow custom message
        use_custom_message = st.checkbox("Use custom message")

        if use_custom_message:
            message = st.text_area(
                "Custom Message", f"Hey {username}! This is a test follow-up message.")
        else:
            message = f"Hey {username}! This is an automatically generated test follow-up message created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."

        # Add button to create test follow-up
        if st.button("Create Test Follow-up"):
            # Calculate scheduled time
            scheduled_time = (datetime.now(timezone.utc) +
                              timedelta(hours=hours_delay)).isoformat()

            # Create follow-up data
            followup_data = {
                "username": username,
                "scheduled_time": scheduled_time,
                "message": message,
                "user_id": selected_user_id
            }

            try:
                # Add to scheduled follow-ups
                scheduled_followups[selected_user_id] = followup_data
                save_scheduled_followups(scheduled_followups)

                st.success(f"Test follow-up created for {username}!")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating follow-up: {e}")
    else:
        st.warning("No users found in analytics data.")

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

# --- Testing Tools ---
# Define the function it calls


def add_test_user():
    try:
        test_user_id = f"test_user_{random.randint(1000, 9999)}"
        test_username = f"TestUser{random.randint(100,999)}"
        analytics.add_conversation_metric(
            test_user_id, {"ig_username": test_username})
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

# --- Follow-up Management Sidebar ---
st.sidebar.header("Follow-up Management")

# Auto follow-up toggle
auto_followup_enabled = st.sidebar.checkbox(
    "Enable Automatic Follow-ups", value=True)
toggle_auto_followup(auto_followup_enabled)

# Button to process scheduled messages
if st.sidebar.button("Process Scheduled Messages"):
    with st.spinner("Processing..."):
        try:
            result = process_scheduled_followups()
            sent = result.get('sent', 0)
            failed = result.get('failed', 0)
            st.sidebar.success(
                f"Processing complete. Sent: {sent}, Failed: {failed}")
            logger.info(
                f"Processed scheduled follow-ups. Sent: {sent}, Failed: {failed}")
        except Exception as e:
            st.error(f"Failed to process scheduled follow-ups: {e}")
            logger.exception("Failed processing scheduled follow-ups.")

# Final separator
st.sidebar.markdown("---")
