import streamlit as st
import time
from datetime import datetime, timezone, timedelta
import os
import sys
import logging

# Assuming conversation_analytics_integration is accessible for saving
from conversation_analytics_integration import analytics

# Import necessary utilities from dashboard_utils
from .dashboard_utils import (
    parse_timestamp,
    analyze_engagement_level,
    ACTIVE_WINDOW
)

# Import functions from followup_service
from .followup_service import (
    generate_ai_follow_up_message
)

# Need to import the original followup_manager for sending messages
# This implies followup_manager needs to be loaded/accessible globally
# or passed into the display function, which might complicate things.
# For now, assume it's loaded similarly to the original file.
# Setup path (might be redundant if main app does it, but safer)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

followup_manager = None


def load_followup_manager():  # Function to load the selenium manager
    global followup_manager
    try:
        followup_manager_path = os.path.join(parent_dir, "followup_manager.py")
        if not os.path.exists(followup_manager_path):
            st.error(
                f"followup_manager.py not found at {followup_manager_path}")
            return False
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        import importlib
        import followup_manager as fm
        importlib.reload(fm)
        followup_manager = fm
        logger.info(
            "Original followup_manager loaded successfully for sending.")
        return True
    except ImportError as e:
        st.error(
            f"Could not import followup_manager: {e}. Direct message sending disabled.")
        logger.error(f"ImportError loading followup_manager: {e}")
        return False
    except Exception as e:
        st.error(f"Unexpected error loading followup_manager: {e}")
        logger.error(f"Exception loading followup_manager: {e}", exc_info=True)
        return False


# Set up logging for this module
logger = logging.getLogger(__name__)

# Moved from analytics_dashboard.py


def display_conversation(selected_user):
    """Display a single conversation with a user, including profile, metrics, follow-up, and history."""

    # Ensure session state has the necessary data (might need explicit checks)
    if 'conversation_metrics' not in st.session_state or selected_user["id"] not in st.session_state.conversation_metrics:
        st.error(
            f"Could not find conversation data for user {selected_user.get('id', 'UNKNOWN')}. Please refresh data.")
        return

    user_data = st.session_state.conversation_metrics[selected_user["id"]]
    conversation_id = selected_user["id"]

    # --- Conversation Analysis Section ---
    if "conversation_rating" in user_data or "conversation_summary" in user_data:
        st.subheader("🔍 Conversation Analysis")
        rating = user_data.get("conversation_rating", "Not Analyzed")
        summary = user_data.get("conversation_summary", "No summary available")
        col1, col2 = st.columns([1, 3])
        with col1:
            rating_color = {
                "Hot Lead": "#ff9999", "Warm Lead": "#ffcc99", "Nurture": "#ffffcc",
                "Signup": "#ccffcc", "General Chat": "#e6e6e6", "Stalled": "#ccccff",
                "Inquiry Only": "#e6ccff", "Analysis Failed": "#ffcccc"
            }.get(rating, "#ffffff")
            st.markdown(
                f"<div style='padding:10px;border-radius:5px;margin:5px 0;background-color:{rating_color};text-align:center;font-weight:bold;'>{rating}</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(
                f"<div style='padding:10px;border-radius:5px;margin:5px 0;background-color:#f5f5f5;'>{summary}</div>", unsafe_allow_html=True)
        st.markdown("---")

    # --- User Profile Section ---
    with st.expander("🧑‍💼 User Profile", expanded=True):
        has_profile_bio = "client_analysis" in user_data and "profile_bio" in user_data.get(
            "client_analysis", {})
        if has_profile_bio:
            profile_bio = user_data["client_analysis"]["profile_bio"]
            col1, col2 = st.columns([1, 2])
            with col1:
                name = profile_bio.get("PERSON NAME") or profile_bio.get(
                    "person_name") or user_data.get("ig_username", "Unknown")
                st.subheader(f"{name}")
                st.caption(f"@{user_data.get('ig_username', conversation_id)}")
                if "PERSONALITY TRAITS" in profile_bio and profile_bio["PERSONALITY TRAITS"]:
                    st.write("**Personality:**")
                    traits_html = " • ".join(
                        [f"<span style='background-color:#f0f7ff;padding:2px 6px;border-radius:10px;margin:2px;display:inline-block;'>{trait}</span>" for trait in profile_bio["PERSONALITY TRAITS"] if trait])
                    st.markdown(traits_html, unsafe_allow_html=True)
            with col2:
                if "INTERESTS" in profile_bio and profile_bio["INTERESTS"]:
                    st.write("**Interests:**")
                    interests_html = " ".join(
                        [f"<span style='background-color:#e6f3ff;padding:3px 8px;border-radius:12px;margin:3px;display:inline-block;'>{interest}</span>" for interest in profile_bio["INTERESTS"] if interest])
                    st.markdown(interests_html, unsafe_allow_html=True)
                if "LIFESTYLE" in profile_bio and profile_bio["LIFESTYLE"] not in ["Unknown", ""]:
                    st.write("**Lifestyle:**")
                    st.write(profile_bio["LIFESTYLE"])
            if "conversation_starters" in profile_bio and profile_bio["conversation_starters"]:
                st.write("💬 **Conversation Starters:**")
                for starter in profile_bio["conversation_starters"]:
                    if starter and starter not in ["Unknown", ""]:
                        st.markdown(f"- {starter}")
        else:
            st.subheader(f"{user_data.get('ig_username', 'Unknown User')}")
            st.caption(f"@{user_data.get('ig_username', conversation_id)}")
            st.info("No detailed profile information available yet.")

    if not has_profile_bio:
        with st.expander("ℹ️ How to get profile data"):
            st.write("Profile data is generated by `followersbot2.py`.")
            st.write("1. Ensure user is in `instagram_followers.txt`")
            st.write("2. Run `followersbot2.py` to analyze profile.")
            st.write("3. Refresh dashboard to view data.")

    # --- User Metrics Section ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("User Info")
        st.write(f"**Username:** {user_data.get('ig_username', 'N/A')}")
        st.write(f"**User ID:** {selected_user['id']}")
        st.write(
            f"**First Seen:** {user_data.get('conversation_start_time', 'N/A')}")
        message_count = user_data.get("user_messages", 0)
        responder_category = "Low Responder"
        category_emoji = "🔄"
        if message_count >= 51:
            responder_category, category_emoji = "High Responder", "🔥"
        elif message_count >= 11:
            responder_category, category_emoji = "Medium Responder", "📊"
        st.write(
            f"**Responder Category:** {category_emoji} {responder_category}")
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
                    st.write(f"**Last Active:** {minutes_ago:.1f} minutes ago")
                else:
                    st.write("**Status:** 🔴 Inactive")
                    st.write("**Last Active:** Invalid timestamp")
            except Exception as e:
                logger.error(
                    f"Error parsing timestamp for user {selected_user['id']}: {e}")
                st.write("**Status:** 🔴 Inactive")
                st.write("**Last Active:** Error")
        else:
            st.write("**Status:** 🔴 Inactive")
            st.write("**Last Active:** Never")
    with col2:
        st.subheader("Engagement Metrics")
        total_msgs = user_data.get("total_messages", 0)
        user_msgs = user_data.get("user_messages", 0)
        ai_msgs = user_data.get("ai_messages", 0)
        st.metric("Total Messages", total_msgs)
        st.metric("User Messages", user_msgs)
        st.metric("AI Messages", ai_msgs)
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
        st.write("**Topics Mentioned:**")
        topics = [topic for topic, key in {"Vegan": "vegan_topic_mentioned", "Weight Loss": "weight_loss_mentioned",
                                           "Muscle Gain": "muscle_gain_mentioned"}.items() if user_data.get(key, False)]
        st.write(", ".join(topics) if topics else "None")

    # --- Follow-up Management Section ---
    st.subheader("Follow-up Management")
    last_active = user_data.get("conversation_end_time") or user_data.get(
        "last_message_timestamp")  # Use backup time
    needs_follow_up = False
    hours_inactive = 0
    follow_up_description = "Not yet determined"
    hours_until_followup = 0

    if last_active:
        last_active_dt = parse_timestamp(last_active)
        if last_active_dt:
            now = datetime.now(timezone.utc)
            time_diff = now - last_active_dt
            hours_inactive = time_diff.total_seconds() / 3600
            message_count = user_data.get("user_messages", 0)
            # Define timing rules based on responder category (can be moved to config/utils)
            if message_count >= 51:
                required_inactive_hours, follow_up_description, days_between_followups = 48, "48h (High)", 7
            elif message_count >= 11:
                required_inactive_hours, follow_up_description, days_between_followups = 120, "5d (Medium)", 10
            else:
                required_inactive_hours, follow_up_description, days_between_followups = 168, "7d (Low)", 14

            follow_up_time = last_active_dt + \
                timedelta(hours=required_inactive_hours)
            time_until_followup = follow_up_time - now
            hours_until_followup = time_until_followup.total_seconds() / 3600

            if hours_inactive >= required_inactive_hours:
                last_follow_up = user_data.get("last_follow_up_date")
                if last_follow_up:
                    last_follow_up_dt = parse_timestamp(last_follow_up)
                    if last_follow_up_dt and (now - last_follow_up_dt).days >= days_between_followups:
                        needs_follow_up = True
                else:  # No previous follow-up, eligible now
                    needs_follow_up = True
        else:
            logger.warning(
                f"Could not parse last_active time '{last_active}' for user {conversation_id}")
            hours_inactive = -1  # Indicate error parsing time

    # --- Follow-up Status Display ---
    status_cols = st.columns([2, 1])
    with status_cols[0]:
        if hours_inactive == -1:
            st.warning(
                "⚠️ Could not determine follow-up status due to invalid time data.")
        elif last_active is None:
            st.warning("⚠️ No conversation history available.")
        elif hours_inactive < 1.0:
            st.success("✅ Active user - no follow-up needed.")
        elif needs_follow_up:
            st.info(
                f"⏰ Eligible for follow-up (inactive {hours_inactive:.1f} hours). Timing: {follow_up_description}")
        else:
            if hours_until_followup > 0:
                time_display = f"{hours_until_followup/24:.1f} days" if hours_until_followup > 24 else f"{hours_until_followup:.1f} hours"
                st.warning(
                    f"⌛ Inactive {hours_inactive:.1f} hours. Follow-up in {time_display}. ({follow_up_description})")
            else:  # Inactive, but recently followed up
                st.info(
                    f"⌛ Inactive {hours_inactive:.1f} hours. Recently followed up.")

    # --- Follow-up Generation/Sending Tools ---
    st.subheader("Follow-up Message Tools")
    # Initialize session state for generated messages if needed
    if "generated_follow_ups" not in st.session_state:
        st.session_state.generated_follow_ups = {}

    # Unique key per user
    user_followup_key = f"followup_{selected_user['id']}"

    # Auto-generate if eligible and not already generated/sent
    if user_followup_key not in st.session_state.generated_follow_ups and needs_follow_up:
        try:
            logger.info(
                f"Auto-generating follow-up for eligible user {conversation_id}")
            follow_up_message = generate_ai_follow_up_message(user_data)
            st.session_state.generated_follow_ups[user_followup_key] = {
                "message": follow_up_message,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "auto_generated": True,
                "edited": False
            }
            # Don't rerun here, let it display naturally
        except Exception as e:
            logger.error(
                f"Error auto-generating follow-up for {conversation_id}: {e}")

    # Display generated message and controls
    if user_followup_key in st.session_state.generated_follow_ups:
        current_data = st.session_state.generated_follow_ups[user_followup_key]
        message = current_data["message"]
        generated_at = current_data["generated_at"]
        is_auto = current_data.get("auto_generated", False)

        st.success(
            f"{'Automatically generated' if is_auto else 'Generated'} follow-up message:")
        edited_message = st.text_area(
            "Edit message before sending:", value=message, height=100, key=f"edit_{user_followup_key}")
        st.caption(f"Generated: {generated_at}")

        if edited_message != message:
            st.session_state.generated_follow_ups[user_followup_key]["message"] = edited_message
            st.session_state.generated_follow_ups[user_followup_key]["edited"] = True
            # Mark as manually edited
            st.session_state.generated_follow_ups[user_followup_key]["auto_generated"] = False
            # Rerun might be needed if you want immediate reflection of the edit status change elsewhere
            # st.rerun()

    # Buttons (Regenerate/Generate and Send)
    col1_btn, col2_btn = st.columns(2)
    with col1_btn:
        generate_button_text = "Regenerate Message" if user_followup_key in st.session_state.generated_follow_ups else "Generate Follow-up Message"
        if st.button(generate_button_text, key=f"gen_{user_followup_key}"):
            with st.spinner("Generating follow-up message..."):
                try:
                    follow_up_message = generate_ai_follow_up_message(
                        user_data)
                    st.session_state.generated_follow_ups[user_followup_key] = {
                        "message": follow_up_message,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "auto_generated": False,  # Manually generated
                        "edited": False
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating message: {e}")

    with col2_btn:
        if user_followup_key in st.session_state.generated_follow_ups:
            if st.button("Send Message Now", key=f"send_{user_followup_key}"):
                username = user_data.get("ig_username")
                current_message = st.session_state.generated_follow_ups[user_followup_key]["message"]
                was_edited = st.session_state.generated_follow_ups[user_followup_key]["edited"]

                if not username:
                    st.error("No Instagram username found for this user")
                else:
                    st.subheader("Message Sending Process")
                    debug_container = st.empty()
                    debug_container.info(
                        f"Sending to @{username}: '{current_message[:30]}...'")

                    # Load the selenium manager if not already loaded
                    if not followup_manager:
                        if not load_followup_manager():
                            debug_container.error(
                                "Failed to load Selenium manager. Cannot send message.")
                            st.stop()

                    # Proceed with sending using the selenium manager
                    try:
                        with st.spinner(f"Sending message to {username}..."):
                            # --- Selenium Interaction ---
                            # Get driver, login if needed, send message
                            driver = followup_manager.get_driver(
                                reuse=True)  # Try to reuse existing driver
                            if not driver:
                                debug_container.info(
                                    "Setting up new browser instance...")
                                driver = followup_manager.setup_driver()

                            if not driver:
                                debug_container.error(
                                    "Failed to setup browser.")
                                st.stop()

                            # Login check/attempt (using functions assumed to be in followup_manager)
                            if not followup_manager.is_logged_in(driver):
                                debug_container.info(
                                    "Logging into Instagram...")
                                login_success = followup_manager.login_to_instagram(
                                    driver,
                                    # Assumes these are defined in followup_manager
                                    followup_manager.INSTAGRAM_USERNAME,
                                    followup_manager.INSTAGRAM_PASSWORD
                                )
                                if not login_success:
                                    debug_container.error(
                                        "Login failed. Attempting to send anyway...")
                                else:
                                    debug_container.success(
                                        "Logged in successfully.")
                            else:
                                debug_container.success("Already logged in.")

                            # Send message
                            debug_container.info(f"Sending message now...")
                            result = followup_manager.send_follow_up_message(
                                driver, username, current_message)
                            # --- End Selenium Interaction ---

                            if result.get("success", False):
                                debug_container.success(
                                    "Message sent successfully!")

                                # Update analytics data (should be done carefully)
                                user_data["last_follow_up_date"] = datetime.now(
                                    timezone.utc).isoformat()
                                user_data["follow_ups_sent"] = user_data.get(
                                    "follow_ups_sent", 0) + 1
                                if "follow_up_history" not in user_data:
                                    user_data["follow_up_history"] = []
                                user_data["follow_up_history"].append({
                                    "date": datetime.now(timezone.utc).isoformat(),
                                    "message": current_message,
                                    "edited": was_edited,
                                    "sent_via_instagram": True,
                                    "sent_early": not needs_follow_up,
                                    "engagement_level": analyze_engagement_level(user_data)["level"]
                                })

                                # Save the updated metrics back to session state
                                st.session_state.conversation_metrics[selected_user["id"]] = user_data
                                # Trigger export/save of the main analytics data
                                analytics.export_analytics()
                                logger.info(
                                    f"Follow-up sent to {username} and analytics saved.")

                                # Remove from generated messages state
                                del st.session_state.generated_follow_ups[user_followup_key]
                                st.success(
                                    f"Message sent to {username} successfully!")
                                time.sleep(2)  # Pause before rerun
                                st.rerun()

                            else:
                                st.error(
                                    f"Failed to send message: {result.get('error', 'Unknown error')}")
                                debug_container.error(
                                    f"Failed: {result.get('error', 'Unknown error')}")

                    except Exception as e:
                        st.error(f"Error during message sending: {str(e)}")
                        logger.exception(
                            f"Error sending message to {username}")
                        import traceback
                        debug_container.error(
                            f"Error details: {traceback.format_exc()}")

    if not needs_follow_up and hours_inactive > 1.0 and hours_inactive != -1:
        st.info(
            "Note: User doesn't meet criteria for automated follow-up, but you can send manually.")

    # --- Follow-up History Section ---
    follow_up_history = user_data.get("follow_up_history", [])
    if follow_up_history:
        st.subheader("Follow-up History")
        # Show most recent first
        for i, entry in enumerate(reversed(follow_up_history)):
            st.markdown(
                f"**{i+1}. Sent:** {entry.get('date', 'Unknown')[:16]} {' (Edited)' if entry.get('edited') else ''}")
            st.info(entry.get("message", "No message content"))
            # Add other details like 'sent_via_instagram', 'sent_early' if needed
            st.markdown("---")

    # --- Conversation History Section ---
    st.subheader("Conversation History")
    history = user_data.get("conversation_history", [])
    client_analysis = user_data.get("client_analysis", {})
    profile_bio = client_analysis.get("profile_bio", {})

    # Display Profile Summary (if available, consider moving to top profile section)
    # ... (This section seems redundant if profile is shown above) ...

    # Display Generated Initial Comment (if available)
    generated_comment = client_analysis.get("generated_comment")
    if generated_comment:
        st.markdown(
            "<small>🤖 Generated Initial Comment (from Profile Analysis)</small>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='padding:10px;border-radius:5px;margin:5px 0;background-color:#e3f2fd;border-left:5px solid #2196f3;'><strong>AI</strong>: {generated_comment}</div>", unsafe_allow_html=True)

    # Display Recorded Conversation History
    if history:
        for msg in history:
            is_ai = msg.get("type") == "ai"
            with st.container():
                timestamp = msg.get("timestamp", "")
                if timestamp:
                    try:
                        dt = parse_timestamp(timestamp)  # Use util function
                        timestamp = dt.strftime(
                            "%Y-%m-%d %H:%M") if dt else "Invalid Date"
                    except Exception:
                        timestamp = "Invalid Date Format"

                st.markdown(f"""
                    <div style='padding:8px 12px;border-radius:15px;margin:5px 0;max-width:75%;float:{"right" if is_ai else "left"};clear:both;background-color:{"#DCF8C6" if is_ai else "#FFFFFF"};border:1px solid {"#c5eeb4" if is_ai else "#e0e0e0"};'>
                    <small style='color:#888;font-size:0.75em;'>{timestamp}</small><br>
                    {msg.get("text", "")}
                    </div>
                """, unsafe_allow_html=True)
        # Add a clear float element after messages if needed
        st.markdown("<div style='clear:both;'></div>", unsafe_allow_html=True)

    elif not generated_comment:
        st.info("No conversation history available.")
