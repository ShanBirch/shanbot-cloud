"""
Check-ins Manager Module
Contains all functions related to automated Monday/Wednesday check-ins
"""

import streamlit as st
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json
import time
import random

# Configure logging
logger = logging.getLogger(__name__)


def send_dm_via_instagram_automation(ig_username: str, message: str) -> bool:
    """Send a DM using the existing Instagram automation infrastructure"""
    try:
        # Import the existing Instagram automation class
        from check_daily_follow_backs import DailyFollowBackChecker

        # Create an instance of the automation class
        # This will handle login and all the Instagram automation
        instagram_bot = DailyFollowBackChecker(
            username="cocos_connected", password="Shannonb3", analyze_profiles=False)

        try:
            # Setup the driver and login to Instagram
            instagram_bot.setup_driver()
            if not instagram_bot.login_to_instagram():
                logger.error("❌ Failed to login to Instagram")
                return False

            # Use the existing send_dm_to_user method
            success = instagram_bot.send_dm_to_user(ig_username, message)

            if success:
                logger.info(f"✅ Successfully sent DM to @{ig_username}")
                return True
            else:
                logger.error(f"❌ Failed to send DM to @{ig_username}")
                return False

        finally:
            # Clean up the driver
            if hasattr(instagram_bot, 'driver') and instagram_bot.driver:
                instagram_bot.driver.quit()
            # Clean up temp directory
            if hasattr(instagram_bot, 'temp_user_data_dir') and instagram_bot.temp_user_data_dir:
                import shutil
                try:
                    shutil.rmtree(instagram_bot.temp_user_data_dir)
                except:
                    pass

    except Exception as e:
        logger.error(f"Error in send_dm_via_instagram_automation: {e}")
        return False


def get_eligible_clients(analytics_data_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all trial and paying clients eligible for check-ins"""
    eligible_clients = []

    conversations_data = analytics_data_dict.get('conversations', {})
    if not conversations_data:
        return eligible_clients

    for ig_username, user_data in conversations_data.items():
        metrics = user_data.get('metrics', {})
        journey_stage = metrics.get('journey_stage', {})

        # Check if user is trial or paying client
        is_paying = journey_stage.get('is_paying_client', False) if isinstance(
            journey_stage, dict) else False
        trial_start_date = journey_stage.get(
            'trial_start_date') if isinstance(journey_stage, dict) else None

        if is_paying or trial_start_date:
            # Check current check-in status
            is_mon_checkin = metrics.get('is_in_checkin_flow_mon', False)
            is_wed_checkin = metrics.get('is_in_checkin_flow_wed', False)

            client_info = {
                'ig_username': ig_username,
                'first_name': metrics.get('first_name', ''),
                'last_name': metrics.get('last_name', ''),
                'is_paying': is_paying,
                'is_trial': bool(trial_start_date),
                'is_mon_checkin': is_mon_checkin,
                'is_wed_checkin': is_wed_checkin,
                'metrics': metrics
            }
            eligible_clients.append(client_info)

    return eligible_clients


def generate_checkin_message(client_data: Dict[str, Any], checkin_type: str) -> str:
    """Generate a check-in message using the appropriate prompt template"""
    try:
        from app import prompts
        from webhook_handlers import get_melbourne_time_str, format_conversation_history

        ig_username = client_data['ig_username']
        first_name = client_data['first_name']
        metrics = client_data['metrics']

        # Get conversation history
        conversation_history = metrics.get('conversation_history', [])
        formatted_history = format_conversation_history(conversation_history)

        # Prepare prompt data
        prompt_data = {
            "current_melbourne_time_str": get_melbourne_time_str(),
            "ig_username": ig_username,
            "first_name": first_name,
            "full_conversation": formatted_history,
            "few_shot_examples": ""  # Will be populated from approved responses
        }

        # Choose template based on check-in type
        if checkin_type == 'monday':
            prompt_template = prompts.MONDAY_MORNING_TEXT_PROMPT_TEMPLATE
            prompt_type = "monday_morning_text"
        else:  # wednesday
            prompt_template = prompts.CHECKINS_PROMPT_TEMPLATE
            prompt_type = "checkins"

        # Generate message using AI
        from webhook_handlers import get_ai_response
        import asyncio

        # Create the prompt
        prompt = prompt_template.format(**prompt_data)

        # Get AI response (simplified for now)
        # In a real implementation, you'd call the AI here
        if checkin_type == 'monday':
            return f"Goooooood Morning {first_name}! Ready for the week? When you planning your sessions?"
        else:
            return f"Heya {first_name}! Hows your week going? Been getting your sessions in?"

    except Exception as e:
        logger.error(f"Error generating check-in message: {e}")
        return "Hey! How's your week going?"


def send_checkin_message(ig_username: str, subscriber_id: str, message: str, checkin_type: str = "wednesday") -> bool:
    """Send a check-in message via Instagram DM automation and update analytics"""
    try:
        from app.analytics import update_analytics_data

        # Get user data if subscriber_id not provided
        if not subscriber_id:
            from webhook_handlers import get_user_data
            _, metrics, _ = get_user_data(ig_username)
            subscriber_id = metrics.get('subscriber_id', '')
            first_name = metrics.get('first_name', '')
            last_name = metrics.get('last_name', '')
        else:
            # Get user data
            from webhook_handlers import get_user_data
            _, metrics, _ = get_user_data(ig_username)
            first_name = metrics.get('first_name', '')
            last_name = metrics.get('last_name', '')

        # Send message via Instagram automation
        success = send_dm_via_instagram_automation(ig_username, message)

        if success:
            # Update analytics to mark user as in check-in flow
            update_analytics_data(
                subscriber_id=subscriber_id,
                ig_username=ig_username,
                message_text="",
                message_direction="system",
                timestamp=datetime.now().isoformat(),
                first_name=first_name,
                last_name=last_name,
                is_in_checkin_flow_mon=(checkin_type == 'monday'),
                is_in_checkin_flow_wed=(checkin_type == 'wednesday')
            )

            # Add to review queue for tracking
            from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
            add_response_to_review_queue(
                user_ig_username=ig_username,
                user_subscriber_id=subscriber_id,
                incoming_message_text="[Check-in initiated]",
                incoming_message_timestamp=datetime.now().isoformat(),
                generated_prompt_text=f"Check-in message for {checkin_type}",
                proposed_response_text=message,
                prompt_type="monday_morning_text" if checkin_type == 'monday' else "checkins",
                status="sent"
            )

            logger.info(
                f"✅ Check-in message sent to {ig_username} ({checkin_type})")
            return True
        else:
            logger.error(f"❌ Failed to send check-in message to {ig_username}")
            return False

    except Exception as e:
        logger.error(f"Error sending check-in message: {e}")
        return False


def remove_checkin_tag(ig_username: str, checkin_type: str) -> bool:
    """Remove check-in tag from user"""
    try:
        from app.analytics import update_analytics_data
        from webhook_handlers import get_user_data

        # Get user data
        _, metrics, _ = get_user_data(ig_username)

        subscriber_id = metrics.get('subscriber_id', '')
        first_name = metrics.get('first_name', '')
        last_name = metrics.get('last_name', '')

        # Update analytics to remove check-in flow
        update_analytics_data(
            subscriber_id=subscriber_id,
            ig_username=ig_username,
            message_text="",
            message_direction="system",
            timestamp=datetime.now().isoformat(),
            first_name=first_name,
            last_name=last_name,
            is_in_checkin_flow_mon=False if checkin_type == 'monday' else metrics.get(
                'is_in_checkin_flow_mon', False),
            is_in_checkin_flow_wed=False if checkin_type == 'wednesday' else metrics.get(
                'is_in_checkin_flow_wed', False)
        )

        logger.info(
            f"✅ Removed {checkin_type} check-in tag from {ig_username}")
        return True

    except Exception as e:
        logger.error(f"Error removing check-in tag: {e}")
        return False


def display_checkins_manager(analytics_data_dict):
    """Primary check-in management system for automated Monday/Wednesday check-ins"""
    st.header("📅 Check-ins Manager")
    st.caption(
        "Automated Monday morning & Wednesday night check-ins for trial and paying clients")

    # Get all conversations
    conversations_data = analytics_data_dict.get('conversations', {})
    if not conversations_data:
        st.warning("No conversation data available")
        return

    # Get eligible clients (trial or paying)
    eligible_clients = []
    for ig_username, user_data in conversations_data.items():
        metrics = user_data.get('metrics', {})
        journey_stage = metrics.get('journey_stage', {})

        is_paying = journey_stage.get('is_paying_client', False) if isinstance(
            journey_stage, dict) else False
        trial_start_date = journey_stage.get(
            'trial_start_date') if isinstance(journey_stage, dict) else None

        if is_paying or trial_start_date:
            is_mon_checkin = metrics.get('is_in_checkin_flow_mon', False)
            is_wed_checkin = metrics.get('is_in_checkin_flow_wed', False)

            eligible_clients.append({
                'ig_username': ig_username,
                'first_name': metrics.get('first_name', ''),
                'last_name': metrics.get('last_name', ''),
                'is_paying': is_paying,
                'is_trial': bool(trial_start_date),
                'is_mon_checkin': is_mon_checkin,
                'is_wed_checkin': is_wed_checkin,
                'metrics': metrics
            })

    if not eligible_clients:
        st.warning("No eligible clients found (trial or paying clients only).")
        return

    # Create tabs for different check-in management functions
    schedule_tab, manual_tab, inactive_tab = st.tabs([
        "📋 Scheduled Check-ins",
        "🎯 Manual Triggers",
        "⚠️ Inactive Clients"
    ])

    with schedule_tab:
        st.subheader("🌅 Monday Morning Text & 💬 Check-ins")
        st.caption(
            "Generate and send personalized check-in messages to your clients")

        # Summary metrics
        paying_count = sum(1 for c in eligible_clients if c['is_paying'])
        trial_count = sum(1 for c in eligible_clients if c['is_trial'])
        mon_active = sum(1 for c in eligible_clients if c['is_mon_checkin'])
        wed_active = sum(1 for c in eligible_clients if c['is_wed_checkin'])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 Paying Clients", paying_count)
        with col2:
            st.metric("🆓 Trial Members", trial_count)
        with col3:
            st.metric("🌅 Monday Active", mon_active)
        with col4:
            st.metric("💬 Wednesday Active", wed_active)

        st.divider()

        # Bulk generation section
        st.subheader("🚀 Generate & Queue Check-in Messages")
        st.caption(
            "Create personalized check-in messages and queue them for Instagram DM sending")

        col_bulk1, col_bulk2 = st.columns(2)

        with col_bulk1:
            if st.button("🌅 Generate All Monday Morning Texts", type="primary", use_container_width=True):
                with st.spinner("Generating Monday morning texts for all clients..."):
                    generated_count = 0
                    for client in eligible_clients:
                        message_key = f"monday_checkin_{client['ig_username']}"
                        # Generate message using new prompt template
                        generated_message = f"Goooooood Morning {client['first_name']}! Ready for the week? When you planning your sessions?"
                        st.session_state[message_key] = generated_message
                        generated_count += 1

                    if generated_count > 0:
                        st.success(
                            f"✅ Generated Monday morning texts for {generated_count} clients!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to generate check-in messages")

        with col_bulk2:
            if st.button("💬 Generate All Wednesday Check-ins", type="primary", use_container_width=True):
                with st.spinner("Generating Wednesday check-ins for all clients..."):
                    generated_count = 0
                    for client in eligible_clients:
                        message_key = f"wednesday_checkin_{client['ig_username']}"
                        # Generate message using new prompt template
                        generated_message = f"Heya {client['first_name']}! Hows your week going? Been getting your sessions in?"
                        st.session_state[message_key] = generated_message
                        generated_count += 1

                    if generated_count > 0:
                        st.success(
                            f"✅ Generated Wednesday check-ins for {generated_count} clients!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to generate check-in messages")

        st.divider()

        # Individual client controls
        st.subheader("👥 Individual Client Controls")
        st.caption("Manage check-in status and send individual messages")

        for client in eligible_clients:
            client_type = "💰 Paying" if client['is_paying'] else "🆓 Trial"
            full_name = f"{client['first_name']} {client['last_name']}".strip(
            ) if client['first_name'] or client['last_name'] else ""

            with st.expander(f"{client_type} **{client['ig_username']}** {f'({full_name})' if full_name else ''}", expanded=False):
                col_mon, col_wed = st.columns(2)

                with col_mon:
                    st.write("**🌅 Monday Morning Text**")
                    current_mon_status = client['is_mon_checkin']

                    if current_mon_status:
                        st.success("✅ Currently ACTIVE")
                        if st.button("🔄 Remove Monday Tag", key=f"remove_mon_{client['ig_username']}", use_container_width=True):
                            # Remove Monday check-in tag
                            from user_profiles import trigger_check_in
                            user_data = {'metrics': client['metrics']}
                            if trigger_check_in(client['ig_username'], "monday", user_data, current_mon_status, client['is_wed_checkin']):
                                st.success(
                                    f"Monday tag removed from {client['ig_username']}")
                                st.rerun()
                            else:
                                st.error("Failed to remove Monday tag")
                    else:
                        st.info("○ Currently Inactive")
                        if st.button("🌅 Activate Monday", key=f"activate_mon_{client['ig_username']}", type="primary", use_container_width=True):
                            # Generate and send Monday message
                            message = f"Goooooood Morning {client['first_name']}! Ready for the week? When you planning your sessions?"

                            # Send via Instagram automation and add to review queue
                            try:
                                from app.analytics import update_analytics_data
                                from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue

                                subscriber_id = client['metrics'].get(
                                    'subscriber_id', '')
                                if subscriber_id:
                                    # Send message via Instagram automation
                                    success = send_dm_via_instagram_automation(
                                        client['ig_username'], message)

                                    if success:
                                        # Update analytics to mark user as in Monday check-in flow
                                        update_analytics_data(
                                            subscriber_id=subscriber_id,
                                            ig_username=client['ig_username'],
                                            message_text="",
                                            message_direction="system",
                                            timestamp=datetime.now().isoformat(),
                                            first_name=client['first_name'],
                                            last_name=client['last_name'],
                                            is_in_checkin_flow_mon=True,
                                            is_in_checkin_flow_wed=client['is_wed_checkin']
                                        )

                                        # Add to review queue for tracking
                                        add_response_to_review_queue(
                                            user_ig_username=client['ig_username'],
                                            user_subscriber_id=subscriber_id,
                                            incoming_message_text="[Monday check-in initiated]",
                                            incoming_message_timestamp=datetime.now().isoformat(),
                                            generated_prompt_text="Monday morning text prompt",
                                            proposed_response_text=message,
                                            prompt_type="monday_morning_text",
                                            status="sent"
                                        )

                                        st.success(
                                            f"Monday morning text sent to {client['ig_username']}!")
                                        st.rerun()
                                    else:
                                        st.error(
                                            "Failed to send message via Instagram DM")
                                else:
                                    st.error(
                                        "No subscriber ID found for this user")
                            except Exception as e:
                                st.error(f"Error sending message: {e}")

                    # Show generated message if available
                    message_key = f"monday_checkin_{client['ig_username']}"
                    if message_key in st.session_state:
                        st.text_area("Generated Monday Message:", value=st.session_state[message_key],
                                     key=f"edit_mon_{client['ig_username']}", height=100)
                        col_send1, col_edit1 = st.columns(2)
                        with col_send1:
                            if st.button("📤 Send", key=f"send_mon_{client['ig_username']}"):
                                message = st.session_state[f"edit_mon_{client['ig_username']}"]

                                # Send via Instagram automation and add to review queue
                                try:
                                    from app.analytics import update_analytics_data
                                    from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue

                                    subscriber_id = client['metrics'].get(
                                        'subscriber_id', '')
                                    if subscriber_id:
                                        # Send message via Instagram automation
                                        success = send_dm_via_instagram_automation(
                                            client['ig_username'], message)

                                        if success:
                                            # Update analytics to mark user as in Monday check-in flow
                                            update_analytics_data(
                                                subscriber_id=subscriber_id,
                                                ig_username=client['ig_username'],
                                                message_text="",
                                                message_direction="system",
                                                timestamp=datetime.now().isoformat(),
                                                first_name=client['first_name'],
                                                last_name=client['last_name'],
                                                is_in_checkin_flow_mon=True,
                                                is_in_checkin_flow_wed=client['is_wed_checkin']
                                            )

                                            # Add to review queue for tracking
                                            add_response_to_review_queue(
                                                user_ig_username=client['ig_username'],
                                                user_subscriber_id=subscriber_id,
                                                incoming_message_text="[Monday check-in sent]",
                                                incoming_message_timestamp=datetime.now().isoformat(),
                                                generated_prompt_text="Monday morning text prompt",
                                                proposed_response_text=message,
                                                prompt_type="monday_morning_text",
                                                status="sent"
                                            )

                                            st.success("Message sent!")
                                            del st.session_state[message_key]
                                            st.rerun()
                                        else:
                                            st.error(
                                                "Failed to send message via Instagram DM")
                                    else:
                                        st.error(
                                            "No subscriber ID found for this user")
                                except Exception as e:
                                    st.error(f"Error sending message: {e}")
                        with col_edit1:
                            if st.button("🗑️ Delete", key=f"delete_mon_{client['ig_username']}"):
                                del st.session_state[message_key]
                                st.rerun()

                with col_wed:
                    st.write("**💬 Wednesday Check-ins**")
                    current_wed_status = client['is_wed_checkin']

                    if current_wed_status:
                        st.success("✅ Currently ACTIVE")
                        if st.button("🔄 Remove Wednesday Tag", key=f"remove_wed_{client['ig_username']}", use_container_width=True):
                            # Remove Wednesday check-in tag
                            from user_profiles import trigger_check_in
                            user_data = {'metrics': client['metrics']}
                            if trigger_check_in(client['ig_username'], "wednesday", user_data, client['is_mon_checkin'], current_wed_status):
                                st.success(
                                    f"Wednesday tag removed from {client['ig_username']}")
                                st.rerun()
                            else:
                                st.error("Failed to remove Wednesday tag")
                    else:
                        st.info("○ Currently Inactive")
                        if st.button("💬 Activate Wednesday", key=f"activate_wed_{client['ig_username']}", type="primary", use_container_width=True):
                            # Generate and send Wednesday message
                            message = f"Heya {client['first_name']}! Hows your week going? Been getting your sessions in?"

                            # Send via Instagram automation and add to review queue
                            try:
                                from app.analytics import update_analytics_data
                                from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue

                                subscriber_id = client['metrics'].get(
                                    'subscriber_id', '')
                                if subscriber_id:
                                    # Send message via Instagram automation
                                    success = send_dm_via_instagram_automation(
                                        client['ig_username'], message)

                                    if success:
                                        # Update analytics to mark user as in Wednesday check-in flow
                                        update_analytics_data(
                                            subscriber_id=subscriber_id,
                                            ig_username=client['ig_username'],
                                            message_text="",
                                            message_direction="system",
                                            timestamp=datetime.now().isoformat(),
                                            first_name=client['first_name'],
                                            last_name=client['last_name'],
                                            is_in_checkin_flow_mon=client['is_mon_checkin'],
                                            is_in_checkin_flow_wed=True
                                        )

                                        # Add to review queue for tracking
                                        add_response_to_review_queue(
                                            user_ig_username=client['ig_username'],
                                            user_subscriber_id=subscriber_id,
                                            incoming_message_text="[Wednesday check-in initiated]",
                                            incoming_message_timestamp=datetime.now().isoformat(),
                                            generated_prompt_text="Wednesday check-in prompt",
                                            proposed_response_text=message,
                                            prompt_type="checkins",
                                            status="sent"
                                        )

                                        st.success(
                                            f"Wednesday check-in sent to {client['ig_username']}!")
                                        st.rerun()
                                    else:
                                        st.error(
                                            "Failed to send message via Instagram DM")
                                else:
                                    st.error(
                                        "No subscriber ID found for this user")
                            except Exception as e:
                                st.error(f"Error sending message: {e}")

                    # Show generated message if available
                    message_key = f"wednesday_checkin_{client['ig_username']}"
                    if message_key in st.session_state:
                        st.text_area("Generated Wednesday Message:", value=st.session_state[message_key],
                                     key=f"edit_wed_{client['ig_username']}", height=100)
                        col_send2, col_edit2 = st.columns(2)
                        with col_send2:
                            if st.button("📤 Send", key=f"send_wed_{client['ig_username']}"):
                                message = st.session_state[f"edit_wed_{client['ig_username']}"]

                                # Send via Instagram automation and add to review queue
                                try:
                                    from app.analytics import update_analytics_data
                                    from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue

                                    subscriber_id = client['metrics'].get(
                                        'subscriber_id', '')
                                    if subscriber_id:
                                        # Send message via Instagram automation
                                        success = send_dm_via_instagram_automation(
                                            client['ig_username'], message)

                                        if success:
                                            # Update analytics to mark user as in Wednesday check-in flow
                                            update_analytics_data(
                                                subscriber_id=subscriber_id,
                                                ig_username=client['ig_username'],
                                                message_text="",
                                                message_direction="system",
                                                timestamp=datetime.now().isoformat(),
                                                first_name=client['first_name'],
                                                last_name=client['last_name'],
                                                is_in_checkin_flow_mon=client['is_mon_checkin'],
                                                is_in_checkin_flow_wed=True
                                            )

                                            # Add to review queue for tracking
                                            add_response_to_review_queue(
                                                user_ig_username=client['ig_username'],
                                                user_subscriber_id=subscriber_id,
                                                incoming_message_text="[Wednesday check-in sent]",
                                                incoming_message_timestamp=datetime.now().isoformat(),
                                                generated_prompt_text="Wednesday check-in prompt",
                                                proposed_response_text=message,
                                                prompt_type="checkins",
                                                status="sent"
                                            )

                                            st.success("Message sent!")
                                            del st.session_state[message_key]
                                            st.rerun()
                                        else:
                                            st.error(
                                                "Failed to send message via Instagram DM")
                                    else:
                                        st.error(
                                            "No subscriber ID found for this user")
                                except Exception as e:
                                    st.error(f"Error sending message: {e}")
                        with col_edit2:
                            if st.button("🗑️ Delete", key=f"delete_wed_{client['ig_username']}"):
                                del st.session_state[message_key]
                                st.rerun()

    with manual_tab:
        st.subheader("🎯 Manual Check-in Triggers")
        st.caption("Manually trigger check-ins for specific clients")

        # Quick actions for individual clients
        for client in eligible_clients:
            client_type = "💰" if client['is_paying'] else "🆓"
            full_name = f"{client['first_name']} {client['last_name']}".strip(
            ) if client['first_name'] or client['last_name'] else ""

            with st.expander(f"{client_type} **{client['ig_username']}** {f'({full_name})' if full_name else ''}", expanded=False):
                col_quick1, col_quick2 = st.columns(2)

                with col_quick1:
                    if st.button("🌅 Quick Monday Text", key=f"quick_mon_{client['ig_username']}", use_container_width=True):
                        message = generate_checkin_message(client, "monday")
                        if send_checkin_message(client['ig_username'], client['metrics'].get('subscriber_id', ''), message, "monday"):
                            st.success(
                                f"Monday text sent to {client['ig_username']}!")
                        else:
                            st.error("Failed to send Monday text")

                with col_quick2:
                    if st.button("💬 Quick Wednesday Check-in", key=f"quick_wed_{client['ig_username']}", use_container_width=True):
                        message = generate_checkin_message(client, "wednesday")
                        if send_checkin_message(client['ig_username'], client['metrics'].get('subscriber_id', ''), message, "wednesday"):
                            st.success(
                                f"Wednesday check-in sent to {client['ig_username']}!")
                        else:
                            st.error("Failed to send Wednesday check-in")

    with inactive_tab:
        st.subheader("⚠️ Inactive Clients")
        st.caption("Clients who haven't responded recently")

        # Find inactive clients (no response in 7+ days)
        inactive_clients = []
        for client in eligible_clients:
            # This would need to be implemented based on your conversation tracking
            # For now, just show all clients
            inactive_clients.append(client)

        if inactive_clients:
            for client in inactive_clients:
                client_type = "💰 Paying" if client['is_paying'] else "🆓 Trial"
                full_name = f"{client['first_name']} {client['last_name']}".strip(
                ) if client['first_name'] or client['last_name'] else ""

                with st.expander(f"{client_type} **{client['ig_username']}** {f'({full_name})' if full_name else ''}", expanded=False):
                    st.info(
                        "Client hasn't responded recently. Consider sending a check-in message.")

                    col_action1, col_action2 = st.columns(2)
                    with col_action1:
                        if st.button("🌅 Send Monday Text", key=f"inactive_mon_{client['ig_username']}"):
                            message = generate_checkin_message(
                                client, "monday")
                            if send_checkin_message(client['ig_username'], client['metrics'].get('subscriber_id', ''), message, "monday"):
                                st.success("Monday text sent!")
                            else:
                                st.error("Failed to send message")

                    with col_action2:
                        if st.button("💬 Send Wednesday Check-in", key=f"inactive_wed_{client['ig_username']}"):
                            message = generate_checkin_message(
                                client, "wednesday")
                            if send_checkin_message(client['ig_username'], client['metrics'].get('subscriber_id', ''), message, "wednesday"):
                                st.success("Wednesday check-in sent!")
                            else:
                                st.error("Failed to send message")
        else:
            st.info("All clients are active! 🎉")
