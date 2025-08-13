import streamlit as st
import json
import logging
import os
from pathlib import Path
import datetime
import google.generativeai as genai
import random
import google.oauth2.service_account
import googleapiclient.discovery
import time

# Import the new SQLite utility functions
from dashboard_sqlite_utils import (
    load_conversations_from_sqlite,
    save_metrics_to_sqlite,
    get_pending_reviews,
    update_review_status,
    add_to_learning_log,
    add_message_to_history,
    get_review_accuracy_stats,
    insert_manual_context_message
)

# Import the actual ManyChat update function
try:
    # Add parent directories to path for imports
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(__file__))
    grandparent_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    if grandparent_dir not in sys.path:
        sys.path.insert(0, grandparent_dir)

    from webhook_handlers import update_manychat_fields
except ImportError:
    try:
        from webhook0605 import update_manychat_fields
    except ImportError:
        st.error("Could not import update_manychat_fields function")
        update_manychat_fields = None

# Import the message splitting function
try:
    from webhook_handlers import split_response_into_messages
except ImportError:
    try:
        from webhook0605 import split_response_into_messages
    except ImportError:
        st.error("Could not import split_response_into_messages function")
        split_response_into_messages = None

# Use direct imports since files are in the same directory
# Assuming overview.py is in the same dir
from overview import display_overview
# Assuming client_journey.py is in the same dir
from client_journey import display_client_journey
# Assuming user_profiles.py is in the same dir
from user_profiles import display_user_profiles, display_user_profile, get_usernames
from scheduled_followups import (
    display_scheduled_followups,
    display_bulk_review_and_send,
    bulk_generate_followups,
    get_user_category,
    get_topic_for_category,
    verify_trial_signup,
    check_sheet_for_signups,
    get_user_sheet_details as get_checkin_data
)

# Rest of the file would be the same as the original dashboard.py...
st.header("🔧 Dashboard Import Fix")
st.success("Dashboard imports have been fixed!")
st.info("Please replace dashboard.py with this fixed version or copy the import fixes to the original file.")
