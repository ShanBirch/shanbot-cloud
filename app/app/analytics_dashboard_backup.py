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
from conversation_analytics_integration import analytics
import sys
import subprocess
import logging  # <-- Add logging import

# Set up logging for this specific module if needed, or use root logger
logger = logging.getLogger(__name__)  # <-- Initialize logger

# Set up path to find followup_manager
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Now try to import followup_manager - do this conditionally to avoid errors when just viewing analytics
followup_manager = None

# Global variables for automatic follow-up
AUTO_FOLLOWUP_ENABLED = True
SCHEDULED_FOLLOWUPS = {}

# Moving display_conversation function here before it's called


def display_conversation(selected_user):
    """Display a single conversation with a user"""
    user_data = st.session_state.conversation_metrics[selected_user["id"]]
    conversation_id = selected_user["id"]

    # Always show user profile section, even if data is missing
    with st.expander("🧑‍💼 User Profile", expanded=True):
        # Check if we have profile bio data
        has_profile_bio = "client_analysis" in user_data and "profile_bio" in user_data.get(
            "client_analysis", {})

        if has_profile_bio:
            profile_bio = user_data["client_analysis"]["profile_bio"]
            col1, col2 = st.columns([1, 2])

            with col1:
                # Display name and basic info
                name = profile_bio.get(
                    "PERSON NAME") or profile_bio.get("person_name") or user_data.get("ig_username", "Unknown")
                st.subheader(f"{name}")
                st.caption(f"@{user_data.get('ig_username', conversation_id)}")

                # Display personality traits if available
                if "PERSONALITY TRAITS" in profile_bio and profile_bio["PERSONALITY TRAITS"]:
                    st.write("**Personality:**")
                    traits_html = " • ".join(
                        [f"<span style='background-color: #f0f7ff; padding: 2px 6px; border-radius: 10px; margin: 2px; display: inline-block;'>{trait}</span>" for trait in profile_bio["PERSONALITY TRAITS"] if trait])
                    st.markdown(traits_html, unsafe_allow_html=True)

            with col2:
                # Display interests in a more visual way
                if "INTERESTS" in profile_bio and profile_bio["INTERESTS"]:
                    st.write("**Interests:**")
                    interests_html = " ".join(
                        [f"<span style='background-color: #e6f3ff; padding: 3px 8px; border-radius: 12px; margin: 3px; display: inline-block;'>{interest}</span>" for interest in profile_bio["INTERESTS"] if interest])
                    st.markdown(interests_html, unsafe_allow_html=True)

                # Display lifestyle summary
                if "LIFESTYLE" in profile_bio and profile_bio["LIFESTYLE"] not in ["Unknown", ""]:
                    st.write("**Lifestyle:**")
                    st.write(profile_bio["LIFESTYLE"])

            # Display conversation starters in a separate expander if available
            if "conversation_starters" in profile_bio and profile_bio["conversation_starters"]:
                # Convert to container instead of expander to avoid nesting
                st.write("💬 **Conversation Starters:**")
                for i, starter in enumerate(profile_bio["conversation_starters"]):
                    if starter and starter not in ["Unknown", ""]:
                        st.markdown(f"- {starter}")
        else:
            # No profile bio available - show placeholder with username only
            st.subheader(f"{user_data.get('ig_username', 'Unknown User')}")
            st.caption(f"@{user_data.get('ig_username', conversation_id)}")
            st.info("No detailed profile information available yet. This data will be populated when followersbot2.py analyzes the user's Instagram profile.")

    # Move the "How to get profile data" outside the expander to avoid nesting
    if not has_profile_bio:
        with st.expander("ℹ️ How to get profile data"):
            st.write(
                "Profile data is generated when followersbot2.py analyzes the user's Instagram posts. To get this data:")
            st.write(
                "1. Make sure the user is included in your instagram_followers.txt file")
            st.write("2. Run followersbot2.py to analyze their profile")
            st.write(
                "3. The next time you view this conversation, profile data will be available")

    # Create three columns for user metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Info")
        st.write(f"**Username:** {user_data.get('ig_username', 'N/A')}")
        st.write(f"**User ID:** {selected_user['id']}")
        st.write(
            f"**First Seen:** {user_data.get('conversation_start_time', 'N/A')}")

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

        # Show user status and last active time using last_message_timestamp
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                last_active_dt = parse_timestamp(last_active_timestamp)

                if last_active_dt:
                    now = datetime.now(timezone.utc)
                    time_diff = now - last_active_dt
                    minutes_ago = time_diff.total_seconds() / 60

                    is_active = time_diff.total_seconds() < ACTIVE_WINDOW
                    status = "🟢 Active" if is_active else "🔴 Inactive"

                    st.write(f"**Status:** {status}")
                    st.write(
                        f"**Last Active:** {minutes_ago:.1f} minutes ago")
                else:
                    st.write(f"**Status:** 🔴 Inactive")
                    st.write("**Last Active:** Invalid timestamp")
            except Exception as e:
                st.error(
                    f"Error parsing timestamp for user {selected_user['id']}: {e}")
                st.write(f"**Status:** 🔴 Inactive")
                st.write(f"**Last Active:** Error parsing timestamp")
        else:
            st.write(f"**Status:** 🔴 Inactive")
            st.write("**Last Active:** Never")

    with col2:
        st.subheader("Engagement Metrics")
        total_msgs = user_data.get("total_messages", 0)
        user_msgs = user_data.get("user_messages", 0)
        ai_msgs = user_data.get("ai_messages", 0)

        st.metric("Total Messages", total_msgs)
        st.metric("User Messages", user_msgs)
        st.metric("AI Messages", ai_msgs)

        # Calculate response rate
        if user_msgs > 0:
            response_rate = (ai_msgs / user_msgs) * 100
            st.metric("Response Rate", f"{response_rate:.1f}%")

    with col3:
        st.subheader("Conversion Info")
        st.write(
            f"**Coaching Inquiries:** {user_data.get('coaching_inquiry_count', 0)}")
        st.write(
            f"**Offer Shown:** {'Yes' if user_data.get('offer_mentioned_in_conv', False) else 'No'}")
        st.write(
            f"**Signed Up:** {'Yes' if user_data.get('signup_recorded', False) else 'No'}")

        # Show topics mentioned
        st.write("**Topics Mentioned:**")
        topics = []
        if user_data.get("vegan_topic_mentioned", False):
            topics.append("Vegan")
        if user_data.get("weight_loss_mentioned", False):
            topics.append("Weight Loss")
        if user_data.get("muscle_gain_mentioned", False):
            topics.append("Muscle Gain")
        st.write(", ".join(topics) if topics else "None")

        # --- Display Conversation Analysis/Rating --- START ---
        conversation_rating = user_data.get("conversation_rating")
        conversation_summary = user_data.get("conversation_summary")

        if conversation_rating or conversation_summary:
            st.markdown("### AI Conversation Analysis")
            if conversation_rating and conversation_rating not in ["Analysis Error", "Analysis Failed"]:
                # Simple color coding for ratings (customize as needed)
                color_map = {
                    "Hot Lead": "#ff4d4d",  # Red
                    "Warm Lead": "#ffa500",  # Orange
                    "Signup": "#28a745",  # Green
                    "Inquiry Only": "#ffc107",  # Amber
                    "Nurture": "#17a2b8",  # Teal
                    "General Chat": "#6c757d",  # Grey
                    "Stalled": "#dc3545",  # Darker Red
                }
                rating_color = color_map.get(
                    conversation_rating, "#6c757d")  # Default to grey
                st.markdown(
                    f"**Rating:** <span style='color:white; background-color:{rating_color}; padding: 2px 8px; border-radius: 10px;'>{conversation_rating}</span>", unsafe_allow_html=True)
            elif conversation_rating:
                # Show error/failed ratings plainly
                st.markdown(f"**Rating:** {conversation_rating}")

            if conversation_summary:
                st.markdown("**Summary:**")
                st.info(conversation_summary)
        # --- Display Conversation Analysis/Rating --- END ---

    # Add follow-up management section before conversation history
    st.subheader("Follow-up Management")

    # Check actual conversation history first
    history = user_data.get("conversation_history", [])
    last_active_timestamp = user_data.get(
        "last_message_timestamp")  # Use the reliable timestamp
    needs_follow_up = False
    hours_inactive = 0
    follow_up_description = "Not yet determined"
    hours_until_followup = 0
    last_active_dt = None  # Initialize last_active_dt

    if last_active_timestamp:
        last_active_dt = parse_timestamp(last_active_timestamp)
        if last_active_dt:
            now = datetime.now(timezone.utc)
            time_diff = now - last_active_dt
            hours_inactive = time_diff.total_seconds() / 3600

            # Determine follow-up timing based on responder category
            # ... [existing logic for required_inactive_hours, etc.] ...
            message_count = user_data.get("user_messages", 0)
            if message_count >= 51:
                required_inactive_hours = 48
                follow_up_description = "48 hours (High Responder)"
                days_between_followups = 7
            elif message_count >= 11:
                required_inactive_hours = 120  # 5 days
                follow_up_description = "5 days (Medium Responder)"
                days_between_followups = 10
            else:
                required_inactive_hours = 168  # 7 days
                follow_up_description = "7 days (Low Responder)"
                days_between_followups = 14

            # Calculate when follow-up should be sent
            follow_up_time = last_active_dt + \
                timedelta(hours=required_inactive_hours)
            time_until_followup = follow_up_time - now
            hours_until_followup = time_until_followup.total_seconds() / 3600

            # Check if enough time has passed based on responder category
            if hours_inactive >= required_inactive_hours:
                # Check if already followed up in the last period
                last_follow_up = user_data.get("last_follow_up_date")
                if last_follow_up:
                    last_follow_up_dt = parse_timestamp(last_follow_up)
                    if last_follow_up_dt:
                        days_since_follow_up = (now - last_follow_up_dt).days
                        if days_since_follow_up >= days_between_followups:
                            needs_follow_up = True
                    else:
                        needs_follow_up = True  # Treat invalid last_follow_up as needing one
                else:
                    needs_follow_up = True

                # Auto-generate follow-up message when user first becomes eligible
                if needs_follow_up and "generated_follow_ups" not in st.session_state:
                    st.session_state.generated_follow_ups = {}

                if needs_follow_up and selected_user["id"] not in st.session_state.generated_follow_ups:
                    # Only generate if we don't already have a message for this user
                    try:
                        # Generate the message silently in the background
                        follow_up_message = generate_ai_follow_up_message(
                            user_data)

                        # Store in session state
                        st.session_state.generated_follow_ups[selected_user["id"]] = {
                            "message": follow_up_message,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "auto_generated": True
                        }
                        # No rerun - will display on next refresh
                    except Exception as e:
                        # Silent error handling - will try again next time
                        print(f"Error auto-generating follow-up: {e}")

    # Create columns for displaying follow-up content
    follow_up_cols = st.columns([2, 1])

    with follow_up_cols[0]:
        # Display status based on history and calculations
        if not history and not user_data.get("client_analysis", {}).get("generated_comment"):
            # Show warning only if truly no history AND no generated comment
            st.warning(
                "⚠️ No conversation history or initial comment recorded for this user.")
        elif last_active_dt is None and last_active_timestamp:
            # Handle case where timestamp exists but failed parsing
            st.warning("⚠️ Invalid timestamp data for last message.")
        elif hours_inactive < 1.0 and last_active_dt:
            st.success("✅ This user is currently active - no follow-up needed.")
        elif needs_follow_up:
            st.info(
                f"⏰ This user has been inactive for {hours_inactive:.1f} hours and is eligible for follow-up.")
            st.caption(f"Follow-up timing: {follow_up_description}")

            # Initialize session state for this user's follow-up message if needed
            if "generated_follow_ups" not in st.session_state:
                st.session_state.generated_follow_ups = {}

            # Display generated message if it exists
            if selected_user["id"] in st.session_state.generated_follow_ups:
                message = st.session_state.generated_follow_ups[selected_user["id"]]["message"]
                generated_at = st.session_state.generated_follow_ups[
                    selected_user["id"]]["generated_at"]
                is_auto = st.session_state.generated_follow_ups[selected_user["id"]].get(
                    "auto_generated", False)

                if is_auto:
                    st.success(
                        "Automatically generated follow-up message:")
                else:
                    st.success("Generated follow-up message:")

                st.info(message)
                st.caption(f"Generated: {generated_at}")

                # Add text area for editing the message
                edited_message = st.text_area(
                    "Edit message before sending:",
                    value=message,
                    height=100,
                    key=f"edit_message_{selected_user['id']}"
                )

                # Update the message in session state if edited
                if edited_message != message:
                    st.session_state.generated_follow_ups[selected_user["id"]
                                                          ]["message"] = edited_message
                    st.session_state.generated_follow_ups[selected_user["id"]
                                                          ]["edited"] = True
                    st.session_state.generated_follow_ups[selected_user["id"]
                                                          ]["auto_generated"] = False

            # Generate or regenerate button
            generate_button_text = "Regenerate Message" if selected_user[
                "id"] in st.session_state.generated_follow_ups else "Generate Follow-up Message"
            if st.button(generate_button_text):
                with st.spinner("Generating follow-up message with Gemini..."):
                    try:
                        # Generate the message
                        follow_up_message = generate_ai_follow_up_message(
                            user_data)

                        # Store in session state
                        st.session_state.generated_follow_ups[selected_user["id"]] = {
                            "message": follow_up_message,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "auto_generated": False
                        }
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating message: {e}")
        else:
            # For users who don't need follow-up yet
            if hours_inactive < 1.0:
                st.success(
                    "✅ This user is currently active - no follow-up needed.")
            elif hours_until_followup > 0:
                time_display = f"{hours_until_followup:.1f} hours"
                if hours_until_followup > 24:
                    days_remaining = hours_until_followup / 24
                    time_display = f"{days_remaining:.1f} days"

                st.warning(
                    f"⌛ This user has been inactive for {hours_inactive:.1f} hours. Eligible for follow-up in {time_display}.")
                st.caption(f"Follow-up timing: {follow_up_description}")
            else:
                st.info(
                    f"⌛ This user has been inactive for {hours_inactive:.1f} hours but doesn't yet meet follow-up criteria.")

            # Allow pre-generating follow-up messages even if not yet eligible
            if hours_inactive > 48:  # Show for users inactive for at least 48 hours
                st.info(
                    "You can pre-generate a follow-up message that will be ready when the user becomes eligible.")

                # Initialize session state for this user's follow-up message if needed
                if "generated_follow_ups" not in st.session_state:
                    st.session_state.generated_follow_ups = {}

                # Display generated message if it exists
                if selected_user["id"] in st.session_state.generated_follow_ups:
                    message = st.session_state.generated_follow_ups[selected_user["id"]]["message"]
                    generated_at = st.session_state.generated_follow_ups[
                        selected_user["id"]]["generated_at"]

                    st.success("Pre-generated follow-up message:")
                    st.info(message)
                    st.caption(f"Generated: {generated_at}")

                    # Add text area for editing the message
                    edited_message = st.text_area(
                        "Edit message:",
                        value=message,
                        height=100,
                        key=f"edit_message_pre_{selected_user['id']}"
                    )

                    # Update the message in session state if edited
                    if edited_message != message:
                        st.session_state.generated_follow_ups[selected_user["id"]
                                                              ]["message"] = edited_message
                        st.session_state.generated_follow_ups[selected_user["id"]
                                                              ]["edited"] = True

                    # Add Send Message Now button to override timing rules
                    send_cols = st.columns(2)
                    with send_cols[0]:
                        if st.button("Send Message Now", key="send_now_button"):
                            username = user_data.get("ig_username")
                            current_message = st.session_state.generated_follow_ups[
                                selected_user["id"]]["message"]

                            if not username:
                                st.error(
                                    "No Instagram username found for this user")
                            else:
                                # Create a container for displaying process info - move outside any potential nesting
                                st.subheader("Message Sending Process")
                                debug_container = st.empty()
                                debug_container.info(
                                    "Starting message send process...")

                                # Debug info about username and message
                                debug_container.info(
                                    f"Sending to Instagram username: '{username}'")
                                debug_container.info(
                                    f"Message length: {len(current_message)} characters")
                                debug_container.info(
                                    f"Message preview: '{current_message[:30]}...'")

                                # Load followup_manager
                                load_followup_manager()
                                if followup_manager is None:
                                    st.error(
                                        "Could not load the follow-up manager module")
                                else:
                                    try:
                                        # Full one-click automated process
                                        with st.spinner(f"Sending message to {username}..."):
                                            # 1. Setup browser
                                            debug_container.info(
                                                "Setting up browser...")

                                            # Try to get an existing browser instance first
                                            try:
                                                driver = followup_manager.get_driver()
                                                if driver:
                                                    debug_container.success(
                                                        "Using existing browser instance!")
                                                else:
                                                    debug_container.info(
                                                        "No browser instance found, creating new one...")
                                                    driver = followup_manager.setup_driver()
                                            except Exception as e:
                                                debug_container.warning(
                                                    f"Error getting existing driver: {e}")
                                                debug_container.info(
                                                    "Creating new browser instance...")
                                                driver = followup_manager.setup_driver()

                                            if driver:
                                                debug_container.success(
                                                    "Browser setup complete!")

                                                # Check if already logged in
                                                is_logged_in = False
                                                try:
                                                    current_url = driver.current_url
                                                    if "instagram.com" in current_url and "accounts/login" not in current_url:
                                                        is_logged_in = True
                                                        debug_container.success(
                                                            "Already logged into Instagram!")
                                                except:
                                                    debug_container.info(
                                                        "Not logged in yet")

                                                # 2. Login to Instagram if needed
                                                if not is_logged_in:
                                                    debug_container.info(
                                                        "Logging into Instagram...")
                                                    login_success = followup_manager.login_to_instagram(
                                                        driver,
                                                        followup_manager.INSTAGRAM_USERNAME,
                                                        followup_manager.INSTAGRAM_PASSWORD
                                                    )

                                                    if login_success:
                                                        debug_container.success(
                                                            "Logged in successfully!")
                                                    else:
                                                        debug_container.error(
                                                            "Login failed - trying direct message anyway")

                                                # 3. Send the message
                                                debug_container.info(
                                                    f"Sending message to {username}...")
                                                result = followup_manager.send_follow_up_message(
                                                    driver, username, current_message
                                                )

                                                if result.get("success", False):
                                                    debug_container.success(
                                                        "Message sent successfully!")

                                                    # Update user data with follow-up info
                                                    was_edited = st.session_state.generated_follow_ups[selected_user["id"]].get(
                                                        "edited", False)

                                                    user_data["last_follow_up_date"] = datetime.now(
                                                        timezone.utc).isoformat()
                                                    user_data["follow_ups_sent"] = user_data.get(
                                                        "follow_ups_sent", 0) + 1

                                                    # Add to follow-up history
                                                    if "follow_up_history" not in user_data:
                                                        user_data["follow_up_history"] = [
                                                        ]

                                                    user_data["follow_up_history"].append({
                                                        "date": datetime.now(timezone.utc).isoformat(),
                                                        "message": current_message,
                                                        "edited": was_edited,
                                                        "sent_via_instagram": True,
                                                        "sent_early": True,
                                                        "engagement_level": analyze_engagement_level(user_data)["level"]
                                                    })

                                                    # Save the updated data
                                                    st.session_state.conversation_metrics[
                                                        selected_user["id"]] = user_data
                                                    analytics.export_analytics()  # Save to disk

                                                    # Remove from session state
                                                    del st.session_state.generated_follow_ups[
                                                        selected_user["id"]]

                                                    st.success(
                                                        f"Message sent to {username} successfully!")
                                                else:
                                                    st.error(
                                                        f"Failed to send message: {result.get('error', 'Unknown error')}")
                                            else:
                                                st.error(
                                                    "Failed to setup browser")

                                            # Keep browser open but ensure we're done
                                            st.info(
                                                "Browser will remain open in case you want to send more messages")

                                    except Exception as e:
                                        st.error(
                                            f"Error during message sending: {str(e)}")
                                        import traceback
                                        debug_container.error(
                                            f"Error details: {traceback.format_exc()}")

                                        # Refresh after send attempt
                                        time.sleep(2)
                                        st.rerun()

                    # Clear confirmation if user interacts with something else
                    if "confirm_override" in st.session_state and st.session_state.confirm_override:
                        if st.button("Cancel", key="cancel_override_button"):
                            st.session_state.confirm_override = False
                            st.rerun()

                # Generate or regenerate button
                generate_button_text = "Pre-generate Follow-up Message" if selected_user[
                    "id"] not in st.session_state.generated_follow_ups else "Regenerate Message"
                if st.button(generate_button_text, key="generate_pre_button"):
                    with st.spinner("Generating follow-up message with Gemini..."):
                        try:
                            # Generate the message
                            follow_up_message = generate_ai_follow_up_message(
                                user_data)

                            # Store in session state
                            st.session_state.generated_follow_ups[selected_user["id"]] = {
                                "message": follow_up_message,
                                "generated_at": datetime.now(timezone.utc).isoformat(),
                                "is_pre_generated": True
                            }
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error generating message: {e}")

    # Show follow-up history if it exists
    follow_up_history = user_data.get("follow_up_history", [])
    if follow_up_history:
        # Change from expander to container with a header to avoid nesting issues
        st.subheader("Follow-up History")
        st.write("Previous follow-up messages sent to this user:")
        for i, entry in enumerate(follow_up_history):
            st.markdown(
                f"**Follow-up {i+1}:** {entry.get('date', 'Unknown')[:10]}")
            st.info(entry.get("message", "No message content"))
            st.markdown("---")

    # Add the conversation history section
    st.subheader("Conversation History")
    history = user_data.get("conversation_history", [])
    client_analysis = user_data.get("client_analysis", {})

    # --- Display Profile Summary --- START ---
    profile_bio = client_analysis.get("profile_bio", {})
    if profile_bio:
        lifestyle = profile_bio.get(
            "LIFESTYLE") or profile_bio.get("lifestyle")
        interests = profile_bio.get(
            "INTERESTS") or profile_bio.get("interests") or []
        background_summary = "**Background Info:** "
        if lifestyle and lifestyle not in ["Unknown", ""]:
            background_summary += f"Lifestyle appears to be {lifestyle}. "
        if interests:
            background_summary += f"Known interests include: {', '.join(interests)}."

        if background_summary != "**Background Info:** ":  # Only display if we have info
            st.markdown(f"""
                <div style='
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0 5px 0;
                    background-color: #fffbe6; /* Light yellow background */
                    border-left: 5px solid #ffc107; /* Amber border */
                '>
                <small>📝 Profile Summary</small><br>
                {background_summary}
                </div>
            """, unsafe_allow_html=True)
    # --- Display Profile Summary --- END ---

    # --- Display Generated Initial Comment --- START ---
    generated_comment = client_analysis.get("generated_comment")
    if generated_comment:
        st.markdown(f"""
            <div style='
                padding: 10px;
                border-radius: 5px;
                margin: 5px 0;
                background-color: #e3f2fd; /* Lighter blue */
                border-left: 5px solid #2196f3; /* Blue border */
            '>
            <small>🤖 Generated Initial Comment (from Profile Analysis)</small><br>
            <strong>AI</strong>: {generated_comment}
            </div>
        """, unsafe_allow_html=True)
    # --- Display Generated Initial Comment --- END ---

    # --- Display Recorded Conversation History --- START ---
    if history:
        for msg in history:
            # Create a message container with different styles for user/AI
            is_ai = msg.get("type") == "ai"
            with st.container():
                # Format timestamp
                timestamp = msg.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(
                            timestamp.replace('Z', '+00:00'))
                        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

                # Display message with standard colors for AI/User
                st.markdown(f"""
                    <div style='
                        padding: 10px;
                        border-radius: 5px;
                        margin: 5px 0;
                        background-color: {"#e1f5fe" if is_ai else "#f5f5f5"}; /* Standard blue/grey */
                        border-left: 5px solid {"#0288d1" if is_ai else "#9e9e9e"};
                    '>
                    <small>{timestamp}</small><br>
                    <strong>{"AI" if is_ai else "User"}</strong>: {msg.get("text", "")}
                    </div>
                """, unsafe_allow_html=True)
    elif not generated_comment:  # Only show this if history is empty AND no generated comment was found
        st.info("No conversation history available.")
    # --- Display Recorded Conversation History --- END ---


def load_followup_manager():
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

        st.info(f"Found followup_manager at {followup_manager_path}")

        # Add parent directory to path if not already there
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        # Try importing now
        import importlib
        import followup_manager as fm
        # Force reload in case it was changed
        importlib.reload(fm)
        followup_manager = fm
        return True
    except ImportError as e:
        st.error(
            f"Could not import followup_manager: {e}. Follow-up sending will be disabled.")
        return False
    except Exception as e:
        st.error(f"Unexpected error loading followup_manager: {e}")
        return False


# Analytics file path
ANALYTICS_FILE_PATH = "C:\\Users\\Shannon\\analytics_data.json"

# Define constants
ACTIVE_WINDOW = 3600  # 1 hour in seconds

# Define helper functions


def ensure_timezone(dt):
    """Ensure a datetime object has timezone information"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_timestamp(timestamp_str):
    """Parse timestamp string to timezone-aware datetime"""
    try:
        if isinstance(timestamp_str, str):
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return ensure_timezone(dt)
        return ensure_timezone(timestamp_str)
    except (ValueError, TypeError):
        return None


def is_user_active(last_active_time):
    """Check if a user is active based on their last active time"""
    if not last_active_time:
        return False

    now = datetime.now(timezone.utc)
    last_active_dt = parse_timestamp(last_active_time)

    if not last_active_dt:
        return False

    time_diff = now - last_active_dt
    return time_diff.total_seconds() < ACTIVE_WINDOW


# Set page config with explicit sidebar settings
st.set_page_config(
    page_title="Shanbot Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Add custom CSS to ensure sidebar visibility
st.markdown("""
    <style>
    [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
        width: 300px;
    }
    [data-testid="stSidebar"][aria-expanded="false"] > div:first-child {
        width: 300px;
        margin-left: -300px;
    }
    </style>
    """, unsafe_allow_html=True)


def should_follow_up(conversation_data):
    """Determine if we should follow up based on conversation state."""
    # Extract metrics
    conv_metrics = conversation_data.get('metrics', {})

    # Get the last message timestamp
    last_message_time = conv_metrics.get('last_message_time')
    if not last_message_time:
        return False

    # Convert to datetime
    try:
        last_dt = datetime.fromisoformat(last_message_time)
    except ValueError:
        # Handle non-ISO format dates
        try:
            last_dt = datetime.strptime(
                last_message_time, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return False

    # Get current time
    now = datetime.now()

    # Calculate time difference
    time_diff = now - last_dt

    # Debug logging
    print(f"DEBUG - ID: {conversation_data.get('id', 'unknown')}, Last Message: {last_dt}, Diff: {time_diff}, Active: {time_diff.days >= 2}")

    # If no message for 2 days, suggest follow-up
    return time_diff.days >= 2


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

    # If automatic follow-up is disabled, always return False
    if not AUTO_FOLLOWUP_ENABLED:
        return False, None, None

    # If we decide to follow up, check if auto-follow-up is enabled
    if AUTO_FOLLOWUP_ENABLED and should_follow_up(conversation_data):
        # Schedule an automatic follow-up
        follow_up_message = generate_follow_up_message(conversation_data)
        schedule_automatic_followup(
            conversation_data.get("username", "unknown"),
            follow_up_message,
            follow_up_timing["conversation_end"]
        )
        return True, follow_up_timing["conversation_end"], follow_up_timing["reason"]

    return False, None, None


def generate_follow_up_message(conversation_data):
    """Generate a casual, friendly follow-up message based on previous conversations"""

    # Get engagement metrics
    conv_metrics = conversation_data.get('metrics', {})
    conv_metadata = conversation_data.get('metadata', {})

    # Get the user name if available
    user_name = conv_metadata.get('user_name', 'there')

    # Basic follow-up template
    follow_up_message = f"Hey {user_name}! How's it going? Just checking in to see how you're doing."

    # Enhance with more context if available
    if 'topic_interests' in conv_metadata:
        interests = conv_metadata.get('topic_interests', [])
        if 'meal_plan' in interests:
            follow_up_message = f"Hey {user_name}! How's your meal plan going? Keeping it clean? 🥗 Still crushing it?"
        elif 'workout' in interests:
            follow_up_message = f"Hey {user_name}! How's your training going this week? Getting those gains? 💪"

    return follow_up_message


def generate_ai_follow_up_message(conversation_data):
    """Generate a personalized follow-up message using Gemini AI based on conversation history and profile analysis"""
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
            for msg in history:
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

        Client Profile Information:
        {profile_info_text}

        Recent Conversation History:
        {history_text}

        Example (using history): "Hey {client_name}! How did that new workout split we talked about go this week? 💪"
        Example (using profile): "Hey {client_name}! Saw you're interested in vegan recipes - tried any cool new ones lately? 🥗"

        Generate the follow-up message now:
        """

        # Generate the response
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # Updated model
        )

        response = model.generate_content(prompt)
        follow_up_message = response.text.strip()

        # If the response is empty or too long, fall back to the regular message
        # Slightly increased word count limit
        if not follow_up_message or len(follow_up_message.split()) > 30:
            logger.warning(
                f"AI generated message too long or empty for {client_ig_username}, falling back. AI Message: '{follow_up_message}'")
            return generate_follow_up_message(conversation_data)

        logger.info(
            f"Generated AI follow-up for {client_ig_username}: '{follow_up_message}'")
        return follow_up_message

    except Exception as e:
        st.error(f"Error generating AI follow-up message: {e}")
        logger.error(
            f"Error generating AI follow-up for user {conversation_data.get('ig_username', 'unknown')}: {e}", exc_info=True)
        # Fallback to regular follow-up message if generation fails
        return generate_follow_up_message(conversation_data)


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

# Modify the auto-refresh initialization to ensure it's disabled
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60  # Default 60 seconds

# Sidebar navigation
st.sidebar.title("Shanbot Analytics")

# Add refresh controls
col1, col2 = st.sidebar.columns(2)
with col1:
    st.session_state.auto_refresh = st.checkbox(
        "Auto Refresh", value=st.session_state.auto_refresh)
with col2:
    if st.session_state.auto_refresh:
        st.session_state.refresh_interval = st.number_input("Interval (s)",
                                                            min_value=10,
                                                            max_value=300,
                                                            value=st.session_state.refresh_interval)

# Add manual refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.success("Data refreshed successfully!")

# Navigation selection in sidebar
# Add "view_profile" to session state if not present
if 'view_profile' not in st.session_state:
    st.session_state.view_profile = None

# Determine default page based on view_profile state
default_nav_index = 0  # Default to Overview
if st.session_state.view_profile:
    default_nav_index = 1  # Switch to User Profiles if a profile is selected

# Add "AI Data Assistant" to the list of pages
nav_options = ["Overview", "User Profiles", "AI Data Assistant"]
selected_page = st.sidebar.radio(
    "Navigation",
    nav_options,
    index=default_nav_index  # Set index based on whether a profile is being viewed
)

# If user manually selected User Profiles, clear any previous selection
if selected_page == "User Profiles" and not st.session_state.view_profile:
    # Reset view_profile if navigating TO User Profiles manually
    # This case might need refinement depending on desired UX
    pass  # Or maybe clear view_profile? Depends on flow.

# If user selects Overview or AI Assistant, clear view_profile
if selected_page != "User Profiles":
    st.session_state.view_profile = None

# Show data loading status
st.sidebar.markdown("---")
st.sidebar.info("Loaded data from analytics_data.json")

# Main content area
st.title(f"Shanbot Analytics - {selected_page}")  # Dynamic title

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # --- Calculate Overall Quality Score --- START ---
    overall_quality_score = calculate_overall_quality_score(
        st.session_state.conversation_metrics)
    # --- Calculate Overall Quality Score --- END ---

    # Calculate user metrics
    total_users = len(st.session_state.conversation_metrics)

    # Calculate active/inactive users using last_message_timestamp
    now = datetime.now(timezone.utc)  # Use UTC for consistency
    active_users = 0
    inactive_users = 0

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Use last_message_timestamp as the indicator of recent activity
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                # Parse the timestamp and ensure it's UTC
                last_active = parse_timestamp(last_active_timestamp)

                if last_active:
                    # Check if active within last hour
                    time_diff = now - last_active
                    if time_diff.total_seconds() < ACTIVE_WINDOW:  # 1 hour in seconds
                        active_users += 1
                    else:
                        inactive_users += 1
                else:
                    # Handle case where timestamp is invalid
                    inactive_users += 1
            except Exception as e:
                # Catch any parsing errors
                st.error(f"Error parsing timestamp for user {user_id}: {e}")
                inactive_users += 1
        else:
            # If no last message timestamp, consider inactive
            inactive_users += 1

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Stats")

        # Debug expander for User Stats calculations - ensure it's not nested in another expander
        with st.expander("User Stats Debug"):
            st.write("Raw Data:")
            st.write(
                f"Total conversations in metrics: {len(st.session_state.conversation_metrics)}")

            # Show active/inactive calculation details
            active_count = 0
            inactive_count = 0
            for user_id, user_data in st.session_state.conversation_metrics.items():
                conv_end = user_data.get("conversation_end_time")
                if conv_end:
                    try:
                        # Parse the timestamp
                        if isinstance(conv_end, str):
                            last_active = datetime.fromisoformat(
                                conv_end.replace('Z', '+00:00'))
                        else:
                            last_active = conv_end

                        # Ensure UTC
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(
                                tzinfo=timezone.utc)

                        # Calculate time difference
                        time_diff = now - last_active
                        minutes_diff = time_diff.total_seconds() / 60

                        st.write(f"User {user_id}:")
                        st.write(f"  - Last active: {last_active}")
                        st.write(
                            f"  - Minutes since last message: {minutes_diff:.1f}")
                        st.write(
                            f"  - Status: {'Active' if minutes_diff < 60 else 'Inactive'}")

                        if time_diff.total_seconds() < ACTIVE_WINDOW:
                            active_count += 1
                    except (ValueError, TypeError) as e:
                        st.write(
                            f"  - Error parsing timestamp for user {user_id}: {e}")
                        inactive_count += 1

            st.write("\nCalculated Totals:")
            st.write(f"Active Users (recounted): {active_count}")
            st.write(f"Inactive Users (recounted): {inactive_count}")

        # Display metrics
        st.metric("Total Users", total_users)
        st.metric("Active Users (1h)", active_users,
                  help="Users who have had a conversation in the last hour")
        st.metric("Inactive Users", inactive_users,
                  help="Users who haven't had a conversation in the last hour")

        # Add Overall Score display here or in a 4th column/new row
        st.metric("Overall Conversation Quality (Avg)", f"{overall_quality_score:.1f}",
                  help="Avg score based on engagement, goals & AI analysis (when available). Range varies.")

    with col2:
        st.subheader("Conversion Metrics")

        # Get total signups and inquiries
        total_signups = 0
        total_inquiries = 0
        total_offers = 0

        # Debug expander for Conversion Metrics - ensure it's not nested in another expander
        with st.expander("Conversion Metrics Debug"):
            st.write("Detailed Conversion Data:")
            for user_id, conv in st.session_state.conversation_metrics.items():
                # Track metrics for this user
                user_metrics = {
                    "signup": conv.get("signup_recorded", False),
                    "inquiries": conv.get("coaching_inquiry_count", 0),
                    "offer_shown": conv.get("offer_mentioned_in_conv", False)
                }

                # Update totals
                if user_metrics["signup"]:
                    total_signups += 1
                if user_metrics["inquiries"] > 0:
                    total_inquiries += 1
                if user_metrics["offer_shown"]:
                    total_offers += 1

                # Only show users with any conversion activity
                if any(user_metrics.values()):
                    st.write(f"\nUser {user_id}:")
                    st.write(f"  - Signed up: {user_metrics['signup']}")
                    st.write(
                        f"  - Inquiries made: {user_metrics['inquiries']}")
                    st.write(f"  - Offer shown: {user_metrics['offer_shown']}")

            st.write("\nTotals:")
            st.write(f"Total Signups: {total_signups}")
            st.write(f"Total Inquiries: {total_inquiries}")
            st.write(f"Total Offers Shown: {total_offers}")

        # Display metrics
        st.metric("Total Memberships Sold", total_signups,
                  help="Number of users who have signed up for membership")
        st.metric("Coaching Inquiries", total_inquiries,
                  help="Number of users who have inquired about coaching")

        # --- Add Expander for Inquiring Users --- START ---
        with st.expander(f"View {total_inquiries} Users Who Inquired"):
            inquiring_users_list = []
            for user_id, user_data in st.session_state.conversation_metrics.items():
                if user_data.get('coaching_inquiry_count', 0) > 0:
                    username = user_data.get("ig_username") or user_id
                    # Calculate status for indicator
                    is_active = False
                    last_active_timestamp = user_data.get(
                        "last_message_timestamp")
                    if last_active_timestamp:
                        try:
                            last_active_dt = parse_timestamp(
                                last_active_timestamp)
                            if last_active_dt:
                                time_diff = datetime.now(
                                    timezone.utc) - last_active_dt
                                if time_diff.total_seconds() < ACTIVE_WINDOW:
                                    is_active = True
                        except Exception:
                            pass
                    status_indicator = "🟢" if is_active else "🔴"
                    inquiring_users_list.append({
                        "id": user_id,
                        "username": username,
                        "status_indicator": status_indicator
                    })

            # Sort the list (e.g., by username)
            inquiring_users_list.sort(key=lambda x: x["username"])

            if inquiring_users_list:
                for user in inquiring_users_list:
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(
                            f"{user['status_indicator']} {user['username']}")
                    with cols[1]:
                        if st.button("View Profile", key=f"view_inquiry_{user['id']}", use_container_width=True):
                            st.session_state.view_profile = user['id']
                            st.rerun()
            else:
                st.info("No users found who have made inquiries.")
        # --- Add Expander for Inquiring Users --- END ---

        # Calculate and display conversion rate
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                  help="Percentage of users who signed up after seeing an offer")

    with col3:
        st.subheader("Engagement Overview")
        total_messages = st.session_state.global_metrics.get(
            "total_messages", 0)
        user_messages = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        ai_messages = st.session_state.global_metrics.get(
            "total_ai_messages", 0)

        # Display metrics
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Response Rate", f"{total_response_rate:.1f}%",
                  help="Percentage of AI questions that received a user response")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"])

    # Function to categorize users based on NEW thresholds
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
            # Users with 0 messages won't appear in these tabs anyway,
            # but good to handle the case.
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
    # Sorting by total messages keeps higher interaction users higher within activity status
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (x["is_active"], x["total_message_count"]), reverse=True)

    # Modify the high responders tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high_index = st.selectbox(
                "Select User",
                options=list(range(len(high_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{high_responders[i]['status_indicator']} {high_responders[i]['username']} - {high_responders[i]['user_message_count']} user msgs",
                key="high_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_high_button"):
                st.session_state.view_profile = high_responders[selected_high_index]['id']
                st.rerun()
        else:
            st.info("No high responders found")

    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium_index = st.selectbox(
                "Select User",
                options=list(range(len(medium_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{medium_responders[i]['status_indicator']} {medium_responders[i]['username']} - {medium_responders[i]['user_message_count']} user msgs",
                key="medium_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_medium_button"):
                st.session_state.view_profile = medium_responders[selected_medium_index]['id']
                st.rerun()
        else:
            st.info("No medium responders found")

    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low_index = st.selectbox(
                "Select User",
                options=list(range(len(low_responders))),
                # Update format_func to use USER messages
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

        # Create user info dict including status
        user_list.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        })

    # Sort users by active status first (descending), then by message count (descending)
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

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
            # Update format_func to include the status indicator
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages"
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
elif selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("Ask questions about your analytics data in natural language.")

    # Initialize chat history in session state
    if "ai_assistant_messages" not in st.session_state:
        st.session_state.ai_assistant_messages = []

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
You are a helpful data analyst assistant embedded in a Streamlit dashboard. Your task is to answer questions about Instagram follower interaction data based ONLY on the provided data context.

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
                {"role": "assistant", "content": "Sorry, I encountered an error."})  # Log simpler error

# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Auto-refresh logic
if st.session_state.auto_refresh and not st.session_state.get('_refreshing', False):
    st.session_state._refreshing = True
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    st.session_state._refreshing = False

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
        message_text="Yes please! I'm particularly interested in weight loss.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=2)).isoformat()
    )

    # Add another AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Perfect! Here's a link to our program: cocospersonaltraining.com/online. It includes personalized workouts, nutrition guidance, and weekly check-ins. Would you like to get started?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=3)).isoformat()
    )

    return "Test user added successfully!"


# Add test user button in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    st.sidebar.success(result)
    # Refresh the data
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.rerun()

# New function to schedule a follow-up message


def schedule_automatic_followup(username, message, scheduled_time):
    """Schedule a follow-up message to be sent automatically at the specified time"""
    global SCHEDULED_FOLLOWUPS

    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": datetime.now(timezone.utc),
        "status": "scheduled"
    })

    # Save scheduled follow-ups to a persistent store
    save_scheduled_followups()

    return True

# New function to check for and send scheduled follow-ups


def process_scheduled_followups():
    """Check for any scheduled follow-ups that are due and send them"""
    global SCHEDULED_FOLLOWUPS
    current_time = datetime.now(timezone.utc)

    # Load the latest scheduled follow-ups
    load_scheduled_followups()

    messages_sent = 0
    messages_to_send = []

    # First pass: identify messages to send
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        for i, msg_data in enumerate(messages):
            if msg_data["status"] == "scheduled" and msg_data["scheduled_time"] <= current_time:
                messages_to_send.append((username, i, msg_data))

    # Second pass: send messages (limited to prevent rate limiting)
    # Limit to 10 messages per processing cycle
    for username, index, msg_data in messages_to_send[:10]:
        try:
            # Get the followup module
            followup_module = sys.modules.get('followup_manager')
            if not followup_module:
                st.error("Follow-up manager not loaded")
                return False

            # Get the driver instance
            driver = followup_module.get_driver()
            if not driver:
                st.error("Instagram browser not available")
                return False

            # Send the message
            result = followup_module.send_follow_up_message(
                driver,
                username,
                msg_data["message"]
            )

            # Update status based on result
            if result.get("success", False):
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "sent"
                SCHEDULED_FOLLOWUPS[username][index]["sent_at"] = datetime.now(
                    timezone.utc)
                messages_sent += 1

                # Log the successful follow-up
                log_followup_success(username, msg_data["message"])
            else:
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
                SCHEDULED_FOLLOWUPS[username][index]["error"] = result.get(
                    "error", "Unknown error")

                # Log the failure
                log_followup_failure(
                    username, result.get("error", "Unknown error"))
        except Exception as e:
            SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
            SCHEDULED_FOLLOWUPS[username][index]["error"] = str(e)
            log_followup_failure(username, str(e))

    # Save the updated status
    save_scheduled_followups()

    return messages_sent

# New function to toggle automatic follow-up mode


def toggle_auto_followup(enabled, username=None):
    """Enable or disable automatic follow-up globally or for a specific user"""
    global AUTO_FOLLOWUP_ENABLED

    if username is None:
        # Global toggle
        AUTO_FOLLOWUP_ENABLED = enabled
        return True
    else:
        # TODO: Implement per-user toggle if needed
        return True

# New function to save scheduled follow-ups


def save_scheduled_followups():
    """Save scheduled follow-ups to a JSON file"""
    # Convert datetime objects to strings for JSON serialization
    serializable_followups = {}
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        serializable_followups[username] = []
        for msg in messages:
            serializable_msg = msg.copy()
            if isinstance(msg["scheduled_time"], datetime):
                serializable_msg["scheduled_time"] = msg["scheduled_time"].isoformat(
                )
            if "created_at" in msg and isinstance(msg["created_at"], datetime):
                serializable_msg["created_at"] = msg["created_at"].isoformat()
            if "sent_at" in msg and isinstance(msg["sent_at"], datetime):
                serializable_msg["sent_at"] = msg["sent_at"].isoformat()
            serializable_followups[username].append(serializable_msg)

    # Save to file
    with open("scheduled_followups.json", "w") as f:
        json.dump(serializable_followups, f, indent=2)

# New function to load scheduled follow-ups


def load_scheduled_followups():
    """Load scheduled follow-ups from a JSON file"""
    global SCHEDULED_FOLLOWUPS

    try:
        with open("scheduled_followups.json", "r") as f:
            serialized_followups = json.load(f)

        # Convert string timestamps back to datetime objects
        SCHEDULED_FOLLOWUPS = {}
        for username, messages in serialized_followups.items():
            SCHEDULED_FOLLOWUPS[username] = []
            for msg in messages:
                if isinstance(msg["scheduled_time"], str):
                    msg["scheduled_time"] = datetime.fromisoformat(
                        msg["scheduled_time"])
                if "created_at" in msg and isinstance(msg["created_at"], str):
                    msg["created_at"] = datetime.fromisoformat(
                        msg["created_at"])
                if "sent_at" in msg and isinstance(msg["sent_at"], str):
                    msg["sent_at"] = datetime.fromisoformat(msg["sent_at"])
                SCHEDULED_FOLLOWUPS[username].append(msg)
    except FileNotFoundError:
        # Initialize empty if file doesn't exist
        SCHEDULED_FOLLOWUPS = {}
    except Exception as e:
        st.error(f"Error loading scheduled follow-ups: {str(e)}")
        SCHEDULED_FOLLOWUPS = {}

# Function for logging follow-up success


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


# --- Follow-up Management in Sidebar ---
st.sidebar.header("Follow-up & Analysis")  # Combine headers
auto_followup = st.sidebar.checkbox(
    "Enable Automatic Follow-ups", value=AUTO_FOLLOWUP_ENABLED)

if auto_followup != AUTO_FOLLOWUP_ENABLED:
    toggle_auto_followup(auto_followup)
    st.sidebar.success(
        f"Automatic follow-up {'enabled' if auto_followup else 'disabled'}")

scheduled_count = sum(len(msgs)
                      for msgs in SCHEDULED_FOLLOWUPS.values() if msgs)
st.sidebar.text(f"Scheduled follow-ups: {scheduled_count}")

if st.sidebar.button("Process Scheduled Messages"):
    with st.spinner("Sending scheduled follow-ups..."):
        sent_count = process_scheduled_followups()
        st.sidebar.success(f"Sent {sent_count} follow-up messages")

st.sidebar.markdown("---")

# --- New Conversation Analysis Function --- START ---


def run_conversation_analysis():
    ANALYSIS_INACTIVITY_THRESHOLD = timedelta(hours=48)
    now = datetime.now(timezone.utc)
    conversations_to_analyze = []
    analysis_results = {}

    st.info("Identifying inactive conversations older than 48 hours...")

    # Identify conversations needing analysis
    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Check if already analyzed (e.g., by checking for 'conversation_summary')
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
        st.success("No new inactive conversations found needing analysis.")
        return 0

    st.info(
        f"Found {len(conversations_to_analyze)} conversations to analyze. Processing...")
    progress_bar = st.progress(0)
    analyzed_count = 0

    # Configure Gemini once
    try:
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
        # Change the model used for analysis
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}")
        return 0

    # Analyze each conversation
    for i, user_id in enumerate(conversations_to_analyze):
        user_data = st.session_state.conversation_metrics[user_id]
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
                [f"{msg.get('type','unknown').capitalize()}: {msg.get('text','')}" for msg in history])
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

            # Call Gemini
            # --- Implement Retry Logic --- START ---
            max_retries = 1  # Try once, then retry once more on 429
            attempt = 0
            analysis_text = None
            while attempt <= max_retries:
                try:
                    response = model.generate_content(prompt)
                    analysis_text = response.text.strip()
                    break  # Success, exit the retry loop
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    # Note: Specific exception type might be google.api_core.exceptions.ResourceExhausted
                    # We'll check the string representation for simplicity here
                    if "429" in str(e) and attempt < max_retries:
                        retry_delay_seconds = 10  # Default retry delay
                        try:
                            # Attempt to parse suggested delay (this part is fragile)
                            delay_match = re.search(
                                r'retry_delay \{ seconds: (\d+) \}', str(e))
                            if delay_match:
                                retry_delay_seconds = int(delay_match.group(1))
                        except Exception as parse_error:
                            logger.warning(
                                f"Could not parse retry_delay from error: {parse_error}")

                        logger.warning(
                            f"Rate limit hit for user {user_id}. Retrying in {retry_delay_seconds} seconds... (Attempt {attempt + 1}/{max_retries})")
                        st.warning(
                            f"Rate limit hit, pausing for {retry_delay_seconds}s before retry...")
                        time.sleep(retry_delay_seconds)
                        attempt += 1
                    else:
                        # Non-retryable error or final attempt failed
                        raise e  # Re-raise the exception to be caught by the outer loop
            # --- Implement Retry Logic --- END ---

            # Parse rating and summary (only if analysis_text was successfully obtained)
            rating = "Analysis Error"
            summary = "Could not parse AI response."
            if analysis_text is not None:
                if '***' in analysis_text:
                    parts = analysis_text.split('***', 1)
                    rating = parts[0].strip()
                    summary = parts[1].strip()
                elif analysis_text:  # Use whole response as summary if split fails
                    summary = analysis_text
                else:  # Handle case where AI returns empty string after retry
                    rating = "Analysis Error"
                    summary = "AI returned empty response."
            else:  # Should not happen if retry logic works, but safety check
                rating = "Analysis Error"
                summary = "Failed to get response from AI after retries."

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

        # Add a small delay between each API call to mitigate rate limits
        time.sleep(2)  # Sleep for 2 seconds

        # Update progress
        progress_bar.progress((i + 1) / len(conversations_to_analyze))

    # Save updated analytics
    if analyzed_count > 0:
        st.info("Saving analysis results...")
        try:
            analytics.export_analytics()
            st.success(
                f"Successfully analyzed and saved results for {analyzed_count} conversations.")
        except Exception as e:
            st.error(f"Failed to save analytics after analysis: {e}")
    else:
        st.warning("No conversations were successfully analyzed.")

    return analyzed_count
# --- New Conversation Analysis Function --- END ---


# Add Analysis Button to Sidebar
st.sidebar.markdown("---")
st.sidebar.header("Conversation Analysis")
if st.sidebar.button("Analyze Inactive Conversations (48h+)"):
    with st.spinner("Running conversation analysis..."):
        run_conversation_analysis()


# --- Testing Tools in Sidebar ---
# ... (add_test_user button remains) ...

# --- New Function for Overall Score --- START ---
def calculate_overall_quality_score(conversation_metrics):
    """Calculates an average quality score across all conversations."""
    if not conversation_metrics:
        return 0.0

    total_score = 0
    scored_conversations_count = 0

    # Define point mapping for AI ratings
    rating_map = {
        "Signup": 15,  # Highest value
        "Hot Lead": 10,
        "Warm Lead": 7,
        "Inquiry Only": 5,
        "Nurture": 4,
        "General Chat": 2,
        "Stalled": 0
        # Failed/Error ratings implicitly get 0 from metric calculation
    }

    for user_id, user_data in conversation_metrics.items():
        score = 0
        has_valid_rating = False
        rating = user_data.get("conversation_rating")

        # Prioritize AI rating if available and valid
        if rating and rating in rating_map:
            score = rating_map[rating]
            has_valid_rating = True
        else:
            # Calculate score based on metrics if no valid AI rating
            metric_score = 0
            user_msgs = user_data.get("user_messages", 0)

            # Engagement points
            if user_msgs >= 51:
                metric_score += 5
            elif user_msgs >= 11:
                metric_score += 3
            elif user_msgs >= 1:
                metric_score += 1

            # Topic points
            if user_data.get("fitness_topic_initiator") is not None:
                metric_score += 2

            # Goal points
            if user_data.get("coaching_inquiry_count", 0) > 0:
                metric_score += 5
            if user_data.get("offer_mentioned_in_conv", False):
                metric_score += 1

            # Signup gets significant boost, potentially overriding other points for simplicity?
            if user_data.get("signup_recorded", False):
                # Let's make signup a high fixed score if not rated by AI
                metric_score = 15

            score = metric_score

        total_score += score
        scored_conversations_count += 1  # Count all conversations

    if scored_conversations_count == 0:
        return 0.0

    average_score = total_score / scored_conversations_count
    return average_score
# --- New Function for Overall Score --- END ---


# --- Main Page Logic --- START ---
# ... (Sidebar logic remains) ...

# Main content area
# ... (Title remains) ...

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # --- Calculate Overall Quality Score --- START ---
    overall_quality_score = calculate_overall_quality_score(
        st.session_state.conversation_metrics)
    # --- Calculate Overall Quality Score --- END ---

    # Calculate user metrics
    total_users = len(st.session_state.conversation_metrics)

    # Calculate active/inactive users using last_message_timestamp
    now = datetime.now(timezone.utc)  # Use UTC for consistency
    active_users = 0
    inactive_users = 0

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Use last_message_timestamp as the indicator of recent activity
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                # Parse the timestamp and ensure it's UTC
                last_active = parse_timestamp(last_active_timestamp)

                if last_active:
                    # Check if active within last hour
                    time_diff = now - last_active
                    if time_diff.total_seconds() < ACTIVE_WINDOW:  # 1 hour in seconds
                        active_users += 1
                    else:
                        inactive_users += 1
                else:
                    # Handle case where timestamp is invalid
                    inactive_users += 1
            except Exception as e:
                # Catch any parsing errors
                st.error(f"Error parsing timestamp for user {user_id}: {e}")
                inactive_users += 1
        else:
            # If no last message timestamp, consider inactive
            inactive_users += 1

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Stats")

        # Debug expander for User Stats calculations - ensure it's not nested in another expander
        with st.expander("User Stats Debug"):
            st.write("Raw Data:")
            st.write(
                f"Total conversations in metrics: {len(st.session_state.conversation_metrics)}")

            # Show active/inactive calculation details
            active_count = 0
            inactive_count = 0
            for user_id, user_data in st.session_state.conversation_metrics.items():
                conv_end = user_data.get("conversation_end_time")
                if conv_end:
                    try:
                        # Parse the timestamp
                        if isinstance(conv_end, str):
                            last_active = datetime.fromisoformat(
                                conv_end.replace('Z', '+00:00'))
                        else:
                            last_active = conv_end

                        # Ensure UTC
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(
                                tzinfo=timezone.utc)

                        # Calculate time difference
                        time_diff = now - last_active
                        minutes_diff = time_diff.total_seconds() / 60

                        st.write(f"User {user_id}:")
                        st.write(f"  - Last active: {last_active}")
                        st.write(
                            f"  - Minutes since last message: {minutes_diff:.1f}")
                        st.write(
                            f"  - Status: {'Active' if minutes_diff < 60 else 'Inactive'}")

                        if time_diff.total_seconds() < ACTIVE_WINDOW:
                            active_count += 1
                    except (ValueError, TypeError) as e:
                        st.write(
                            f"  - Error parsing timestamp for user {user_id}: {e}")
                        inactive_count += 1

            st.write("\nCalculated Totals:")
            st.write(f"Active Users (recounted): {active_count}")
            st.write(f"Inactive Users (recounted): {inactive_count}")

        # Display metrics
        st.metric("Total Users", total_users)
        st.metric("Active Users (1h)", active_users,
                  help="Users who have had a conversation in the last hour")
        st.metric("Inactive Users", inactive_users,
                  help="Users who haven't had a conversation in the last hour")

        # Add Overall Score display here or in a 4th column/new row
        st.metric("Overall Conversation Quality (Avg)", f"{overall_quality_score:.1f}",
                  help="Avg score based on engagement, goals & AI analysis (when available). Range varies.")

    with col2:
        st.subheader("Conversion Metrics")

        # Get total signups and inquiries
        total_signups = 0
        total_inquiries = 0
        total_offers = 0

        # Debug expander for Conversion Metrics - ensure it's not nested in another expander
        with st.expander("Conversion Metrics Debug"):
            st.write("Detailed Conversion Data:")
            for user_id, conv in st.session_state.conversation_metrics.items():
                # Track metrics for this user
                user_metrics = {
                    "signup": conv.get("signup_recorded", False),
                    "inquiries": conv.get("coaching_inquiry_count", 0),
                    "offer_shown": conv.get("offer_mentioned_in_conv", False)
                }

                # Update totals
                if user_metrics["signup"]:
                    total_signups += 1
                if user_metrics["inquiries"] > 0:
                    total_inquiries += 1
                if user_metrics["offer_shown"]:
                    total_offers += 1

                # Only show users with any conversion activity
                if any(user_metrics.values()):
                    st.write(f"\nUser {user_id}:")
                    st.write(f"  - Signed up: {user_metrics['signup']}")
                    st.write(
                        f"  - Inquiries made: {user_metrics['inquiries']}")
                    st.write(f"  - Offer shown: {user_metrics['offer_shown']}")

            st.write("\nTotals:")
            st.write(f"Total Signups: {total_signups}")
            st.write(f"Total Inquiries: {total_inquiries}")
            st.write(f"Total Offers Shown: {total_offers}")

        # Display metrics
        st.metric("Total Memberships Sold", total_signups,
                  help="Number of users who have signed up for membership")
        st.metric("Coaching Inquiries", total_inquiries,
                  help="Number of users who have inquired about coaching")

        # --- Add Expander for Inquiring Users --- START ---
        with st.expander(f"View {total_inquiries} Users Who Inquired"):
            inquiring_users_list = []
            for user_id, user_data in st.session_state.conversation_metrics.items():
                if user_data.get('coaching_inquiry_count', 0) > 0:
                    username = user_data.get("ig_username") or user_id
                    # Calculate status for indicator
                    is_active = False
                    last_active_timestamp = user_data.get(
                        "last_message_timestamp")
                    if last_active_timestamp:
                        try:
                            last_active_dt = parse_timestamp(
                                last_active_timestamp)
                            if last_active_dt:
                                time_diff = datetime.now(
                                    timezone.utc) - last_active_dt
                                if time_diff.total_seconds() < ACTIVE_WINDOW:
                                    is_active = True
                        except Exception:
                            pass
                    status_indicator = "🟢" if is_active else "🔴"
                    inquiring_users_list.append({
                        "id": user_id,
                        "username": username,
                        "status_indicator": status_indicator
                    })

            # Sort the list (e.g., by username)
            inquiring_users_list.sort(key=lambda x: x["username"])

            if inquiring_users_list:
                for user in inquiring_users_list:
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(
                            f"{user['status_indicator']} {user['username']}")
                    with cols[1]:
                        if st.button("View Profile", key=f"view_inquiry_{user['id']}", use_container_width=True):
                            st.session_state.view_profile = user['id']
                            st.rerun()
            else:
                st.info("No users found who have made inquiries.")
        # --- Add Expander for Inquiring Users --- END ---

        # Calculate and display conversion rate
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                  help="Percentage of users who signed up after seeing an offer")

    with col3:
        st.subheader("Engagement Overview")
        total_messages = st.session_state.global_metrics.get(
            "total_messages", 0)
        user_messages = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        ai_messages = st.session_state.global_metrics.get(
            "total_ai_messages", 0)

        # Display metrics
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Response Rate", f"{total_response_rate:.1f}%",
                  help="Percentage of AI questions that received a user response")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"])

    # Function to categorize users based on NEW thresholds
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
            # Users with 0 messages won't appear in these tabs anyway,
            # but good to handle the case.
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
    # Sorting by total messages keeps higher interaction users higher within activity status
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (x["is_active"], x["total_message_count"]), reverse=True)

    # Modify the high responders tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high_index = st.selectbox(
                "Select User",
                options=list(range(len(high_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{high_responders[i]['status_indicator']} {high_responders[i]['username']} - {high_responders[i]['user_message_count']} user msgs",
                key="high_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_high_button"):
                st.session_state.view_profile = high_responders[selected_high_index]['id']
                st.rerun()
        else:
            st.info("No high responders found")

    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium_index = st.selectbox(
                "Select User",
                options=list(range(len(medium_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{medium_responders[i]['status_indicator']} {medium_responders[i]['username']} - {medium_responders[i]['user_message_count']} user msgs",
                key="medium_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_medium_button"):
                st.session_state.view_profile = medium_responders[selected_medium_index]['id']
                st.rerun()
        else:
            st.info("No medium responders found")

    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low_index = st.selectbox(
                "Select User",
                options=list(range(len(low_responders))),
                # Update format_func to use USER messages
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

        # Create user info dict including status
        user_list.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        })

    # Sort users by active status first (descending), then by message count (descending)
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

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
            # Update format_func to include the status indicator
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages"
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
elif selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("Ask questions about your analytics data in natural language.")

    # Initialize chat history in session state
    if "ai_assistant_messages" not in st.session_state:
        st.session_state.ai_assistant_messages = []

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
You are a helpful data analyst assistant embedded in a Streamlit dashboard. Your task is to answer questions about Instagram follower interaction data based ONLY on the provided data context.

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
                {"role": "assistant", "content": "Sorry, I encountered an error."})  # Log simpler error

# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Auto-refresh logic
if st.session_state.auto_refresh and not st.session_state.get('_refreshing', False):
    st.session_state._refreshing = True
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    st.session_state._refreshing = False

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
        message_text="Yes please! I'm particularly interested in weight loss.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=2)).isoformat()
    )

    # Add another AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Perfect! Here's a link to our program: cocospersonaltraining.com/online. It includes personalized workouts, nutrition guidance, and weekly check-ins. Would you like to get started?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=3)).isoformat()
    )

    return "Test user added successfully!"


# Add test user button in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    st.sidebar.success(result)
    # Refresh the data
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.rerun()

# New function to schedule a follow-up message


def schedule_automatic_followup(username, message, scheduled_time):
    """Schedule a follow-up message to be sent automatically at the specified time"""
    global SCHEDULED_FOLLOWUPS

    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": datetime.now(timezone.utc),
        "status": "scheduled"
    })

    # Save scheduled follow-ups to a persistent store
    save_scheduled_followups()

    return True

# New function to check for and send scheduled follow-ups


def process_scheduled_followups():
    """Check for any scheduled follow-ups that are due and send them"""
    global SCHEDULED_FOLLOWUPS
    current_time = datetime.now(timezone.utc)

    # Load the latest scheduled follow-ups
    load_scheduled_followups()

    messages_sent = 0
    messages_to_send = []

    # First pass: identify messages to send
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        for i, msg_data in enumerate(messages):
            if msg_data["status"] == "scheduled" and msg_data["scheduled_time"] <= current_time:
                messages_to_send.append((username, i, msg_data))

    # Second pass: send messages (limited to prevent rate limiting)
    # Limit to 10 messages per processing cycle
    for username, index, msg_data in messages_to_send[:10]:
        try:
            # Get the followup module
            followup_module = sys.modules.get('followup_manager')
            if not followup_module:
                st.error("Follow-up manager not loaded")
                return False

            # Get the driver instance
            driver = followup_module.get_driver()
            if not driver:
                st.error("Instagram browser not available")
                return False

            # Send the message
            result = followup_module.send_follow_up_message(
                driver,
                username,
                msg_data["message"]
            )

            # Update status based on result
            if result.get("success", False):
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "sent"
                SCHEDULED_FOLLOWUPS[username][index]["sent_at"] = datetime.now(
                    timezone.utc)
                messages_sent += 1

                # Log the successful follow-up
                log_followup_success(username, msg_data["message"])
            else:
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
                SCHEDULED_FOLLOWUPS[username][index]["error"] = result.get(
                    "error", "Unknown error")

                # Log the failure
                log_followup_failure(
                    username, result.get("error", "Unknown error"))
        except Exception as e:
            SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
            SCHEDULED_FOLLOWUPS[username][index]["error"] = str(e)
            log_followup_failure(username, str(e))

    # Save the updated status
    save_scheduled_followups()

    return messages_sent

# New function to toggle automatic follow-up mode


def toggle_auto_followup(enabled, username=None):
    """Enable or disable automatic follow-up globally or for a specific user"""
    global AUTO_FOLLOWUP_ENABLED

    if username is None:
        # Global toggle
        AUTO_FOLLOWUP_ENABLED = enabled
        return True
    else:
        # TODO: Implement per-user toggle if needed
        return True

# New function to save scheduled follow-ups


def save_scheduled_followups():
    """Save scheduled follow-ups to a JSON file"""
    # Convert datetime objects to strings for JSON serialization
    serializable_followups = {}
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        serializable_followups[username] = []
        for msg in messages:
            serializable_msg = msg.copy()
            if isinstance(msg["scheduled_time"], datetime):
                serializable_msg["scheduled_time"] = msg["scheduled_time"].isoformat(
                )
            if "created_at" in msg and isinstance(msg["created_at"], datetime):
                serializable_msg["created_at"] = msg["created_at"].isoformat()
            if "sent_at" in msg and isinstance(msg["sent_at"], datetime):
                serializable_msg["sent_at"] = msg["sent_at"].isoformat()
            serializable_followups[username].append(serializable_msg)

    # Save to file
    with open("scheduled_followups.json", "w") as f:
        json.dump(serializable_followups, f, indent=2)

# New function to load scheduled follow-ups


def load_scheduled_followups():
    """Load scheduled follow-ups from a JSON file"""
    global SCHEDULED_FOLLOWUPS

    try:
        with open("scheduled_followups.json", "r") as f:
            serialized_followups = json.load(f)

        # Convert string timestamps back to datetime objects
        SCHEDULED_FOLLOWUPS = {}
        for username, messages in serialized_followups.items():
            SCHEDULED_FOLLOWUPS[username] = []
            for msg in messages:
                if isinstance(msg["scheduled_time"], str):
                    msg["scheduled_time"] = datetime.fromisoformat(
                        msg["scheduled_time"])
                if "created_at" in msg and isinstance(msg["created_at"], str):
                    msg["created_at"] = datetime.fromisoformat(
                        msg["created_at"])
                if "sent_at" in msg and isinstance(msg["sent_at"], str):
                    msg["sent_at"] = datetime.fromisoformat(msg["sent_at"])
                SCHEDULED_FOLLOWUPS[username].append(msg)
    except FileNotFoundError:
        # Initialize empty if file doesn't exist
        SCHEDULED_FOLLOWUPS = {}
    except Exception as e:
        st.error(f"Error loading scheduled follow-ups: {str(e)}")
        SCHEDULED_FOLLOWUPS = {}

# Function for logging follow-up success


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


# --- Follow-up Management in Sidebar ---
st.sidebar.header("Follow-up & Analysis")  # Combine headers
auto_followup = st.sidebar.checkbox(
    "Enable Automatic Follow-ups", value=AUTO_FOLLOWUP_ENABLED)

if auto_followup != AUTO_FOLLOWUP_ENABLED:
    toggle_auto_followup(auto_followup)
    st.sidebar.success(
        f"Automatic follow-up {'enabled' if auto_followup else 'disabled'}")

scheduled_count = sum(len(msgs)
                      for msgs in SCHEDULED_FOLLOWUPS.values() if msgs)
st.sidebar.text(f"Scheduled follow-ups: {scheduled_count}")

if st.sidebar.button("Process Scheduled Messages"):
    with st.spinner("Sending scheduled follow-ups..."):
        sent_count = process_scheduled_followups()
        st.sidebar.success(f"Sent {sent_count} follow-up messages")

st.sidebar.markdown("---")

# --- New Conversation Analysis Function --- START ---


def run_conversation_analysis():
    ANALYSIS_INACTIVITY_THRESHOLD = timedelta(hours=48)
    now = datetime.now(timezone.utc)
    conversations_to_analyze = []
    analysis_results = {}

    st.info("Identifying inactive conversations older than 48 hours...")

    # Identify conversations needing analysis
    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Check if already analyzed (e.g., by checking for 'conversation_summary')
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
        st.success("No new inactive conversations found needing analysis.")
        return 0

    st.info(
        f"Found {len(conversations_to_analyze)} conversations to analyze. Processing...")
    progress_bar = st.progress(0)
    analyzed_count = 0

    # Configure Gemini once
    try:
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
        # Change the model used for analysis
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}")
        return 0

    # Analyze each conversation
    for i, user_id in enumerate(conversations_to_analyze):
        user_data = st.session_state.conversation_metrics[user_id]
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
                [f"{msg.get('type','unknown').capitalize()}: {msg.get('text','')}" for msg in history])
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

            # Call Gemini
            # --- Implement Retry Logic --- START ---
            max_retries = 1  # Try once, then retry once more on 429
            attempt = 0
            analysis_text = None
            while attempt <= max_retries:
                try:
                    response = model.generate_content(prompt)
                    analysis_text = response.text.strip()
                    break  # Success, exit the retry loop
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    # Note: Specific exception type might be google.api_core.exceptions.ResourceExhausted
                    # We'll check the string representation for simplicity here
                    if "429" in str(e) and attempt < max_retries:
                        retry_delay_seconds = 10  # Default retry delay
                        try:
                            # Attempt to parse suggested delay (this part is fragile)
                            delay_match = re.search(
                                r'retry_delay \{ seconds: (\d+) \}', str(e))
                            if delay_match:
                                retry_delay_seconds = int(delay_match.group(1))
                        except Exception as parse_error:
                            logger.warning(
                                f"Could not parse retry_delay from error: {parse_error}")

                        logger.warning(
                            f"Rate limit hit for user {user_id}. Retrying in {retry_delay_seconds} seconds... (Attempt {attempt + 1}/{max_retries})")
                        st.warning(
                            f"Rate limit hit, pausing for {retry_delay_seconds}s before retry...")
                        time.sleep(retry_delay_seconds)
                        attempt += 1
                    else:
                        # Non-retryable error or final attempt failed
                        raise e  # Re-raise the exception to be caught by the outer loop
            # --- Implement Retry Logic --- END ---

            # Parse rating and summary (only if analysis_text was successfully obtained)
            rating = "Analysis Error"
            summary = "Could not parse AI response."
            if analysis_text is not None:
                if '***' in analysis_text:
                    parts = analysis_text.split('***', 1)
                    rating = parts[0].strip()
                    summary = parts[1].strip()
                elif analysis_text:  # Use whole response as summary if split fails
                    summary = analysis_text
                else:  # Handle case where AI returns empty string after retry
                    rating = "Analysis Error"
                    summary = "AI returned empty response."
            else:  # Should not happen if retry logic works, but safety check
                rating = "Analysis Error"
                summary = "Failed to get response from AI after retries."

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

        # Add a small delay between each API call to mitigate rate limits
        time.sleep(2)  # Sleep for 2 seconds

        # Update progress
        progress_bar.progress((i + 1) / len(conversations_to_analyze))

    # Save updated analytics
    if analyzed_count > 0:
        st.info("Saving analysis results...")
        try:
            analytics.export_analytics()
            st.success(
                f"Successfully analyzed and saved results for {analyzed_count} conversations.")
        except Exception as e:
            st.error(f"Failed to save analytics after analysis: {e}")
    else:
        st.warning("No conversations were successfully analyzed.")

    return analyzed_count
# --- New Conversation Analysis Function --- END ---


# Add Analysis Button to Sidebar
st.sidebar.markdown("---")
st.sidebar.header("Conversation Analysis")
if st.sidebar.button("Analyze Inactive Conversations (48h+)"):
    with st.spinner("Running conversation analysis..."):
        run_conversation_analysis()


# --- Testing Tools in Sidebar ---
# ... (add_test_user button remains) ...

# --- New Function for Overall Score --- START ---
def calculate_overall_quality_score(conversation_metrics):
    """Calculates an average quality score across all conversations."""
    if not conversation_metrics:
        return 0.0

    total_score = 0
    scored_conversations_count = 0

    # Define point mapping for AI ratings
    rating_map = {
        "Signup": 15,  # Highest value
        "Hot Lead": 10,
        "Warm Lead": 7,
        "Inquiry Only": 5,
        "Nurture": 4,
        "General Chat": 2,
        "Stalled": 0
        # Failed/Error ratings implicitly get 0 from metric calculation
    }

    for user_id, user_data in conversation_metrics.items():
        score = 0
        has_valid_rating = False
        rating = user_data.get("conversation_rating")

        # Prioritize AI rating if available and valid
        if rating and rating in rating_map:
            score = rating_map[rating]
            has_valid_rating = True
        else:
            # Calculate score based on metrics if no valid AI rating
            metric_score = 0
            user_msgs = user_data.get("user_messages", 0)

            # Engagement points
            if user_msgs >= 51:
                metric_score += 5
            elif user_msgs >= 11:
                metric_score += 3
            elif user_msgs >= 1:
                metric_score += 1

            # Topic points
            if user_data.get("fitness_topic_initiator") is not None:
                metric_score += 2

            # Goal points
            if user_data.get("coaching_inquiry_count", 0) > 0:
                metric_score += 5
            if user_data.get("offer_mentioned_in_conv", False):
                metric_score += 1

            # Signup gets significant boost, potentially overriding other points for simplicity?
            if user_data.get("signup_recorded", False):
                # Let's make signup a high fixed score if not rated by AI
                metric_score = 15

            score = metric_score

        total_score += score
        scored_conversations_count += 1  # Count all conversations

    if scored_conversations_count == 0:
        return 0.0

    average_score = total_score / scored_conversations_count
    return average_score
# --- New Function for Overall Score --- END ---


# --- Main Page Logic --- START ---
# ... (Sidebar logic remains) ...

# Main content area
# ... (Title remains) ...

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # --- Calculate Overall Quality Score --- START ---
    overall_quality_score = calculate_overall_quality_score(
        st.session_state.conversation_metrics)
    # --- Calculate Overall Quality Score --- END ---

    # Calculate user metrics
    total_users = len(st.session_state.conversation_metrics)

    # Calculate active/inactive users using last_message_timestamp
    now = datetime.now(timezone.utc)  # Use UTC for consistency
    active_users = 0
    inactive_users = 0

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Use last_message_timestamp as the indicator of recent activity
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                # Parse the timestamp and ensure it's UTC
                last_active = parse_timestamp(last_active_timestamp)

                if last_active:
                    # Check if active within last hour
                    time_diff = now - last_active
                    if time_diff.total_seconds() < ACTIVE_WINDOW:  # 1 hour in seconds
                        active_users += 1
                    else:
                        inactive_users += 1
                else:
                    # Handle case where timestamp is invalid
                    inactive_users += 1
            except Exception as e:
                # Catch any parsing errors
                st.error(f"Error parsing timestamp for user {user_id}: {e}")
                inactive_users += 1
        else:
            # If no last message timestamp, consider inactive
            inactive_users += 1

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Stats")

        # Debug expander for User Stats calculations - ensure it's not nested in another expander
        with st.expander("User Stats Debug"):
            st.write("Raw Data:")
            st.write(
                f"Total conversations in metrics: {len(st.session_state.conversation_metrics)}")

            # Show active/inactive calculation details
            active_count = 0
            inactive_count = 0
            for user_id, user_data in st.session_state.conversation_metrics.items():
                conv_end = user_data.get("conversation_end_time")
                if conv_end:
                    try:
                        # Parse the timestamp
                        if isinstance(conv_end, str):
                            last_active = datetime.fromisoformat(
                                conv_end.replace('Z', '+00:00'))
                        else:
                            last_active = conv_end

                        # Ensure UTC
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(
                                tzinfo=timezone.utc)

                        # Calculate time difference
                        time_diff = now - last_active
                        minutes_diff = time_diff.total_seconds() / 60

                        st.write(f"User {user_id}:")
                        st.write(f"  - Last active: {last_active}")
                        st.write(
                            f"  - Minutes since last message: {minutes_diff:.1f}")
                        st.write(
                            f"  - Status: {'Active' if minutes_diff < 60 else 'Inactive'}")

                        if time_diff.total_seconds() < ACTIVE_WINDOW:
                            active_count += 1
                    except (ValueError, TypeError) as e:
                        st.write(
                            f"  - Error parsing timestamp for user {user_id}: {e}")
                        inactive_count += 1

            st.write("\nCalculated Totals:")
            st.write(f"Active Users (recounted): {active_count}")
            st.write(f"Inactive Users (recounted): {inactive_count}")

        # Display metrics
        st.metric("Total Users", total_users)
        st.metric("Active Users (1h)", active_users,
                  help="Users who have had a conversation in the last hour")
        st.metric("Inactive Users", inactive_users,
                  help="Users who haven't had a conversation in the last hour")

        # Add Overall Score display here or in a 4th column/new row
        st.metric("Overall Conversation Quality (Avg)", f"{overall_quality_score:.1f}",
                  help="Avg score based on engagement, goals & AI analysis (when available). Range varies.")

    with col2:
        st.subheader("Conversion Metrics")

        # Get total signups and inquiries
        total_signups = 0
        total_inquiries = 0
        total_offers = 0

        # Debug expander for Conversion Metrics - ensure it's not nested in another expander
        with st.expander("Conversion Metrics Debug"):
            st.write("Detailed Conversion Data:")
            for user_id, conv in st.session_state.conversation_metrics.items():
                # Track metrics for this user
                user_metrics = {
                    "signup": conv.get("signup_recorded", False),
                    "inquiries": conv.get("coaching_inquiry_count", 0),
                    "offer_shown": conv.get("offer_mentioned_in_conv", False)
                }

                # Update totals
                if user_metrics["signup"]:
                    total_signups += 1
                if user_metrics["inquiries"] > 0:
                    total_inquiries += 1
                if user_metrics["offer_shown"]:
                    total_offers += 1

                # Only show users with any conversion activity
                if any(user_metrics.values()):
                    st.write(f"\nUser {user_id}:")
                    st.write(f"  - Signed up: {user_metrics['signup']}")
                    st.write(
                        f"  - Inquiries made: {user_metrics['inquiries']}")
                    st.write(f"  - Offer shown: {user_metrics['offer_shown']}")

            st.write("\nTotals:")
            st.write(f"Total Signups: {total_signups}")
            st.write(f"Total Inquiries: {total_inquiries}")
            st.write(f"Total Offers Shown: {total_offers}")

        # Display metrics
        st.metric("Total Memberships Sold", total_signups,
                  help="Number of users who have signed up for membership")
        st.metric("Coaching Inquiries", total_inquiries,
                  help="Number of users who have inquired about coaching")

        # --- Add Expander for Inquiring Users --- START ---
        with st.expander(f"View {total_inquiries} Users Who Inquired"):
            inquiring_users_list = []
            for user_id, user_data in st.session_state.conversation_metrics.items():
                if user_data.get('coaching_inquiry_count', 0) > 0:
                    username = user_data.get("ig_username") or user_id
                    # Calculate status for indicator
                    is_active = False
                    last_active_timestamp = user_data.get(
                        "last_message_timestamp")
                    if last_active_timestamp:
                        try:
                            last_active_dt = parse_timestamp(
                                last_active_timestamp)
                            if last_active_dt:
                                time_diff = datetime.now(
                                    timezone.utc) - last_active_dt
                                if time_diff.total_seconds() < ACTIVE_WINDOW:
                                    is_active = True
                        except Exception:
                            pass
                    status_indicator = "🟢" if is_active else "🔴"
                    inquiring_users_list.append({
                        "id": user_id,
                        "username": username,
                        "status_indicator": status_indicator
                    })

            # Sort the list (e.g., by username)
            inquiring_users_list.sort(key=lambda x: x["username"])

            if inquiring_users_list:
                for user in inquiring_users_list:
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(
                            f"{user['status_indicator']} {user['username']}")
                    with cols[1]:
                        if st.button("View Profile", key=f"view_inquiry_{user['id']}", use_container_width=True):
                            st.session_state.view_profile = user['id']
                            st.rerun()
            else:
                st.info("No users found who have made inquiries.")
        # --- Add Expander for Inquiring Users --- END ---

        # Calculate and display conversion rate
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                  help="Percentage of users who signed up after seeing an offer")

    with col3:
        st.subheader("Engagement Overview")
        total_messages = st.session_state.global_metrics.get(
            "total_messages", 0)
        user_messages = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        ai_messages = st.session_state.global_metrics.get(
            "total_ai_messages", 0)

        # Display metrics
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Response Rate", f"{total_response_rate:.1f}%",
                  help="Percentage of AI questions that received a user response")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"])

    # Function to categorize users based on NEW thresholds
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
            # Users with 0 messages won't appear in these tabs anyway,
            # but good to handle the case.
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
    # Sorting by total messages keeps higher interaction users higher within activity status
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (x["is_active"], x["total_message_count"]), reverse=True)

    # Modify the high responders tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high_index = st.selectbox(
                "Select User",
                options=list(range(len(high_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{high_responders[i]['status_indicator']} {high_responders[i]['username']} - {high_responders[i]['user_message_count']} user msgs",
                key="high_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_high_button"):
                st.session_state.view_profile = high_responders[selected_high_index]['id']
                st.rerun()
        else:
            st.info("No high responders found")

    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium_index = st.selectbox(
                "Select User",
                options=list(range(len(medium_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{medium_responders[i]['status_indicator']} {medium_responders[i]['username']} - {medium_responders[i]['user_message_count']} user msgs",
                key="medium_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_medium_button"):
                st.session_state.view_profile = medium_responders[selected_medium_index]['id']
                st.rerun()
        else:
            st.info("No medium responders found")

    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low_index = st.selectbox(
                "Select User",
                options=list(range(len(low_responders))),
                # Update format_func to use USER messages
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

        # Create user info dict including status
        user_list.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        })

    # Sort users by active status first (descending), then by message count (descending)
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

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
            # Update format_func to include the status indicator
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages"
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
elif selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("Ask questions about your analytics data in natural language.")

    # Initialize chat history in session state
    if "ai_assistant_messages" not in st.session_state:
        st.session_state.ai_assistant_messages = []

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
You are a helpful data analyst assistant embedded in a Streamlit dashboard. Your task is to answer questions about Instagram follower interaction data based ONLY on the provided data context.

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
                {"role": "assistant", "content": "Sorry, I encountered an error."})  # Log simpler error

# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Auto-refresh logic
if st.session_state.auto_refresh and not st.session_state.get('_refreshing', False):
    st.session_state._refreshing = True
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    st.session_state._refreshing = False

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
        message_text="Yes please! I'm particularly interested in weight loss.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=2)).isoformat()
    )

    # Add another AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Perfect! Here's a link to our program: cocospersonaltraining.com/online. It includes personalized workouts, nutrition guidance, and weekly check-ins. Would you like to get started?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=3)).isoformat()
    )

    return "Test user added successfully!"


# Add test user button in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    st.sidebar.success(result)
    # Refresh the data
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.rerun()

# New function to schedule a follow-up message


def schedule_automatic_followup(username, message, scheduled_time):
    """Schedule a follow-up message to be sent automatically at the specified time"""
    global SCHEDULED_FOLLOWUPS

    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": datetime.now(timezone.utc),
        "status": "scheduled"
    })

    # Save scheduled follow-ups to a persistent store
    save_scheduled_followups()

    return True

# New function to check for and send scheduled follow-ups


def process_scheduled_followups():
    """Check for any scheduled follow-ups that are due and send them"""
    global SCHEDULED_FOLLOWUPS
    current_time = datetime.now(timezone.utc)

    # Load the latest scheduled follow-ups
    load_scheduled_followups()

    messages_sent = 0
    messages_to_send = []

    # First pass: identify messages to send
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        for i, msg_data in enumerate(messages):
            if msg_data["status"] == "scheduled" and msg_data["scheduled_time"] <= current_time:
                messages_to_send.append((username, i, msg_data))

    # Second pass: send messages (limited to prevent rate limiting)
    # Limit to 10 messages per processing cycle
    for username, index, msg_data in messages_to_send[:10]:
        try:
            # Get the followup module
            followup_module = sys.modules.get('followup_manager')
            if not followup_module:
                st.error("Follow-up manager not loaded")
                return False

            # Get the driver instance
            driver = followup_module.get_driver()
            if not driver:
                st.error("Instagram browser not available")
                return False

            # Send the message
            result = followup_module.send_follow_up_message(
                driver,
                username,
                msg_data["message"]
            )

            # Update status based on result
            if result.get("success", False):
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "sent"
                SCHEDULED_FOLLOWUPS[username][index]["sent_at"] = datetime.now(
                    timezone.utc)
                messages_sent += 1

                # Log the successful follow-up
                log_followup_success(username, msg_data["message"])
            else:
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
                SCHEDULED_FOLLOWUPS[username][index]["error"] = result.get(
                    "error", "Unknown error")

                # Log the failure
                log_followup_failure(
                    username, result.get("error", "Unknown error"))
        except Exception as e:
            SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
            SCHEDULED_FOLLOWUPS[username][index]["error"] = str(e)
            log_followup_failure(username, str(e))

    # Save the updated status
    save_scheduled_followups()

    return messages_sent

# New function to toggle automatic follow-up mode


def toggle_auto_followup(enabled, username=None):
    """Enable or disable automatic follow-up globally or for a specific user"""
    global AUTO_FOLLOWUP_ENABLED

    if username is None:
        # Global toggle
        AUTO_FOLLOWUP_ENABLED = enabled
        return True
    else:
        # TODO: Implement per-user toggle if needed
        return True

# New function to save scheduled follow-ups


def save_scheduled_followups():
    """Save scheduled follow-ups to a JSON file"""
    # Convert datetime objects to strings for JSON serialization
    serializable_followups = {}
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        serializable_followups[username] = []
        for msg in messages:
            serializable_msg = msg.copy()
            if isinstance(msg["scheduled_time"], datetime):
                serializable_msg["scheduled_time"] = msg["scheduled_time"].isoformat(
                )
            if "created_at" in msg and isinstance(msg["created_at"], datetime):
                serializable_msg["created_at"] = msg["created_at"].isoformat()
            if "sent_at" in msg and isinstance(msg["sent_at"], datetime):
                serializable_msg["sent_at"] = msg["sent_at"].isoformat()
            serializable_followups[username].append(serializable_msg)

    # Save to file
    with open("scheduled_followups.json", "w") as f:
        json.dump(serializable_followups, f, indent=2)

# New function to load scheduled follow-ups


def load_scheduled_followups():
    """Load scheduled follow-ups from a JSON file"""
    global SCHEDULED_FOLLOWUPS

    try:
        with open("scheduled_followups.json", "r") as f:
            serialized_followups = json.load(f)

        # Convert string timestamps back to datetime objects
        SCHEDULED_FOLLOWUPS = {}
        for username, messages in serialized_followups.items():
            SCHEDULED_FOLLOWUPS[username] = []
            for msg in messages:
                if isinstance(msg["scheduled_time"], str):
                    msg["scheduled_time"] = datetime.fromisoformat(
                        msg["scheduled_time"])
                if "created_at" in msg and isinstance(msg["created_at"], str):
                    msg["created_at"] = datetime.fromisoformat(
                        msg["created_at"])
                if "sent_at" in msg and isinstance(msg["sent_at"], str):
                    msg["sent_at"] = datetime.fromisoformat(msg["sent_at"])
                SCHEDULED_FOLLOWUPS[username].append(msg)
    except FileNotFoundError:
        # Initialize empty if file doesn't exist
        SCHEDULED_FOLLOWUPS = {}
    except Exception as e:
        st.error(f"Error loading scheduled follow-ups: {str(e)}")
        SCHEDULED_FOLLOWUPS = {}

# Function for logging follow-up success


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


# --- Follow-up Management in Sidebar ---
st.sidebar.header("Follow-up & Analysis")  # Combine headers
auto_followup = st.sidebar.checkbox(
    "Enable Automatic Follow-ups", value=AUTO_FOLLOWUP_ENABLED)

if auto_followup != AUTO_FOLLOWUP_ENABLED:
    toggle_auto_followup(auto_followup)
    st.sidebar.success(
        f"Automatic follow-up {'enabled' if auto_followup else 'disabled'}")

scheduled_count = sum(len(msgs)
                      for msgs in SCHEDULED_FOLLOWUPS.values() if msgs)
st.sidebar.text(f"Scheduled follow-ups: {scheduled_count}")

if st.sidebar.button("Process Scheduled Messages"):
    with st.spinner("Sending scheduled follow-ups..."):
        sent_count = process_scheduled_followups()
        st.sidebar.success(f"Sent {sent_count} follow-up messages")

st.sidebar.markdown("---")

# --- New Conversation Analysis Function --- START ---


def run_conversation_analysis():
    ANALYSIS_INACTIVITY_THRESHOLD = timedelta(hours=48)
    now = datetime.now(timezone.utc)
    conversations_to_analyze = []
    analysis_results = {}

    st.info("Identifying inactive conversations older than 48 hours...")

    # Identify conversations needing analysis
    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Check if already analyzed (e.g., by checking for 'conversation_summary')
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
        st.success("No new inactive conversations found needing analysis.")
        return 0

    st.info(
        f"Found {len(conversations_to_analyze)} conversations to analyze. Processing...")
    progress_bar = st.progress(0)
    analyzed_count = 0

    # Configure Gemini once
    try:
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
        # Change the model used for analysis
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}")
        return 0

    # Analyze each conversation
    for i, user_id in enumerate(conversations_to_analyze):
        user_data = st.session_state.conversation_metrics[user_id]
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
                [f"{msg.get('type','unknown').capitalize()}: {msg.get('text','')}" for msg in history])
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

            # Call Gemini
            # --- Implement Retry Logic --- START ---
            max_retries = 1  # Try once, then retry once more on 429
            attempt = 0
            analysis_text = None
            while attempt <= max_retries:
                try:
                    response = model.generate_content(prompt)
                    analysis_text = response.text.strip()
                    break  # Success, exit the retry loop
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    # Note: Specific exception type might be google.api_core.exceptions.ResourceExhausted
                    # We'll check the string representation for simplicity here
                    if "429" in str(e) and attempt < max_retries:
                        retry_delay_seconds = 10  # Default retry delay
                        try:
                            # Attempt to parse suggested delay (this part is fragile)
                            delay_match = re.search(
                                r'retry_delay \{ seconds: (\d+) \}', str(e))
                            if delay_match:
                                retry_delay_seconds = int(delay_match.group(1))
                        except Exception as parse_error:
                            logger.warning(
                                f"Could not parse retry_delay from error: {parse_error}")

                        logger.warning(
                            f"Rate limit hit for user {user_id}. Retrying in {retry_delay_seconds} seconds... (Attempt {attempt + 1}/{max_retries})")
                        st.warning(
                            f"Rate limit hit, pausing for {retry_delay_seconds}s before retry...")
                        time.sleep(retry_delay_seconds)
                        attempt += 1
                    else:
                        # Non-retryable error or final attempt failed
                        raise e  # Re-raise the exception to be caught by the outer loop
            # --- Implement Retry Logic --- END ---

            # Parse rating and summary (only if analysis_text was successfully obtained)
            rating = "Analysis Error"
            summary = "Could not parse AI response."
            if analysis_text is not None:
                if '***' in analysis_text:
                    parts = analysis_text.split('***', 1)
                    rating = parts[0].strip()
                    summary = parts[1].strip()
                elif analysis_text:  # Use whole response as summary if split fails
                    summary = analysis_text
                else:  # Handle case where AI returns empty string after retry
                    rating = "Analysis Error"
                    summary = "AI returned empty response."
            else:  # Should not happen if retry logic works, but safety check
                rating = "Analysis Error"
                summary = "Failed to get response from AI after retries."

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

        # Add a small delay between each API call to mitigate rate limits
        time.sleep(2)  # Sleep for 2 seconds

        # Update progress
        progress_bar.progress((i + 1) / len(conversations_to_analyze))

    # Save updated analytics
    if analyzed_count > 0:
        st.info("Saving analysis results...")
        try:
            analytics.export_analytics()
            st.success(
                f"Successfully analyzed and saved results for {analyzed_count} conversations.")
        except Exception as e:
            st.error(f"Failed to save analytics after analysis: {e}")
    else:
        st.warning("No conversations were successfully analyzed.")

    return analyzed_count
# --- New Conversation Analysis Function --- END ---


# Add Analysis Button to Sidebar
st.sidebar.markdown("---")
st.sidebar.header("Conversation Analysis")
if st.sidebar.button("Analyze Inactive Conversations (48h+)"):
    with st.spinner("Running conversation analysis..."):
        run_conversation_analysis()


# --- Testing Tools in Sidebar ---
# ... (add_test_user button remains) ...

# --- New Function for Overall Score --- START ---
def calculate_overall_quality_score(conversation_metrics):
    """Calculates an average quality score across all conversations."""
    if not conversation_metrics:
        return 0.0

    total_score = 0
    scored_conversations_count = 0

    # Define point mapping for AI ratings
    rating_map = {
        "Signup": 15,  # Highest value
        "Hot Lead": 10,
        "Warm Lead": 7,
        "Inquiry Only": 5,
        "Nurture": 4,
        "General Chat": 2,
        "Stalled": 0
        # Failed/Error ratings implicitly get 0 from metric calculation
    }

    for user_id, user_data in conversation_metrics.items():
        score = 0
        has_valid_rating = False
        rating = user_data.get("conversation_rating")

        # Prioritize AI rating if available and valid
        if rating and rating in rating_map:
            score = rating_map[rating]
            has_valid_rating = True
        else:
            # Calculate score based on metrics if no valid AI rating
            metric_score = 0
            user_msgs = user_data.get("user_messages", 0)

            # Engagement points
            if user_msgs >= 51:
                metric_score += 5
            elif user_msgs >= 11:
                metric_score += 3
            elif user_msgs >= 1:
                metric_score += 1

            # Topic points
            if user_data.get("fitness_topic_initiator") is not None:
                metric_score += 2

            # Goal points
            if user_data.get("coaching_inquiry_count", 0) > 0:
                metric_score += 5
            if user_data.get("offer_mentioned_in_conv", False):
                metric_score += 1

            # Signup gets significant boost, potentially overriding other points for simplicity?
            if user_data.get("signup_recorded", False):
                # Let's make signup a high fixed score if not rated by AI
                metric_score = 15

            score = metric_score

        total_score += score
        scored_conversations_count += 1  # Count all conversations

    if scored_conversations_count == 0:
        return 0.0

    average_score = total_score / scored_conversations_count
    return average_score
# --- New Function for Overall Score --- END ---


# --- Main Page Logic --- START ---
# ... (Sidebar logic remains) ...

# Main content area
# ... (Title remains) ...

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # --- Calculate Overall Quality Score --- START ---
    overall_quality_score = calculate_overall_quality_score(
        st.session_state.conversation_metrics)
    # --- Calculate Overall Quality Score --- END ---

    # Calculate user metrics
    total_users = len(st.session_state.conversation_metrics)

    # Calculate active/inactive users using last_message_timestamp
    now = datetime.now(timezone.utc)  # Use UTC for consistency
    active_users = 0
    inactive_users = 0

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Use last_message_timestamp as the indicator of recent activity
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                # Parse the timestamp and ensure it's UTC
                last_active = parse_timestamp(last_active_timestamp)

                if last_active:
                    # Check if active within last hour
                    time_diff = now - last_active
                    if time_diff.total_seconds() < ACTIVE_WINDOW:  # 1 hour in seconds
                        active_users += 1
                    else:
                        inactive_users += 1
                else:
                    # Handle case where timestamp is invalid
                    inactive_users += 1
            except Exception as e:
                # Catch any parsing errors
                st.error(f"Error parsing timestamp for user {user_id}: {e}")
                inactive_users += 1
        else:
            # If no last message timestamp, consider inactive
            inactive_users += 1

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Stats")

        # Debug expander for User Stats calculations - ensure it's not nested in another expander
        with st.expander("User Stats Debug"):
            st.write("Raw Data:")
            st.write(
                f"Total conversations in metrics: {len(st.session_state.conversation_metrics)}")

            # Show active/inactive calculation details
            active_count = 0
            inactive_count = 0
            for user_id, user_data in st.session_state.conversation_metrics.items():
                conv_end = user_data.get("conversation_end_time")
                if conv_end:
                    try:
                        # Parse the timestamp
                        if isinstance(conv_end, str):
                            last_active = datetime.fromisoformat(
                                conv_end.replace('Z', '+00:00'))
                        else:
                            last_active = conv_end

                        # Ensure UTC
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(
                                tzinfo=timezone.utc)

                        # Calculate time difference
                        time_diff = now - last_active
                        minutes_diff = time_diff.total_seconds() / 60

                        st.write(f"User {user_id}:")
                        st.write(f"  - Last active: {last_active}")
                        st.write(
                            f"  - Minutes since last message: {minutes_diff:.1f}")
                        st.write(
                            f"  - Status: {'Active' if minutes_diff < 60 else 'Inactive'}")

                        if time_diff.total_seconds() < ACTIVE_WINDOW:
                            active_count += 1
                    except (ValueError, TypeError) as e:
                        st.write(
                            f"  - Error parsing timestamp for user {user_id}: {e}")
                        inactive_count += 1

            st.write("\nCalculated Totals:")
            st.write(f"Active Users (recounted): {active_count}")
            st.write(f"Inactive Users (recounted): {inactive_count}")

        # Display metrics
        st.metric("Total Users", total_users)
        st.metric("Active Users (1h)", active_users,
                  help="Users who have had a conversation in the last hour")
        st.metric("Inactive Users", inactive_users,
                  help="Users who haven't had a conversation in the last hour")

        # Add Overall Score display here or in a 4th column/new row
        st.metric("Overall Conversation Quality (Avg)", f"{overall_quality_score:.1f}",
                  help="Avg score based on engagement, goals & AI analysis (when available). Range varies.")

    with col2:
        st.subheader("Conversion Metrics")

        # Get total signups and inquiries
        total_signups = 0
        total_inquiries = 0
        total_offers = 0

        # Debug expander for Conversion Metrics - ensure it's not nested in another expander
        with st.expander("Conversion Metrics Debug"):
            st.write("Detailed Conversion Data:")
            for user_id, conv in st.session_state.conversation_metrics.items():
                # Track metrics for this user
                user_metrics = {
                    "signup": conv.get("signup_recorded", False),
                    "inquiries": conv.get("coaching_inquiry_count", 0),
                    "offer_shown": conv.get("offer_mentioned_in_conv", False)
                }

                # Update totals
                if user_metrics["signup"]:
                    total_signups += 1
                if user_metrics["inquiries"] > 0:
                    total_inquiries += 1
                if user_metrics["offer_shown"]:
                    total_offers += 1

                # Only show users with any conversion activity
                if any(user_metrics.values()):
                    st.write(f"\nUser {user_id}:")
                    st.write(f"  - Signed up: {user_metrics['signup']}")
                    st.write(
                        f"  - Inquiries made: {user_metrics['inquiries']}")
                    st.write(f"  - Offer shown: {user_metrics['offer_shown']}")

            st.write("\nTotals:")
            st.write(f"Total Signups: {total_signups}")
            st.write(f"Total Inquiries: {total_inquiries}")
            st.write(f"Total Offers Shown: {total_offers}")

        # Display metrics
        st.metric("Total Memberships Sold", total_signups,
                  help="Number of users who have signed up for membership")
        st.metric("Coaching Inquiries", total_inquiries,
                  help="Number of users who have inquired about coaching")

        # --- Add Expander for Inquiring Users --- START ---
        with st.expander(f"View {total_inquiries} Users Who Inquired"):
            inquiring_users_list = []
            for user_id, user_data in st.session_state.conversation_metrics.items():
                if user_data.get('coaching_inquiry_count', 0) > 0:
                    username = user_data.get("ig_username") or user_id
                    # Calculate status for indicator
                    is_active = False
                    last_active_timestamp = user_data.get(
                        "last_message_timestamp")
                    if last_active_timestamp:
                        try:
                            last_active_dt = parse_timestamp(
                                last_active_timestamp)
                            if last_active_dt:
                                time_diff = datetime.now(
                                    timezone.utc) - last_active_dt
                                if time_diff.total_seconds() < ACTIVE_WINDOW:
                                    is_active = True
                        except Exception:
                            pass
                    status_indicator = "🟢" if is_active else "🔴"
                    inquiring_users_list.append({
                        "id": user_id,
                        "username": username,
                        "status_indicator": status_indicator
                    })

            # Sort the list (e.g., by username)
            inquiring_users_list.sort(key=lambda x: x["username"])

            if inquiring_users_list:
                for user in inquiring_users_list:
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(
                            f"{user['status_indicator']} {user['username']}")
                    with cols[1]:
                        if st.button("View Profile", key=f"view_inquiry_{user['id']}", use_container_width=True):
                            st.session_state.view_profile = user['id']
                            st.rerun()
            else:
                st.info("No users found who have made inquiries.")
        # --- Add Expander for Inquiring Users --- END ---

        # Calculate and display conversion rate
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                  help="Percentage of users who signed up after seeing an offer")

    with col3:
        st.subheader("Engagement Overview")
        total_messages = st.session_state.global_metrics.get(
            "total_messages", 0)
        user_messages = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        ai_messages = st.session_state.global_metrics.get(
            "total_ai_messages", 0)

        # Display metrics
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Response Rate", f"{total_response_rate:.1f}%",
                  help="Percentage of AI questions that received a user response")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"])

    # Function to categorize users based on NEW thresholds
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
            # Users with 0 messages won't appear in these tabs anyway,
            # but good to handle the case.
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
    # Sorting by total messages keeps higher interaction users higher within activity status
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (x["is_active"], x["total_message_count"]), reverse=True)

    # Modify the high responders tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high_index = st.selectbox(
                "Select User",
                options=list(range(len(high_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{high_responders[i]['status_indicator']} {high_responders[i]['username']} - {high_responders[i]['user_message_count']} user msgs",
                key="high_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_high_button"):
                st.session_state.view_profile = high_responders[selected_high_index]['id']
                st.rerun()
        else:
            st.info("No high responders found")

    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium_index = st.selectbox(
                "Select User",
                options=list(range(len(medium_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{medium_responders[i]['status_indicator']} {medium_responders[i]['username']} - {medium_responders[i]['user_message_count']} user msgs",
                key="medium_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_medium_button"):
                st.session_state.view_profile = medium_responders[selected_medium_index]['id']
                st.rerun()
        else:
            st.info("No medium responders found")

    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low_index = st.selectbox(
                "Select User",
                options=list(range(len(low_responders))),
                # Update format_func to use USER messages
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

        # Create user info dict including status
        user_list.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        })

    # Sort users by active status first (descending), then by message count (descending)
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

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
            # Update format_func to include the status indicator
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages"
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
elif selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("Ask questions about your analytics data in natural language.")

    # Initialize chat history in session state
    if "ai_assistant_messages" not in st.session_state:
        st.session_state.ai_assistant_messages = []

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
You are a helpful data analyst assistant embedded in a Streamlit dashboard. Your task is to answer questions about Instagram follower interaction data based ONLY on the provided data context.

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
                {"role": "assistant", "content": "Sorry, I encountered an error."})  # Log simpler error

# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Auto-refresh logic
if st.session_state.auto_refresh and not st.session_state.get('_refreshing', False):
    st.session_state._refreshing = True
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    st.session_state._refreshing = False

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
        message_text="Yes please! I'm particularly interested in weight loss.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=2)).isoformat()
    )

    # Add another AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Perfect! Here's a link to our program: cocospersonaltraining.com/online. It includes personalized workouts, nutrition guidance, and weekly check-ins. Would you like to get started?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=3)).isoformat()
    )

    return "Test user added successfully!"


# Add test user button in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    st.sidebar.success(result)
    # Refresh the data
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.rerun()

# New function to schedule a follow-up message


def schedule_automatic_followup(username, message, scheduled_time):
    """Schedule a follow-up message to be sent automatically at the specified time"""
    global SCHEDULED_FOLLOWUPS

    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": datetime.now(timezone.utc),
        "status": "scheduled"
    })

    # Save scheduled follow-ups to a persistent store
    save_scheduled_followups()

    return True

# New function to check for and send scheduled follow-ups


def process_scheduled_followups():
    """Check for any scheduled follow-ups that are due and send them"""
    global SCHEDULED_FOLLOWUPS
    current_time = datetime.now(timezone.utc)

    # Load the latest scheduled follow-ups
    load_scheduled_followups()

    messages_sent = 0
    messages_to_send = []

    # First pass: identify messages to send
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        for i, msg_data in enumerate(messages):
            if msg_data["status"] == "scheduled" and msg_data["scheduled_time"] <= current_time:
                messages_to_send.append((username, i, msg_data))

    # Second pass: send messages (limited to prevent rate limiting)
    # Limit to 10 messages per processing cycle
    for username, index, msg_data in messages_to_send[:10]:
        try:
            # Get the followup module
            followup_module = sys.modules.get('followup_manager')
            if not followup_module:
                st.error("Follow-up manager not loaded")
                return False

            # Get the driver instance
            driver = followup_module.get_driver()
            if not driver:
                st.error("Instagram browser not available")
                return False

            # Send the message
            result = followup_module.send_follow_up_message(
                driver,
                username,
                msg_data["message"]
            )

            # Update status based on result
            if result.get("success", False):
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "sent"
                SCHEDULED_FOLLOWUPS[username][index]["sent_at"] = datetime.now(
                    timezone.utc)
                messages_sent += 1

                # Log the successful follow-up
                log_followup_success(username, msg_data["message"])
            else:
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
                SCHEDULED_FOLLOWUPS[username][index]["error"] = result.get(
                    "error", "Unknown error")

                # Log the failure
                log_followup_failure(
                    username, result.get("error", "Unknown error"))
        except Exception as e:
            SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
            SCHEDULED_FOLLOWUPS[username][index]["error"] = str(e)
            log_followup_failure(username, str(e))

    # Save the updated status
    save_scheduled_followups()

    return messages_sent

# New function to toggle automatic follow-up mode


def toggle_auto_followup(enabled, username=None):
    """Enable or disable automatic follow-up globally or for a specific user"""
    global AUTO_FOLLOWUP_ENABLED

    if username is None:
        # Global toggle
        AUTO_FOLLOWUP_ENABLED = enabled
        return True
    else:
        # TODO: Implement per-user toggle if needed
        return True

# New function to save scheduled follow-ups


def save_scheduled_followups():
    """Save scheduled follow-ups to a JSON file"""
    # Convert datetime objects to strings for JSON serialization
    serializable_followups = {}
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        serializable_followups[username] = []
        for msg in messages:
            serializable_msg = msg.copy()
            if isinstance(msg["scheduled_time"], datetime):
                serializable_msg["scheduled_time"] = msg["scheduled_time"].isoformat(
                )
            if "created_at" in msg and isinstance(msg["created_at"], datetime):
                serializable_msg["created_at"] = msg["created_at"].isoformat()
            if "sent_at" in msg and isinstance(msg["sent_at"], datetime):
                serializable_msg["sent_at"] = msg["sent_at"].isoformat()
            serializable_followups[username].append(serializable_msg)

    # Save to file
    with open("scheduled_followups.json", "w") as f:
        json.dump(serializable_followups, f, indent=2)

# New function to load scheduled follow-ups


def load_scheduled_followups():
    """Load scheduled follow-ups from a JSON file"""
    global SCHEDULED_FOLLOWUPS

    try:
        with open("scheduled_followups.json", "r") as f:
            serialized_followups = json.load(f)

        # Convert string timestamps back to datetime objects
        SCHEDULED_FOLLOWUPS = {}
        for username, messages in serialized_followups.items():
            SCHEDULED_FOLLOWUPS[username] = []
            for msg in messages:
                if isinstance(msg["scheduled_time"], str):
                    msg["scheduled_time"] = datetime.fromisoformat(
                        msg["scheduled_time"])
                if "created_at" in msg and isinstance(msg["created_at"], str):
                    msg["created_at"] = datetime.fromisoformat(
                        msg["created_at"])
                if "sent_at" in msg and isinstance(msg["sent_at"], str):
                    msg["sent_at"] = datetime.fromisoformat(msg["sent_at"])
                SCHEDULED_FOLLOWUPS[username].append(msg)
    except FileNotFoundError:
        # Initialize empty if file doesn't exist
        SCHEDULED_FOLLOWUPS = {}
    except Exception as e:
        st.error(f"Error loading scheduled follow-ups: {str(e)}")
        SCHEDULED_FOLLOWUPS = {}

# Function for logging follow-up success


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


# --- Follow-up Management in Sidebar ---
st.sidebar.header("Follow-up & Analysis")  # Combine headers
auto_followup = st.sidebar.checkbox(
    "Enable Automatic Follow-ups", value=AUTO_FOLLOWUP_ENABLED)

if auto_followup != AUTO_FOLLOWUP_ENABLED:
    toggle_auto_followup(auto_followup)
    st.sidebar.success(
        f"Automatic follow-up {'enabled' if auto_followup else 'disabled'}")

scheduled_count = sum(len(msgs)
                      for msgs in SCHEDULED_FOLLOWUPS.values() if msgs)
st.sidebar.text(f"Scheduled follow-ups: {scheduled_count}")

if st.sidebar.button("Process Scheduled Messages"):
    with st.spinner("Sending scheduled follow-ups..."):
        sent_count = process_scheduled_followups()
        st.sidebar.success(f"Sent {sent_count} follow-up messages")

st.sidebar.markdown("---")

# --- New Conversation Analysis Function --- START ---


def run_conversation_analysis():
    ANALYSIS_INACTIVITY_THRESHOLD = timedelta(hours=48)
    now = datetime.now(timezone.utc)
    conversations_to_analyze = []
    analysis_results = {}

    st.info("Identifying inactive conversations older than 48 hours...")

    # Identify conversations needing analysis
    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Check if already analyzed (e.g., by checking for 'conversation_summary')
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
        st.success("No new inactive conversations found needing analysis.")
        return 0

    st.info(
        f"Found {len(conversations_to_analyze)} conversations to analyze. Processing...")
    progress_bar = st.progress(0)
    analyzed_count = 0

    # Configure Gemini once
    try:
        genai.configure(api_key="AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
        # Change the model used for analysis
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}")
        return 0

    # Analyze each conversation
    for i, user_id in enumerate(conversations_to_analyze):
        user_data = st.session_state.conversation_metrics[user_id]
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
                [f"{msg.get('type','unknown').capitalize()}: {msg.get('text','')}" for msg in history])
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

            # Call Gemini
            # --- Implement Retry Logic --- START ---
            max_retries = 1  # Try once, then retry once more on 429
            attempt = 0
            analysis_text = None
            while attempt <= max_retries:
                try:
                    response = model.generate_content(prompt)
                    analysis_text = response.text.strip()
                    break  # Success, exit the retry loop
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    # Note: Specific exception type might be google.api_core.exceptions.ResourceExhausted
                    # We'll check the string representation for simplicity here
                    if "429" in str(e) and attempt < max_retries:
                        retry_delay_seconds = 10  # Default retry delay
                        try:
                            # Attempt to parse suggested delay (this part is fragile)
                            delay_match = re.search(
                                r'retry_delay \{ seconds: (\d+) \}', str(e))
                            if delay_match:
                                retry_delay_seconds = int(delay_match.group(1))
                        except Exception as parse_error:
                            logger.warning(
                                f"Could not parse retry_delay from error: {parse_error}")

                        logger.warning(
                            f"Rate limit hit for user {user_id}. Retrying in {retry_delay_seconds} seconds... (Attempt {attempt + 1}/{max_retries})")
                        st.warning(
                            f"Rate limit hit, pausing for {retry_delay_seconds}s before retry...")
                        time.sleep(retry_delay_seconds)
                        attempt += 1
                    else:
                        # Non-retryable error or final attempt failed
                        raise e  # Re-raise the exception to be caught by the outer loop
            # --- Implement Retry Logic --- END ---

            # Parse rating and summary (only if analysis_text was successfully obtained)
            rating = "Analysis Error"
            summary = "Could not parse AI response."
            if analysis_text is not None:
                if '***' in analysis_text:
                    parts = analysis_text.split('***', 1)
                    rating = parts[0].strip()
                    summary = parts[1].strip()
                elif analysis_text:  # Use whole response as summary if split fails
                    summary = analysis_text
                else:  # Handle case where AI returns empty string after retry
                    rating = "Analysis Error"
                    summary = "AI returned empty response."
            else:  # Should not happen if retry logic works, but safety check
                rating = "Analysis Error"
                summary = "Failed to get response from AI after retries."

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

        # Add a small delay between each API call to mitigate rate limits
        time.sleep(2)  # Sleep for 2 seconds

        # Update progress
        progress_bar.progress((i + 1) / len(conversations_to_analyze))

    # Save updated analytics
    if analyzed_count > 0:
        st.info("Saving analysis results...")
        try:
            analytics.export_analytics()
            st.success(
                f"Successfully analyzed and saved results for {analyzed_count} conversations.")
        except Exception as e:
            st.error(f"Failed to save analytics after analysis: {e}")
    else:
        st.warning("No conversations were successfully analyzed.")

    return analyzed_count
# --- New Conversation Analysis Function --- END ---


# Add Analysis Button to Sidebar
st.sidebar.markdown("---")
st.sidebar.header("Conversation Analysis")
if st.sidebar.button("Analyze Inactive Conversations (48h+)"):
    with st.spinner("Running conversation analysis..."):
        run_conversation_analysis()


# --- Testing Tools in Sidebar ---
# ... (add_test_user button remains) ...

# --- New Function for Overall Score --- START ---
def calculate_overall_quality_score(conversation_metrics):
    """Calculates an average quality score across all conversations."""
    if not conversation_metrics:
        return 0.0

    total_score = 0
    scored_conversations_count = 0

    # Define point mapping for AI ratings
    rating_map = {
        "Signup": 15,  # Highest value
        "Hot Lead": 10,
        "Warm Lead": 7,
        "Inquiry Only": 5,
        "Nurture": 4,
        "General Chat": 2,
        "Stalled": 0
        # Failed/Error ratings implicitly get 0 from metric calculation
    }

    for user_id, user_data in conversation_metrics.items():
        score = 0
        has_valid_rating = False
        rating = user_data.get("conversation_rating")

        # Prioritize AI rating if available and valid
        if rating and rating in rating_map:
            score = rating_map[rating]
            has_valid_rating = True
        else:
            # Calculate score based on metrics if no valid AI rating
            metric_score = 0
            user_msgs = user_data.get("user_messages", 0)

            # Engagement points
            if user_msgs >= 51:
                metric_score += 5
            elif user_msgs >= 11:
                metric_score += 3
            elif user_msgs >= 1:
                metric_score += 1

            # Topic points
            if user_data.get("fitness_topic_initiator") is not None:
                metric_score += 2

            # Goal points
            if user_data.get("coaching_inquiry_count", 0) > 0:
                metric_score += 5
            if user_data.get("offer_mentioned_in_conv", False):
                metric_score += 1

            # Signup gets significant boost, potentially overriding other points for simplicity?
            if user_data.get("signup_recorded", False):
                # Let's make signup a high fixed score if not rated by AI
                metric_score = 15

            score = metric_score

        total_score += score
        scored_conversations_count += 1  # Count all conversations

    if scored_conversations_count == 0:
        return 0.0

    average_score = total_score / scored_conversations_count
    return average_score
# --- New Function for Overall Score --- END ---


# --- Main Page Logic --- START ---
# ... (Sidebar logic remains) ...

# Main content area
# ... (Title remains) ...

# Content based on selection
if selected_page == "Overview":
    st.header("📊 Global Metrics")

    # --- Calculate Overall Quality Score --- START ---
    overall_quality_score = calculate_overall_quality_score(
        st.session_state.conversation_metrics)
    # --- Calculate Overall Quality Score --- END ---

    # Calculate user metrics
    total_users = len(st.session_state.conversation_metrics)

    # Calculate active/inactive users using last_message_timestamp
    now = datetime.now(timezone.utc)  # Use UTC for consistency
    active_users = 0
    inactive_users = 0

    for user_id, user_data in st.session_state.conversation_metrics.items():
        # Use last_message_timestamp as the indicator of recent activity
        last_active_timestamp = user_data.get("last_message_timestamp")
        if last_active_timestamp:
            try:
                # Parse the timestamp and ensure it's UTC
                last_active = parse_timestamp(last_active_timestamp)

                if last_active:
                    # Check if active within last hour
                    time_diff = now - last_active
                    if time_diff.total_seconds() < ACTIVE_WINDOW:  # 1 hour in seconds
                        active_users += 1
                    else:
                        inactive_users += 1
                else:
                    # Handle case where timestamp is invalid
                    inactive_users += 1
            except Exception as e:
                # Catch any parsing errors
                st.error(f"Error parsing timestamp for user {user_id}: {e}")
                inactive_users += 1
        else:
            # If no last message timestamp, consider inactive
            inactive_users += 1

    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("User Stats")

        # Debug expander for User Stats calculations - ensure it's not nested in another expander
        with st.expander("User Stats Debug"):
            st.write("Raw Data:")
            st.write(
                f"Total conversations in metrics: {len(st.session_state.conversation_metrics)}")

            # Show active/inactive calculation details
            active_count = 0
            inactive_count = 0
            for user_id, user_data in st.session_state.conversation_metrics.items():
                conv_end = user_data.get("conversation_end_time")
                if conv_end:
                    try:
                        # Parse the timestamp
                        if isinstance(conv_end, str):
                            last_active = datetime.fromisoformat(
                                conv_end.replace('Z', '+00:00'))
                        else:
                            last_active = conv_end

                        # Ensure UTC
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(
                                tzinfo=timezone.utc)

                        # Calculate time difference
                        time_diff = now - last_active
                        minutes_diff = time_diff.total_seconds() / 60

                        st.write(f"User {user_id}:")
                        st.write(f"  - Last active: {last_active}")
                        st.write(
                            f"  - Minutes since last message: {minutes_diff:.1f}")
                        st.write(
                            f"  - Status: {'Active' if minutes_diff < 60 else 'Inactive'}")

                        if time_diff.total_seconds() < ACTIVE_WINDOW:
                            active_count += 1
                    except (ValueError, TypeError) as e:
                        st.write(
                            f"  - Error parsing timestamp for user {user_id}: {e}")
                        inactive_count += 1

            st.write("\nCalculated Totals:")
            st.write(f"Active Users (recounted): {active_count}")
            st.write(f"Inactive Users (recounted): {inactive_count}")

        # Display metrics
        st.metric("Total Users", total_users)
        st.metric("Active Users (1h)", active_users,
                  help="Users who have had a conversation in the last hour")
        st.metric("Inactive Users", inactive_users,
                  help="Users who haven't had a conversation in the last hour")

        # Add Overall Score display here or in a 4th column/new row
        st.metric("Overall Conversation Quality (Avg)", f"{overall_quality_score:.1f}",
                  help="Avg score based on engagement, goals & AI analysis (when available). Range varies.")

    with col2:
        st.subheader("Conversion Metrics")

        # Get total signups and inquiries
        total_signups = 0
        total_inquiries = 0
        total_offers = 0

        # Debug expander for Conversion Metrics - ensure it's not nested in another expander
        with st.expander("Conversion Metrics Debug"):
            st.write("Detailed Conversion Data:")
            for user_id, conv in st.session_state.conversation_metrics.items():
                # Track metrics for this user
                user_metrics = {
                    "signup": conv.get("signup_recorded", False),
                    "inquiries": conv.get("coaching_inquiry_count", 0),
                    "offer_shown": conv.get("offer_mentioned_in_conv", False)
                }

                # Update totals
                if user_metrics["signup"]:
                    total_signups += 1
                if user_metrics["inquiries"] > 0:
                    total_inquiries += 1
                if user_metrics["offer_shown"]:
                    total_offers += 1

                # Only show users with any conversion activity
                if any(user_metrics.values()):
                    st.write(f"\nUser {user_id}:")
                    st.write(f"  - Signed up: {user_metrics['signup']}")
                    st.write(
                        f"  - Inquiries made: {user_metrics['inquiries']}")
                    st.write(f"  - Offer shown: {user_metrics['offer_shown']}")

            st.write("\nTotals:")
            st.write(f"Total Signups: {total_signups}")
            st.write(f"Total Inquiries: {total_inquiries}")
            st.write(f"Total Offers Shown: {total_offers}")

        # Display metrics
        st.metric("Total Memberships Sold", total_signups,
                  help="Number of users who have signed up for membership")
        st.metric("Coaching Inquiries", total_inquiries,
                  help="Number of users who have inquired about coaching")

        # --- Add Expander for Inquiring Users --- START ---
        with st.expander(f"View {total_inquiries} Users Who Inquired"):
            inquiring_users_list = []
            for user_id, user_data in st.session_state.conversation_metrics.items():
                if user_data.get('coaching_inquiry_count', 0) > 0:
                    username = user_data.get("ig_username") or user_id
                    # Calculate status for indicator
                    is_active = False
                    last_active_timestamp = user_data.get(
                        "last_message_timestamp")
                    if last_active_timestamp:
                        try:
                            last_active_dt = parse_timestamp(
                                last_active_timestamp)
                            if last_active_dt:
                                time_diff = datetime.now(
                                    timezone.utc) - last_active_dt
                                if time_diff.total_seconds() < ACTIVE_WINDOW:
                                    is_active = True
                        except Exception:
                            pass
                    status_indicator = "🟢" if is_active else "🔴"
                    inquiring_users_list.append({
                        "id": user_id,
                        "username": username,
                        "status_indicator": status_indicator
                    })

            # Sort the list (e.g., by username)
            inquiring_users_list.sort(key=lambda x: x["username"])

            if inquiring_users_list:
                for user in inquiring_users_list:
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(
                            f"{user['status_indicator']} {user['username']}")
                    with cols[1]:
                        if st.button("View Profile", key=f"view_inquiry_{user['id']}", use_container_width=True):
                            st.session_state.view_profile = user['id']
                            st.rerun()
            else:
                st.info("No users found who have made inquiries.")
        # --- Add Expander for Inquiring Users --- END ---

        # Calculate and display conversion rate
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%",
                  help="Percentage of users who signed up after seeing an offer")

    with col3:
        st.subheader("Engagement Overview")
        total_messages = st.session_state.global_metrics.get(
            "total_messages", 0)
        user_messages = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        ai_messages = st.session_state.global_metrics.get(
            "total_ai_messages", 0)

        # Display metrics
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Response Rate", f"{total_response_rate:.1f}%",
                  help="Percentage of AI questions that received a user response")

    # Add Responder Categories section
    st.header("👥 Responder Categories")

    # Create tabs for different responder categories
    responder_tabs = st.tabs(
        ["High Responders", "Medium Responders", "Low Responders"])

    # Function to categorize users based on NEW thresholds
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
            # Users with 0 messages won't appear in these tabs anyway,
            # but good to handle the case.
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
    # Sorting by total messages keeps higher interaction users higher within activity status
    for responder_list in [high_responders, medium_responders, low_responders]:
        responder_list.sort(
            key=lambda x: (x["is_active"], x["total_message_count"]), reverse=True)

    # Modify the high responders tab
    with responder_tabs[0]:  # High Responders
        st.subheader(f"High Responders ({len(high_responders)})")
        if high_responders:
            selected_high_index = st.selectbox(
                "Select User",
                options=list(range(len(high_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{high_responders[i]['status_indicator']} {high_responders[i]['username']} - {high_responders[i]['user_message_count']} user msgs",
                key="high_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_high_button"):
                st.session_state.view_profile = high_responders[selected_high_index]['id']
                st.rerun()
        else:
            st.info("No high responders found")

    with responder_tabs[1]:  # Medium Responders
        st.subheader(f"Medium Responders ({len(medium_responders)})")
        if medium_responders:
            selected_medium_index = st.selectbox(
                "Select User",
                options=list(range(len(medium_responders))),
                # Update format_func to use USER messages
                format_func=lambda i: f"{medium_responders[i]['status_indicator']} {medium_responders[i]['username']} - {medium_responders[i]['user_message_count']} user msgs",
                key="medium_responder_select"
            )

            # Add a View Profile button
            if st.button("View Profile", key="view_medium_button"):
                st.session_state.view_profile = medium_responders[selected_medium_index]['id']
                st.rerun()
        else:
            st.info("No medium responders found")

    with responder_tabs[2]:  # Low Responders
        st.subheader(f"Low Responders ({len(low_responders)})")
        if low_responders:
            selected_low_index = st.selectbox(
                "Select User",
                options=list(range(len(low_responders))),
                # Update format_func to use USER messages
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

        # Create user info dict including status
        user_list.append({
            "id": user_id,
            "username": username,
            "message_count": message_count,
            "is_active": is_active,  # Store boolean for sorting
            "status_indicator": status_indicator  # Store indicator for display
        })

    # Sort users by active status first (descending), then by message count (descending)
    user_list.sort(key=lambda x: (
        x["is_active"], x["message_count"]), reverse=True)

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
            # Update format_func to include the status indicator
            format_func=lambda x: f"{x['status_indicator']} {x['username']} - {x['message_count']} messages"
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
elif selected_page == "AI Data Assistant":
    st.header("🤖 AI Data Assistant")
    st.info("Ask questions about your analytics data in natural language.")

    # Initialize chat history in session state
    if "ai_assistant_messages" not in st.session_state:
        st.session_state.ai_assistant_messages = []

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
You are a helpful data analyst assistant embedded in a Streamlit dashboard. Your task is to answer questions about Instagram follower interaction data based ONLY on the provided data context.

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
                {"role": "assistant", "content": "Sorry, I encountered an error."})  # Log simpler error

# Footer
st.markdown("---")
st.markdown("Analytics Dashboard | Reading from: " +
            os.path.abspath(ANALYTICS_FILE_PATH))
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Auto-refresh logic
if st.session_state.auto_refresh and not st.session_state.get('_refreshing', False):
    st.session_state._refreshing = True
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    st.session_state._refreshing = False

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
        message_text="Yes please! I'm particularly interested in weight loss.",
        message_type="user",
        timestamp=(current_time + timedelta(minutes=2)).isoformat()
    )

    # Add another AI response
    analytics.analyze_message(
        subscriber_id=test_user_id,
        message_text="Perfect! Here's a link to our program: cocospersonaltraining.com/online. It includes personalized workouts, nutrition guidance, and weekly check-ins. Would you like to get started?",
        message_type="ai",
        timestamp=(current_time + timedelta(minutes=3)).isoformat()
    )

    return "Test user added successfully!"


# Add test user button in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Testing Tools")
if st.sidebar.button("Add Test User"):
    result = add_test_user()
    st.sidebar.success(result)
    # Refresh the data
    st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
    st.rerun()

# New function to schedule a follow-up message


def schedule_automatic_followup(username, message, scheduled_time):
    """Schedule a follow-up message to be sent automatically at the specified time"""
    global SCHEDULED_FOLLOWUPS

    if username not in SCHEDULED_FOLLOWUPS:
        SCHEDULED_FOLLOWUPS[username] = []

    SCHEDULED_FOLLOWUPS[username].append({
        "message": message,
        "scheduled_time": scheduled_time,
        "created_at": datetime.now(timezone.utc),
        "status": "scheduled"
    })

    # Save scheduled follow-ups to a persistent store
    save_scheduled_followups()

    return True

# New function to check for and send scheduled follow-ups


def process_scheduled_followups():
    """Check for any scheduled follow-ups that are due and send them"""
    global SCHEDULED_FOLLOWUPS
    current_time = datetime.now(timezone.utc)

    # Load the latest scheduled follow-ups
    load_scheduled_followups()

    messages_sent = 0
    messages_to_send = []

    # First pass: identify messages to send
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        for i, msg_data in enumerate(messages):
            if msg_data["status"] == "scheduled" and msg_data["scheduled_time"] <= current_time:
                messages_to_send.append((username, i, msg_data))

    # Second pass: send messages (limited to prevent rate limiting)
    # Limit to 10 messages per processing cycle
    for username, index, msg_data in messages_to_send[:10]:
        try:
            # Get the followup module
            followup_module = sys.modules.get('followup_manager')
            if not followup_module:
                st.error("Follow-up manager not loaded")
                return False

            # Get the driver instance
            driver = followup_module.get_driver()
            if not driver:
                st.error("Instagram browser not available")
                return False

            # Send the message
            result = followup_module.send_follow_up_message(
                driver,
                username,
                msg_data["message"]
            )

            # Update status based on result
            if result.get("success", False):
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "sent"
                SCHEDULED_FOLLOWUPS[username][index]["sent_at"] = datetime.now(
                    timezone.utc)
                messages_sent += 1

                # Log the successful follow-up
                log_followup_success(username, msg_data["message"])
            else:
                SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
                SCHEDULED_FOLLOWUPS[username][index]["error"] = result.get(
                    "error", "Unknown error")

                # Log the failure
                log_followup_failure(
                    username, result.get("error", "Unknown error"))
        except Exception as e:
            SCHEDULED_FOLLOWUPS[username][index]["status"] = "failed"
            SCHEDULED_FOLLOWUPS[username][index]["error"] = str(e)
            log_followup_failure(username, str(e))

    # Save the updated status
    save_scheduled_followups()

    return messages_sent

# New function to toggle automatic follow-up mode


def toggle_auto_followup(enabled, username=None):
    """Enable or disable automatic follow-up globally or for a specific user"""
    global AUTO_FOLLOWUP_ENABLED

    if username is None:
        # Global toggle
        AUTO_FOLLOWUP_ENABLED = enabled
        return True
    else:
        # TODO: Implement per-user toggle if needed
        return True

# New function to save scheduled follow-ups


def save_scheduled_followups():
    """Save scheduled follow-ups to a JSON file"""
    # Convert datetime objects to strings for JSON serialization
    serializable_followups = {}
    for username, messages in SCHEDULED_FOLLOWUPS.items():
        serializable_followups[username] = []
        for msg in messages:
            serializable_msg = msg.copy()
            if isinstance(msg["scheduled_time"], datetime):
                serializable_msg["scheduled_time"] = msg["scheduled_time"].isoformat(
                )
            if "created_at" in msg and isinstance(msg["created_at"], datetime):
                serializable_msg["created_at"] = msg["created_at"].isoformat()
            if "sent_at" in msg and isinstance(msg["sent_at"], datetime):
                serializable_msg["sent_at"] = msg["sent_at"].isoformat()
            serializable_followups[username].append(serializable_msg)

    # Save to file
    with open("scheduled_followups.json", "w") as f:
        json.dump(serializable_followups, f, indent=2)

# New function to load scheduled follow-ups


def load_scheduled_followups():
    """Load scheduled follow-ups from a JSON file"""
    global SCHEDULED_FOLLOWUPS

    try:
        with open("scheduled_followups.json", "r") as f:
            serialized_followups = json.load(f)

        # Convert string timestamps back to datetime objects
        SCHEDULED_FOLLOWUPS = {}
        for username, messages in serialized_followups.items():
            SCHEDULED_FOLLOWUPS[username] = []
            for msg in messages:
                if isinstance(msg["scheduled_time"], str):
                    msg["scheduled_time"] = datetime.fromisoformat(
                        msg["scheduled_time"])
                if "created_at" in msg and isinstance(msg["created_at"], str):
                    msg["created_at"] = datetime.fromisoformat(
                        msg["created_at"])
                if "sent_at" in msg and isinstance(msg["sent_at"], str):
                    msg["sent_at"] = datetime.fromisoformat(msg["sent_at"])
                SCHEDULED_FOLLOWUPS[username].append(msg)
    except FileNotFoundError:
        # Initialize empty if file doesn't exist
        SCHEDULED_FOLLOWUPS = {}
    except Exception as e:
        st.error(f"Error loading scheduled follow-ups: {str(e)}")
        SCHEDULED_FOLLOWUPS = {}

# Function for logging follow-up success


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
    analytics.analyze_message
    subscriber_id = test_user_id,
    # ... (Responder Categories Tabs display) ...
