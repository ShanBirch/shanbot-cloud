import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import random
import logging
from typing import Dict, Any
from .analytics import load_analytics_data
from .utils import get_melbourne_time_str

# Import utilities
from app.dashboard_utils import (
    ensure_timezone,
    parse_timestamp,
    is_user_active,
    should_follow_up,
    analyze_engagement_level,
    get_smart_follow_up_timing,
    generate_follow_up_message,
    get_retry_delay,
    call_gemini_with_retries,
    ACTIVE_WINDOW
)

# Import follow-up service functions
from app.followup_service import (
    generate_ai_follow_up_message,
    schedule_automatic_followup,
    process_scheduled_followups,
    save_scheduled_followups,
    load_scheduled_followups,
    log_followup_success,
    log_followup_failure,
    toggle_auto_followup
)

logger = logging.getLogger(__name__)

# Analytics file path
ANALYTICS_FILE_PATH = "C:\\Users\\Shannon\\analytics_data.json"


def init_session_state():
    """Initialize session state variables."""
    if 'global_metrics' not in st.session_state:
        st.session_state.global_metrics = {}
        st.session_state.conversation_metrics = {}
        try:
            st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
            logger.info("Initial analytics data loaded into session state.")
        except Exception as e:
            st.error(f"Failed to load initial analytics data: {e}")
            logger.exception("Failed initial analytics data load.")

    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = False
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 60
    if 'view_profile' not in st.session_state:
        st.session_state.view_profile = None
    if 'followup_manager_loaded' not in st.session_state:
        st.session_state.followup_manager_loaded = False


def render_sidebar():
    """Render the sidebar controls."""
    st.sidebar.title("Shanbot Analytics")

    # Add refresh controls
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.session_state.auto_refresh = st.checkbox(
            "Auto Refresh", value=st.session_state.get('auto_refresh', False))
    with col2:
        if st.session_state.auto_refresh:
            st.session_state.refresh_interval = st.number_input(
                "Interval (s)",
                min_value=10,
                max_value=300,
                value=st.session_state.get('refresh_interval', 60)
            )

    # Add manual refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        try:
            st.session_state.global_metrics, st.session_state.conversation_metrics = load_analytics_data()
            st.success("Data refreshed successfully!")
            logger.info("Manual data refresh triggered.")
        except Exception as e:
            st.error(f"Failed to refresh data: {e}")
            logger.exception("Manual data refresh failed.")


def render_overview():
    """Render the overview page."""
    st.header("📊 Global Metrics")

    if not st.session_state.conversation_metrics:
        st.warning(
            "Conversation metrics data is not available. Check data loading.")
        return

    total_users = len(st.session_state.conversation_metrics)
    active_users = 0
    inactive_users = 0
    now = datetime.now(timezone.utc)

    for user_data in st.session_state.conversation_metrics.values():
        last_active_timestamp = user_data.get("last_message_timestamp")
        if is_user_active(last_active_timestamp):
            active_users += 1
        else:
            inactive_users += 1

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
        total_signups = sum(1 for data in st.session_state.conversation_metrics.values(
        ) if data.get("signup_recorded", False))
        total_inquiries = sum(1 for data in st.session_state.conversation_metrics.values(
        ) if data.get("coaching_inquiry_count", 0) > 0)
        total_offers = sum(1 for data in st.session_state.conversation_metrics.values(
        ) if data.get("offer_mentioned_in_conv", False))

        st.metric("Total Memberships Sold", total_signups)
        st.metric("Coaching Inquiries", total_inquiries)
        conversion_rate = (total_signups / total_offers *
                           100) if total_offers > 0 else 0
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%")

    with col3:
        st.subheader("Engagement Overview")
        global_total = st.session_state.global_metrics.get("total_messages", 0)
        global_user = st.session_state.global_metrics.get(
            "total_user_messages", 0)
        global_ai = st.session_state.global_metrics.get("total_ai_messages", 0)
        response_rate = (global_ai / global_user *
                         100) if global_user > 0 else 0

        st.metric("Total Messages", global_total)
        st.metric("User Messages", global_user)
        st.metric("AI Messages", global_ai)
        st.metric("Response Rate", f"{response_rate:.1f}%")


def main():
    """Main function to run the dashboard."""
    init_session_state()
    render_sidebar()

    # Navigation
    nav_options = ["Overview", "User Profiles", "Analysis Results",
                   "Batch Follow-up", "Scheduled Follow-ups", "AI Data Assistant"]
    selected_page = st.sidebar.radio("Navigation", nav_options)

    st.title(f"Shanbot Analytics - {selected_page}")

    if selected_page == "Overview":
        render_overview()
    # Add other page renderers as needed

    # Auto-refresh logic
    if st.session_state.get('auto_refresh', False) and not st.session_state.get('_refreshing', False):
        st.session_state._refreshing = True
        time.sleep(st.session_state.get('refresh_interval', 60))
        st.session_state._refreshing = False
        st.rerun()
    elif not st.session_state.get('auto_refresh', False):
        st.session_state._refreshing = False


if __name__ == "__main__":
    main()
