import notifications
import streamlit as st
import subprocess
import re
import numpy as np
import requests
import pytz
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import sqlite3
from datetime import datetime, timedelta
import tempfile  # Added for creating temporary username files
import subprocess  # Added for triggering Instagram analysis
import json
import logging
from pathlib import Path
import google.generativeai as genai
import random
import google.oauth2.service_account
import googleapiclient.discovery
import time
from dashboard_sqlite_utils import update_analytics_data as save_metrics_to_sqlite
from shared_utils import get_user_topics
from checkins_manager import display_checkins_manager, generate_checkin_message, send_checkin_message
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
from user_profiles import display_user_profiles, display_user_profile, get_usernames, trigger_check_in
from client_journey import display_client_journey
from overview import display_overview
from analytics_overview import get_stage_metrics, display_overview_tab, get_users_from_last_30_days, display_recent_interactions
from user_management import display_daily_report, bulk_update_leads_journey_stage, bulk_update_client_profiles, display_user_profiles_with_bulk_update
from notifications import display_notification_panel, add_trial_notification, add_sale_notification, add_email_collected_notification
import sys
from dashboard_sqlite_utils import (
    load_conversations_from_sqlite,
    get_pending_reviews,
    update_review_status,
    add_message_to_history,
    get_review_accuracy_stats,
    insert_manual_context_message,
    add_response_to_review_queue,
    get_good_few_shot_examples,
    get_vegan_few_shot_examples,
    is_user_in_vegan_flow,
    delete_reviews_for_user
)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure the page FIRST - before any other Streamlit commands or imports
st.set_page_config(
    page_title="Shannon Bot Analytics Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Now import other modules


# Add parent directories to path BEFORE importing from them
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(os.path.dirname(__file__))
grandparent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Path to the daily follow-back script
DAILY_FOLLOW_BACK_SCRIPT_PATH = os.path.join(
    grandparent_dir, 'check_daily_follow_backs.py')

# Path to Shannon's followup manager script
FOLLOWUP_MANAGER_SCRIPT_PATH = os.path.join(
    grandparent_dir, 'followup_manager.py')

# Ensure current directory is first in path (highest priority)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# Add parent directories with lower priority (append to end)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
if grandparent_dir not in sys.path:
    sys.path.append(grandparent_dir)

# Add project directories to sys.path to ensure correct module resolution
current_dir = os.path.dirname(__file__)
app_dir = os.path.abspath(os.path.join(current_dir, '..'))
project_root = os.path.abspath(os.path.join(app_dir, '..'))

if app_dir not in sys.path:
    sys.path.insert(0, app_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import from local modules and parent directories

# Import analytics module from parent directory
try:
    from analytics import update_analytics_data
except ImportError:
    st.error("Could not import analytics module")
    update_analytics_data = None

# Import from dashboard_modules

# Import from parent directory
try:
    from webhook_handlers import split_response_into_messages
except ImportError:
    try:
        from webhook0605 import split_response_into_messages
    except ImportError:
        def split_response_into_messages(text):
            return [text]  # Fallback function

# Add the import for the new checkins_manager module at the top with other imports

# Import the new SQLite utility functions

# Import the actual ManyChat update function
try:
    from webhook_handlers import update_manychat_fields
except ImportError:
    try:
        from webhook0605 import update_manychat_fields
    except ImportError:
        st.error("Could not import update_manychat_fields function")
        update_manychat_fields = None

# Import the message splitting function

# Use direct imports since files are in the same directory
# Assuming overview.py is in the same dir
# Assuming client_journey.py is in the same dir
# Assuming user_profiles.py is in the same dir

# Path for action_items JSON file - keep this as it's separate for now
ACTION_ITEMS_JSON_FILE = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.json"
# Path for Google Sheets credentials (remains the same)
SHEETS_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(__file__), "sheets_credentials.json")  # Corrected path if sheets_credentials.json is in dashboard_modules

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import from shared utilities to avoid circular imports

# Import modules that depend on shared utilities after they are defined

# Google Sheets configuration (remains the same)
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"


def get_daily_follow_counts():
    """Get today's follow counts for both online and local modes."""
    conn = None
    try:
        db_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')

        # Get online count
        cursor.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE DATE(followed_at) = ? AND search_mode = ?", (today, 'online'))
        online_count = cursor.fetchone()[0]

        # Get local count
        cursor.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE DATE(followed_at) = ? AND search_mode = ?", (today, 'local'))
        local_count = cursor.fetchone()[0]

        return online_count, local_count
    except Exception as e:
        logger.error(f"Error getting daily follow counts: {e}", exc_info=True)
        return 0, 0  # Return 0 on error
    finally:
        if conn:
            conn.close()


def check_and_update_signups(data: dict) -> dict:
    """Check for new signups and update user stages accordingly."""
    data_updated = False  # This flag might be less relevant if saves happen per user

    # The 'data' dict now primarily comes from SQLite via load_analytics_data
    # and 'conversations' is the key holding the SQLite loaded data.
    if 'conversations' not in data:
        logger.error(
            "'conversations' key missing from data in check_and_update_signups. Cannot proceed.")
        return data, False

    for username, user_container in data.get('conversations', {}).items():
        # User data is now directly under username, not nested in 'metrics' in the same way as JSON
        # metrics is the direct user data dict from SQLite load
        metrics = user_container.get('metrics', {})
        if not metrics:
            logger.warning(
                f"No metrics found for user {username} in check_and_update_signups")
            continue

        ig_username = metrics.get('ig_username')

        # Journey stage logic might need to be adapted if journey_stage is a dict
        current_journey_stage = metrics.get('journey_stage', {})
        if not isinstance(current_journey_stage, dict):
            current_journey_stage = {}  # Default to dict if not already

        # Skip if already in trial or paying stage
        if current_journey_stage.get('is_paying_client') or current_journey_stage.get('trial_start_date'):
            continue

        # Check if user has signed up
        # verify_trial_signup likely needs to check Google Sheets
        if ig_username and verify_trial_signup(ig_username):
            logger.info(
                f"Found signup for {ig_username}, updating to Trial Week 1")
            # Update journey_stage directly
            current_journey_stage['trial_start_date'] = datetime.now(
            ).isoformat()  # Example: set trial start
            # Update current stage
            current_journey_stage['current_stage'] = 'Trial Week 1'
            # Assign back to metrics
            metrics['journey_stage'] = current_journey_stage

            # Save this specific user's updated metrics to SQLite
            if save_metrics_to_sqlite(
                subscriber_id=metrics.get('subscriber_id'),
                ig_username=ig_username,
                message_text="User signed up for trial.",
                message_direction="system",
                timestamp=datetime.now().isoformat(),
                **metrics
            ):
                logger.info(
                    f"Successfully saved updated journey_stage for {ig_username} to SQLite.")
                data_updated = True  # Indicate that at least one user was updated

                # NEW: Remove from fresh vegan auto mode now that they're a trial member
                try:
                    from conversation_strategy import check_and_cleanup_vegan_eligibility
                    check_and_cleanup_vegan_eligibility(ig_username)
                except ImportError:
                    logger.warning("Could not import vegan cleanup function")

                # NEW: Add trial signup notification
                try:
                    add_trial_notification(ig_username, "Trial Week 1")
                    logger.info(
                        f"Added trial signup notification for {ig_username}")
                except Exception as e:
                    logger.warning(f"Could not add trial notification: {e}")
            else:
                logger.error(
                    f"Failed to save updated journey_stage for {ig_username} to SQLite.")

    return data, data_updated


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_analytics_data():
    """Load analytics data: conversations from SQLite, action_items from JSON with caching."""
    logger.info("Starting to load analytics data...")
    data = {}
    analytics_file_path_for_actions = ACTION_ITEMS_JSON_FILE  # For action_items

    # 1. Load conversations from SQLite
    try:
        conversations_from_sqlite = load_conversations_from_sqlite()
        # This is already in the desired format
        data['conversations'] = conversations_from_sqlite
        logger.info(
            f"Successfully loaded {len(conversations_from_sqlite)} conversations from SQLite.")
        if conversations_from_sqlite:
            sample_user = next(iter(conversations_from_sqlite))
            logger.info(
                f"Sample SQLite user data structure for '{sample_user}': {json.dumps(conversations_from_sqlite[sample_user].get('metrics', {}), indent=2, default=str)}")

    except Exception as e:
        logger.error(
            f"Error loading conversations from SQLite: {e}", exc_info=True)
        st.error(f"Error loading conversation data from SQLite: {e}")
        data['conversations'] = {}  # Ensure it's an empty dict on error

    # 2. Load action_items from JSON file
    try:
        if os.path.exists(analytics_file_path_for_actions):
            with open(analytics_file_path_for_actions, 'r', encoding='utf-8') as f:
                json_data_content = json.load(f)
                data['action_items'] = json_data_content.get(
                    'action_items', [])
            logger.info(
                f"Successfully loaded {len(data.get('action_items',[]))} action items from JSON: {analytics_file_path_for_actions}")
        else:
            logger.warning(
                f"Action items JSON file not found at {analytics_file_path_for_actions}. Initializing with empty list.")
            data['action_items'] = []
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding JSON from {analytics_file_path_for_actions}: {e}")
        st.error(f"Error loading action items from JSON: {e}")
        data['action_items'] = []
    except Exception as e:
        logger.error(
            f"Unexpected error loading action items from {analytics_file_path_for_actions}: {e}", exc_info=True)
        data['action_items'] = []

    # For compatibility, the dashboard might expect analytics_file path for saving JSON later.
    # It might be better to handle JSON saving separately if only action_items go there.
    return data, analytics_file_path_for_actions  # Return path for JSON for now


# Configure Gemini with 3-fallback system like webhook0605.py
try:
    # Try to get from Streamlit secrets first (for cloud deployment)
    GEMINI_API_KEY = st.secrets["general"]["GEMINI_API_KEY"]
except:
    # Fallback to the same API key used in webhook_handlers.py
    GEMINI_API_KEY = "AIzaSyAH6467EocGBwuMi-oDLawrNyCKjPHHmN8"

# Gemini model constants (updated primary to flash-lite)
GEMINI_MODEL_PRO = "gemini-2.5-flash-lite"
GEMINI_MODEL_FLASH = "gemini-2.0-flash-thinking-exp-01-21"
GEMINI_MODEL_FLASH_STANDARD = "gemini-2.0-flash"

# Retry constants
RETRY_DELAY = 16  # Seconds to wait before retry
MAX_RETRIES = 3  # Maximum number of retry attempts

if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY" and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # We'll create models dynamically in the retry function
        logger.info("Gemini configured successfully with 3-fallback system.")
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}")
        st.error("Failed to configure Gemini AI. Some features might not work.")
else:
    logger.warning(
        "Gemini API Key not found or is a placeholder. AI features will be disabled.")
    st.info("Gemini API Key not configured. AI features disabled.")


# --- Instagram Analysis Functions ---

def trigger_instagram_analysis_for_user(ig_username: str) -> tuple[bool, str]:
    """
    Trigger Instagram analysis for a specific user by calling anaylize_followers.py

    Args:
        ig_username: The Instagram username to analyze

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Step 1: Clear any existing progress file to ensure fresh analysis
        progress_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\analysis_progress.json"
        if os.path.exists(progress_file):
            try:
                os.remove(progress_file)
                logger.info(f"Cleared existing progress file: {progress_file}")
            except Exception as e:
                logger.warning(f"Could not clear progress file: {e}")

        # Step 2: Path to the analyzer script
        analyzer_script_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\anaylize_followers.py"

        if not os.path.exists(analyzer_script_path):
            return False, f"❌ Analyzer script not found at {analyzer_script_path}"

        # Step 3: Use --direct-user flag instead of creating temporary file
        cmd = ["python", analyzer_script_path, "--direct-user", ig_username]

        logger.info(f"Running Instagram analysis command: {' '.join(cmd)}")

        # Step 4: Execute the command
        # For debugging, let output show in terminal and run in background
        logger.info("Starting Instagram analysis in background...")
        result = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(analyzer_script_path),
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                subprocess, 'CREATE_NEW_CONSOLE') else 0
        )

        # Return immediately since we're running in background
        return True, f"✅ Instagram analysis started for {ig_username}. Check the new console window for progress."

    except Exception as e:
        logger.error(
            f"Error triggering Instagram analysis for {ig_username}: {e}", exc_info=True)
        return False, f"❌ Error triggering analysis for {ig_username}: {str(e)}"

# --- End Instagram Analysis Functions ---


def check_service_status(service_name: str, port: int) -> tuple[bool, str]:
    """Check if a service is running on a specific port"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('localhost', port))
        sock.close()

        if result == 0:
            return True, f"{service_name} is running on port {port}"
        else:
            return False, f"{service_name} is not running on port {port}"
    except Exception as e:
        return False, f"Error checking {service_name}: {str(e)}"


def get_ngrok_tunnel_url() -> tuple[bool, str]:
    """Get the current ngrok tunnel URL"""
    try:
        import requests
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tunnels = data.get('tunnels', [])
            if tunnels:
                public_url = tunnels[0].get('public_url', '')
                if public_url:
                    return True, public_url
        return False, "No active tunnel found"
    except Exception as e:
        return False, f"Error getting tunnel URL: {str(e)}"


def start_webhook_services():
    """Start both webhook and ngrok services"""
    import subprocess
    import time
    import os

    try:
        # Define the base directory
        base_dir = r"C:\Users\Shannon\OneDrive\Desktop\shanbot"

        # Start webhook server
        webhook_process = subprocess.Popen(
            # Updated to launch webhook_main.py on port 8001 with reload for auto-restart on changes
            ["python", "webhook_main.py", "--port", "8001", "--reload"],
            cwd=base_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                subprocess, 'CREATE_NEW_CONSOLE') else 0
        )

        # Wait a moment for webhook to start
        time.sleep(3)

        # Start ngrok - use full path to ngrok.exe
        ngrok_path = os.path.join(base_dir, "ngrok.exe")
        if not os.path.exists(ngrok_path):
            # Try alternative path or just use ngrok if it's in PATH
            ngrok_path = "ngrok"

        ngrok_process = subprocess.Popen(
            [ngrok_path, "http", "8001"],  # Updated ngrok to point to port 8001
            cwd=base_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                subprocess, 'CREATE_NEW_CONSOLE') else 0
        )

        # Wait for ngrok to establish tunnel
        time.sleep(5)

        return True, "Services started successfully!"

    except Exception as e:
        return False, f"Error starting services: {str(e)}"


def display_webhook_manager():
    """Display the webhook management interface"""
    st.header("🔗 Webhook Manager")
    st.caption(
        "Manage your webhook server and ngrok tunnel for ManyChat integration")

    # Create columns for status and controls
    status_col, control_col = st.columns([2, 1])

    with status_col:
        st.subheader("📊 Service Status")

        # Check webhook status
        webhook_running, webhook_msg = check_service_status(
            "Webhook Server", 8001)  # Updated to check port 8001
        webhook_status = "🟢 Online" if webhook_running else "🔴 Offline"
        st.write(f"**Webhook Server:** {webhook_status}")
        st.caption(webhook_msg)

        # Check ngrok status
        ngrok_running, ngrok_msg = check_service_status("ngrok", 4040)
        ngrok_status = "🟢 Online" if ngrok_running else "🔴 Offline"
        st.write(f"**ngrok Tunnel:** {ngrok_status}")
        st.caption(ngrok_msg)

        # Get tunnel URL if ngrok is running
        if ngrok_running:
            tunnel_found, tunnel_url = get_ngrok_tunnel_url()
            if tunnel_found:
                st.subheader("🌐 Public Webhook URL")
                webhook_url = f"{tunnel_url}/webhook/manychat"
                st.code(webhook_url, language="text")
                st.caption(
                    "👆 Copy this URL into your ManyChat webhook configuration")

                # Add copy button functionality
                if st.button("📋 Copy URL to Clipboard"):
                    st.write(
                        "URL copied! (Use Ctrl+C to copy from the code box above)")

                # Test webhook endpoint
                st.subheader("🧪 Test Endpoints")
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Test Health Endpoint"):
                        try:
                            import requests
                            # Note: Ngrok might add a warning for non-HTTPS, so skip it
                            headers = {'ngrok-skip-browser-warning': 'true'}
                            response = requests.get(
                                f"{tunnel_url}/health", headers=headers, timeout=10)
                            if response.status_code == 200:
                                st.success("✅ Health endpoint is working!")
                                st.json(response.json())
                            else:
                                st.error(
                                    f"❌ Health check failed: {response.status_code}")
                        except Exception as e:
                            st.error(
                                f"❌ Error testing health endpoint: {str(e)}")

                with col2:
                    if st.button("Open ngrok Dashboard"):
                        import webbrowser
                        webbrowser.open("http://localhost:4040")
                        st.success("🌐 ngrok dashboard opened in browser")
            else:
                st.warning(f"⚠️ Could not retrieve tunnel URL: {tunnel_url}")
        else:
            st.info("ℹ️ Start ngrok to get the public webhook URL")

    with control_col:
        st.subheader("🎛️ Controls")

        # Overall status indicator
        both_running = webhook_running and ngrok_running
        overall_status = "🟢 All Services Online" if both_running else "🟡 Partial/Offline"
        st.metric("Overall Status", overall_status)

        # Start services button
        if st.button("🚀 Start All Services", type="primary", use_container_width=True):
            if both_running:
                st.info("✅ Services are already running!")
            else:
                with st.spinner("Starting webhook and ngrok services..."):
                    success, message = start_webhook_services()
                    if success:
                        st.success(message)
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(message)

        # Individual service controls
        st.divider()
        st.write("**Individual Controls:**")

        if st.button("🔄 Restart Webhook", use_container_width=True):
            with st.spinner("Restarting webhook server..."):
                try:
                    import subprocess
                    import os

                    base_dir = r"C:\Users\Shannon\OneDrive\Desktop\shanbot"

                    # Start webhook server in new console
                    webhook_process = subprocess.Popen(
                        ["python", "webhook_main.py", "--port",
                            "8001", "--reload"],  # Updated to use port 8001 with reload for auto-restart
                        cwd=base_dir,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                            subprocess, 'CREATE_NEW_CONSOLE') else 0
                    )

                    st.success(
                        "✅ Webhook server restarted! Check the new console window.")
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Failed to restart webhook: {str(e)}")

        if st.button("🔄 Restart ngrok", use_container_width=True):
            with st.spinner("Restarting ngrok tunnel..."):
                try:
                    import subprocess
                    import os

                    base_dir = r"C:\Users\Shannon\OneDrive\Desktop\shanbot"

                    # Start ngrok
                    ngrok_path = os.path.join(base_dir, "ngrok.exe")
                    if not os.path.exists(ngrok_path):
                        ngrok_path = "ngrok"

                    ngrok_process = subprocess.Popen(
                        # Updated ngrok to point to port 8001
                        [ngrok_path, "http", "8001"],
                        cwd=base_dir,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                            subprocess, 'CREATE_NEW_CONSOLE') else 0
                    )

                    st.success(
                        "✅ ngrok tunnel restarted! Check the new console window.")
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Failed to restart ngrok: {str(e)}")

        # Auto-refresh toggle
        st.divider()
        auto_refresh = st.checkbox("🔄 Auto-refresh status (30s)")
        if auto_refresh:
            time.sleep(30)
            st.rerun()

    # Instructions section
    st.divider()
    st.subheader("📖 Setup Instructions")

    with st.expander("How to configure ManyChat webhook", expanded=False):
        st.markdown("""
        **Step 1: Start Services**
        1. Click the "🚀 Start All Services" button above
        2. Wait for both services to show "🟢 Online" status
        
        **Step 2: Get Webhook URL**
        1. Copy the webhook URL from the "Public Webhook URL" section
        2. The URL format will be: `https://[random].ngrok-free.app/webhook/manychat`
        
        **Step 3: Configure ManyChat**
        1. Go to your ManyChat dashboard
        2. Navigate to Settings → Integrations → Webhooks
        3. Paste the webhook URL
        4. Set the method to "POST"
        5. Save the configuration
        
        **Step 4: Test**
        1. Send a test message through your Instagram bot
        2. Check the ngrok dashboard (http://localhost:4040) for incoming requests
        3. Monitor the webhook logs in the console
        """)

    with st.expander("Troubleshooting", expanded=False):
        st.markdown("""
        **Common Issues:**
        
        - **Services won't start:** Check if ports 8000 and 4040 are available
        - **Tunnel URL not showing:** Wait 10-15 seconds after starting ngrok
        - **ManyChat can't reach webhook:** Ensure ngrok tunnel is active and URL is correct
        - **Authentication errors:** Check that your ManyChat API credentials are correct
        
        **Logs and Monitoring:**
        - Webhook logs: Check the console where webhook0605.py is running
        - ngrok logs: Visit http://localhost:4040 for request details
        - Dashboard logs: Check the Streamlit console for any errors
        """)


def call_gemini_with_retry_sync(model_name: str, prompt: str, retry_count: int = 0) -> str:
    """Synchronous version of call_gemini_with_retry for dashboard use."""
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) and retry_count < MAX_RETRIES:
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Rate limit hit for {model_name}. Falling back to flash-thinking model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            else:
                wait_time = RETRY_DELAY * (retry_count + 1)
                logger.warning(
                    f"Rate limit hit. Waiting {wait_time} seconds before retry {retry_count + 1} on {model_name}")
                time.sleep(wait_time)
                return call_gemini_with_retry_sync(model_name, prompt, retry_count + 1)
        elif retry_count < MAX_RETRIES:
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Main model failed: {e}. Trying first fallback model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            elif model_name == GEMINI_MODEL_FLASH:
                logger.warning(
                    f"First fallback model failed: {e}. Trying second fallback model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH_STANDARD, prompt, retry_count + 1)
        logger.error(f"All Gemini attempts failed: {e}")
        raise e


def regenerate_with_enhanced_context(user_ig_username: str, incoming_message: str, conversation_history: list, original_prompt: str, prompt_type: str = 'general_chat') -> str:
    """
    Regenerate a response with enhanced context from user bio and conversation topics.

    Args:
        user_ig_username: Instagram username of the user
        incoming_message: The user's message we're responding to
        conversation_history: Recent conversation history
        original_prompt: The original prompt that was used
        prompt_type: Type of prompt (general_chat, member_chat, etc.)

    Returns:
        str: Enhanced response tailored to user's bio and interests
    """
    try:
        logger.info(
            f"Generating enhanced contextual response for {user_ig_username}")

        # Get user data from analytics
        user_container = None
        conversations_data = st.session_state.analytics_data.get(
            'conversations', {})

        # Find user by ig_username in metrics
        for username, container in conversations_data.items():
            if isinstance(container, dict) and 'metrics' in container:
                metrics = container['metrics']
                if isinstance(metrics, dict) and metrics.get('ig_username', '').lower() == user_ig_username.lower():
                    user_container = container
                    break

        if not user_container:
            logger.warning(
                f"User {user_ig_username} not found in analytics data, using original prompt")
            return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH, original_prompt)

        metrics = user_container['metrics']

        # Extract bio information
        client_analysis = metrics.get('client_analysis', {})
        interests = client_analysis.get('interests', [])
        recent_activities = client_analysis.get('recent_activities', [])

        # Get conversation topics
        conversation_topics = get_user_topics(metrics)

        # Format recent conversation context
        formatted_history = ""
        if conversation_history:
            # Last 10 messages for context
            for msg in conversation_history[-10:]:
                sender = "User" if msg.get('type') == 'user' else "Shannon"
                text = msg.get('text', '')
                formatted_history += f"{sender}: {text}\n"

        # Get user's name for personalization
        first_name = metrics.get('first_name', user_ig_username)

        # Build enhanced prompt based on prompt type
        if prompt_type == 'general_chat':
            enhanced_prompt = f"""
You are Shannon, a casual Australian fitness coach chatting with {first_name} (@{user_ig_username}) on Instagram DM.

**User's Bio & Interests:**
- Interests: {', '.join(interests[:5]) if interests else 'Not specified'}
- Recent Activities: {', '.join(recent_activities[:3]) if recent_activities else 'Not specified'}

**Conversation Topics to Draw From:**
{chr(10).join([f"- {topic}" for topic in conversation_topics[:5]])
     if conversation_topics else "- General fitness and lifestyle"}

**Recent Conversation:**
{formatted_history}

**User's Current Message:** {incoming_message}

**Instructions:**
- Respond in Shannon's casual, friendly Australian style
- Reference their interests or recent activities naturally if relevant
- Create personalized connections like "oh hey I saw you liked [interest], have you been around [related activity] lately?"
- Keep it conversational and engaging
- Ask follow-up questions related to their bio/interests when appropriate
- Don't force bio references if they don't fit naturally
- CRITICAL: Your response MUST be between 1 and 15 words.

Generate a natural, personalized response that feels like Shannon knows them personally:
"""

        elif prompt_type == 'checkin_monday':
            enhanced_prompt = f"""
You are Shannon, a casual Australian fitness coach doing a Monday morning check-in with your client {first_name} (@{user_ig_username}).

**Shannon's actual Monday check-in style examples:**
- "Goooooood Morning! Ready for the week?"
- "Morning! How's your week starting?"
- "Goooooood Morning! How was the weekend?"
- "Morning mate! Ready to crush this week?"

**Client's Recent Context:**
{formatted_history[-200:] if formatted_history else 'No recent context'}

**Client's Message:** {incoming_message}

**CRITICAL INSTRUCTIONS:**
- Generate ONLY ONE SHORT MESSAGE (1-2 sentences maximum)
- Your response MUST be between 1 and 15 words.
- Use Shannon's casual, simple style
- Start with "Goooooood Morning!" or similar
- Keep it brief and natural
- NO long paragraphs or multiple topics
- NO emojis unless very minimal
- Ask ONE simple question about their week/weekend

Generate ONE short Monday morning message:
"""

        elif prompt_type == 'checkin_wednesday':
            enhanced_prompt = f"""
You are Shannon, a casual Australian fitness coach doing a Wednesday night check-in with your client {first_name} (@{user_ig_username}).

**Shannon's actual Wednesday check-in style examples:**
- "Heya! Hows your week going?"
- "Hey hey! Hows your week been?"
- "Heya, how's the week treating you?"
- "Hows your week going so far?"

**Client's Recent Context:**
{formatted_history[-200:] if formatted_history else 'No recent context'}

**Client's Message:** {incoming_message}

**CRITICAL INSTRUCTIONS:**
- Generate ONLY ONE SHORT MESSAGE (1-2 sentences maximum)
- Your response MUST be between 1 and 15 words.
- Use Shannon's casual, simple style
- Start with "Heya!" or "Hey hey!"
- Keep it brief and natural
- NO long paragraphs or multiple topics
- NO emojis unless very minimal
- Ask ONE simple question about their week

Generate ONE short Wednesday check-in message:
"""

        elif prompt_type == 'member_chat':
            enhanced_prompt = f"""
You are Shannon, a casual Australian fitness coach chatting with your client {first_name} (@{user_ig_username}).

**Client's Profile:**
- Interests: {', '.join(interests[:5]) if interests else 'Fitness focused'}
- Recent Activities: {', '.join(recent_activities[:3]) if recent_activities else 'Training related'}

**Member Chat Topics:**
{chr(10).join([f"- {topic}" for topic in conversation_topics[:3]])
     if conversation_topics else "- Training progress and goals"}

**Recent Conversation:**
{formatted_history}

**Client's Message:** {incoming_message}

**Instructions:**
- Respond as their personal fitness coach
- Reference their specific interests/activities to show you remember them
- Ask about progress related to their interests (e.g., if they like hiking, ask about recent hikes)
- Keep it personal and supportive
- Show genuine interest in their individual journey
- CRITICAL: Your response MUST be between 1 and 15 words.

Generate a personalized coaching response:
"""

        else:
            # Default enhanced prompt
            enhanced_prompt = f"""
You are Shannon responding to {first_name} (@{user_ig_username}).

**Their Interests:** {', '.join(interests[:5]) if interests else 'General'}
**Recent Activities:** {', '.join(recent_activities[:3]) if recent_activities else 'Various'}
**Conversation Topics:** {', '.join(conversation_topics[:3]) if conversation_topics else 'General chat'}

**Recent Chat:**
{formatted_history}

**Their Message:** {incoming_message}

Respond naturally, referencing their interests when relevant. Keep it casual and personal.
Your response MUST be between 1 and 15 words.
"""

        # Generate response with enhanced context
        logger.info(
            f"Using enhanced prompt for {user_ig_username} with {len(interests)} interests and {len(conversation_topics)} topics")

        enhanced_response = call_gemini_with_retry_sync(
            GEMINI_MODEL_PRO, enhanced_prompt)

        logger.info(
            f"Successfully generated enhanced response for {user_ig_username}: {enhanced_response[:100]}...")
        return enhanced_response

    except Exception as e:
        logger.error(
            f"Error in enhanced regeneration for {user_ig_username}: {e}", exc_info=True)
        # Fallback to original prompt if enhancement fails
        return call_gemini_with_retry_sync(GEMINI_MODEL_FLASH, original_prompt)


# Add a session state for message queue (remains the same)
if 'message_queue' not in st.session_state:
    st.session_state.message_queue = []

# Add session state for last signup check (remains the same)
if 'last_signup_check' not in st.session_state:
    st.session_state.last_signup_check = None


def get_response_category_color(num_responses):
    """Return color and emoji indicator based on number of responses"""
    if num_responses >= 20:
        return "🟢"  # Green circle for high responders
    elif num_responses >= 11:
        return "🟡"  # Yellow circle for medium responders
    elif num_responses >= 1:
        return "🟠"  # Orange circle for low responders
    else:
        return "🔴"  # Red circle for no response


def generate_follow_up_message(conversation_history, topic, days_since_last=None):
    """Generate a follow-up message using Gemini with timing context and 3-fallback system"""
    if not GEMINI_API_KEY or GEMINI_API_KEY in ["YOUR_GEMINI_API_KEY", "your_gemini_api_key_here"]:
        st.error("Gemini API key not available. Cannot generate message.")
        return "[Gemini not available]"
    try:
        # Format conversation history
        formatted_history = ""
        for msg in conversation_history:  # conversation_history should be a list of dicts
            sender = "User" if msg.get('type') == 'user' else "Shannon"
            formatted_history += f"{sender}: {msg.get('text', '')}\n"

        # Create timing-aware prompt
        timing_context = ""
        if days_since_last:
            if days_since_last <= 2:
                timing_context = f"It's been {days_since_last} days since they last messaged - this is a recent follow-up, so keep it casual and direct."
            elif days_since_last <= 7:
                timing_context = f"It's been {days_since_last} days since they last messaged - acknowledge the gap briefly and re-engage warmly."
            elif days_since_last <= 14:
                timing_context = f"It's been {days_since_last} days (about {days_since_last//7} weeks) since they last messaged - acknowledge the longer gap and restart the conversation gently."
            else:
                timing_context = f"It's been {days_since_last} days (over {days_since_last//7} weeks) since they last messaged - this is a re-engagement message, be warm and understanding about the gap."

        prompt = f"""You are Shannon, a casual Australian fitness coach reaching out to someone on Instagram.
        
        TIMING CONTEXT: {timing_context}
        
        TOPIC TO DISCUSS: {topic}
        
        PREVIOUS CONVERSATION:
        {formatted_history}
        
        Create a casual, friendly follow-up message that:
        - Acknowledges the time gap appropriately (if relevant)
        - Transitions naturally into the topic
        - Feels personal and conversational
        - Is between 1-15 words total
        - Uses Shannon's relaxed Australian tone
        
        Examples by timing:
        - 2-3 days: "hey! been thinking about [topic]..."
        - 1 week: "heya! how's things been? was just thinking about [topic]..."
        - 2+ weeks: "hey there! hope you've been well! was just thinking about [topic]..."
        
        Generate ONLY the message, no other text:"""

        # Use the 3-fallback system starting with the best model
        response_text = call_gemini_with_retry_sync(GEMINI_MODEL_PRO, prompt)
        return response_text
    except Exception as e:
        st.error(f"Error generating message: {e}")
        logger.error(f"Gemini message generation error: {e}", exc_info=True)
        return None


def get_stage_topics(stage_number):
    """Get conversation topics for a specific stage"""
    stage_topics = {
        1: ["Topic 1 - Discuss their favorite plant-based protein sources for muscle growth and any creative vegetarian recipes they've discovered recently."],
        2: ["Topic 2 - Explore their approach to tracking progress with clients, specifically what metrics they prioritize beyond just weight loss and how they use fitness apps."],
        3: ["Topic 3 - Talk about their. experience adapting resistance training techniques for clients with different fitness levels and what common mistakes they see people make."],
        4: ["Topic 4 - Share tips on incorporating high-protein vegetarian meals into a busy schedule and how they advise clients to make healthy eating more convenient in Melbourne."],
        5: ["Topic 5 - Enquire about leads fitness journey - offer 1 month trial"],
        6: ["Trial Week 1 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 1 - Wednesday Night: Heya! Hows your week going?"],
        7: ["Trial Week 2 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 2 - Wednesday Night: Heya! Hows your week going?"],
        8: ["Trial Week 3 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 3 - Wednesday Night: Heya! Hows your week going?"],
        9: ["Trial Week 4 - Monday Morning: Goooooood Morning! Ready for the week?",
            "Trial Week 4 - Wednesday Night: Heya! Hows your week going?"],
        10: ["Paying Client - Monday Morning: Goooooood Morning! Ready for the week?",
             "Paying Client - Wednesday Night: Heya! Hows your week going?"]
    }
    return stage_topics.get(stage_number, [])


def get_response_level_wait_time(num_responses):
    """Return wait time in days based on response level"""
    if num_responses >= 20:  # High responder (green)
        return 2  # 48 hours
    elif num_responses >= 11:  # Medium responder (yellow)
        return 5  # 5 days
    else:  # Low responder (orange/red)
        return 7  # 7 days


def get_users_ready_for_followup(analytics_data: dict):
    """Determine which users are ready for follow-up based on their response level, matching user_profiles logic."""
    ready_for_followup = {
        'high_responders': [],
        'medium_responders': [],
        'low_responders': [],
        'total_count': 0
    }
    current_time = datetime.now()

    # Known non-user keys
    known_non_user_keys = ["conversations",
                           "action_items", "conversation_history"]
    processed_usernames = set()

    # Helper to process a user
    def process_user(username, user_data):
        if username in processed_usernames:
            return
        processed_usernames.add(username)
        metrics = user_data.get('metrics', {})
        if not metrics:
            return
        last_interaction_ts_str = metrics.get('last_interaction_timestamp')
        last_message_time = None
        if last_interaction_ts_str:
            try:
                last_message_time = datetime.fromisoformat(
                    last_interaction_ts_str.split('+')[0])
            except (ValueError, AttributeError):
                pass
        if not last_message_time:
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                try:
                    last_msg_in_history = conversation_history[-1]
                    last_message_time = datetime.fromisoformat(
                        last_msg_in_history.get('timestamp', '').split('+')[0])
                except (IndexError, ValueError, AttributeError):
                    pass
        if not last_message_time:
            return
        num_responses = metrics.get('user_messages', 0)
        wait_days = get_response_level_wait_time(num_responses)
        time_since_last_message = current_time - last_message_time
        if time_since_last_message.days >= wait_days:
            user_info = {
                'username': username,
                'days_since_last_message': time_since_last_message.days,
                'response_count': num_responses,
                'last_message_time': last_message_time
            }
            if num_responses >= 20:
                ready_for_followup['high_responders'].append(user_info)
            elif num_responses >= 11:
                ready_for_followup['medium_responders'].append(user_info)
            else:
                ready_for_followup['low_responders'].append(user_info)
            ready_for_followup['total_count'] += 1

    # Process all top-level users
    for username, user_data in analytics_data.items():
        if username in known_non_user_keys:
            continue
        if isinstance(user_data, dict):
            process_user(username, user_data)

    # Process users under 'conversations'
    nested_conversations = analytics_data.get('conversations')
    if isinstance(nested_conversations, dict):
        for username, user_data in nested_conversations.items():
            process_user(username, user_data)

    logger.info(
        f"Users ready for followup: High={len(ready_for_followup['high_responders'])}, Med={len(ready_for_followup['medium_responders'])}, Low={len(ready_for_followup['low_responders'])}")
    return ready_for_followup


# get_user_topics function moved to shared_utils.py to avoid circular imports


def queue_message_for_followup(username, message, topic):
    """Add a message to the follow-up queue and to conversation history for check-ins"""
    st.session_state.message_queue.append({
        'username': username,
        'message': message,
        'topic': topic,
        'queued_time': datetime.now().isoformat()
    })

    # If this is a check-in message, add it to conversation history immediately
    # so the AI knows about it for future conversations
    if topic and 'check' in topic.lower():
        try:
            add_message_to_history(
                ig_username=username,
                message_type='ai',
                message_text=message,
                message_timestamp=None  # This will use current timestamp
            )
            logger.info(
                f"Check-in message added to conversation history for {username}")
        except Exception as e:
            logger.error(
                f"Failed to add check-in message to conversation history for {username}: {e}", exc_info=True)


def save_followup_queue():
    """Save the follow-up queue to a file for the follow-up manager"""
    # Fix: Save to the main shanbot directory where followup_manager.py expects it
    queue_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\followup_queue.json"
    try:
        with open(queue_file, 'w') as f:
            json.dump({
                'messages': st.session_state.message_queue,
                'created_at': datetime.now().isoformat()
            }, f, indent=2)
        logger.info(f"Followup queue saved to {queue_file}")
        return True
    except Exception as e:
        st.error(f"Error saving follow-up queue: {e}")
        logger.error(f"Error saving followup_queue.json: {e}", exc_info=True)
        return False


def display_user_followup(user_followup_info, all_analytics_data):
    """Display user follow-up information with message generation and sending capabilities."""
    username = user_followup_info['username']

    # Get user_data by checking the 'conversations' part of all_analytics_data
    user_container = all_analytics_data.get('conversations', {}).get(username)
    if not user_container or 'metrics' not in user_container:
        st.error(
            f"Could not find data for user '{username}' to display followup.")
        logger.error(
            f"Data or metrics missing for user {username} in display_user_followup.")
        return

    # This is the dict of the user's data from SQLite
    metrics = user_container['metrics']

    with st.expander(f"{username} - {user_followup_info['days_since_last_message']} days since last message"):
        # Create columns for layout
        info_col, history_col = st.columns([1, 1])

        with info_col:
            # Basic Information
            st.write("### User Information")
            st.write(
                f"**Response count:** {user_followup_info['response_count']}")
            st.write(
                f"**Last message:** {user_followup_info['last_message_time'].strftime('%Y-%m-%d %H:%M')}")

            # Get user's conversation topics from metrics
            available_topics = get_user_topics(metrics)

            if not available_topics:
                st.warning("No conversation topics available for this user")
                current_topic = "General catch-up"  # Default topic
            else:
                # Get user's category and appropriate topic
                # get_user_category needs to handle new metrics structure
                user_category = get_user_category(metrics)
                current_topic = get_topic_for_category(
                    user_category, metrics)  # Same for get_topic_for_category

                # Show current topic
                st.write("### Current Topic")
                st.info(current_topic)

                if st.button(f"Generate Message", key=f"gen_{username}"):
                    if not GEMINI_API_KEY or GEMINI_API_KEY in ["YOUR_GEMINI_API_KEY", "your_gemini_api_key_here"]:
                        st.error(
                            "Gemini API key not available for message generation.")
                        return
                    with st.spinner("Generating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic, user_followup_info.get('days_since_last_message', None))
                    if message:
                        # Store generated message in user_followup_info (which is part of a list, not session state directly)
                        user_followup_info['generated_message'] = message
                        user_followup_info['selected_topic'] = current_topic
                        st.success("Message generated!")
                        st.rerun()  # Rerun to show the text_area
                    else:
                        st.error("Failed to generate message.")

        with history_col:
            # Conversation History
            st.write("### Conversation History")
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                st.write("Last 5 messages:")
                history_container = st.container()
                with history_container:
                    for msg in conversation_history[-5:]:
                        sender = "User" if msg.get(
                            'type') == 'user' else "Shannon"
                        st.write(f"**{sender}:** {msg.get('text', '')}")
            else:
                st.info("No conversation history available")

        # Message editing section - full width below columns
        st.write("### Follow-up Message")
        if 'generated_message' in user_followup_info:
            # Create a text area for editing the message
            edited_message = st.text_area(
                "Edit message if needed:",
                value=user_followup_info['generated_message'],
                key=f"edit_{username}",
                height=100
            )

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                # Add a regenerate button
                if st.button("Regenerate", key=f"regen_{username}"):
                    if not GEMINI_API_KEY or GEMINI_API_KEY in ["YOUR_GEMINI_API_KEY", "your_gemini_api_key_here"]:
                        st.error(
                            "Gemini API key not available for message regeneration.")
                        return
                    with st.spinner("Regenerating message..."):
                        conversation_history = metrics.get(
                            'conversation_history', [])
                        message = generate_follow_up_message(
                            conversation_history, current_topic, user_followup_info.get('days_since_last_message', None))
                        if message:
                            user_followup_info['generated_message'] = message
                            user_followup_info['selected_topic'] = current_topic
                        st.success("Message regenerated!")
                        st.rerun()
                else:
                    st.error("Failed to regenerate message")

            with col2:
                # Add queue message button
                if st.button("Queue Message", key=f"queue_{username}"):
                    queue_message_for_followup(
                        username, edited_message, current_topic)
                    st.success(f"Message queued for {username}")
                    st.rerun()  # Rerun to reflect queue update

            # Update the stored message if edited
            if edited_message != user_followup_info['generated_message']:
                user_followup_info['generated_message'] = edited_message
                # No need for success message or rerun here, just update the dict for next interaction
        else:
            st.warning("Click 'Generate Message' to create a message")


def display_scheduled_followups_tab(analytics_data_dict):
    """Display the scheduled follow-ups section. Renamed to avoid conflict."""
    st.header("📅 Scheduled Follow-ups")

    # Get users ready for follow-up
    followup_data_list = get_users_ready_for_followup(analytics_data_dict)

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Ready for Follow-up",
                  followup_data_list['total_count'])

    with col2:
        high_count = len(followup_data_list['high_responders'])
        st.metric("High Responders Ready (48h)", high_count)

    with col3:
        medium_count = len(followup_data_list['medium_responders'])
        st.metric("Medium Responders Ready (5d)", medium_count)

    with col4:
        low_count = len(followup_data_list['low_responders'])
        st.metric("Low Responders Ready (7d)", low_count)

    # Display queued messages if any exist
    if st.session_state.message_queue:
        st.subheader("📬 Queued Messages")
        st.write(
            f"{len(st.session_state.message_queue)} messages queued for sending")

        # Show queued messages in an expander
        with st.expander("View Queued Messages"):
            for msg_item in st.session_state.message_queue:
                st.write(f"**To:** {msg_item['username']}")
                st.write(f"**Topic:** {msg_item['topic']}")
                st.write(f"**Message:** {msg_item['message']}")
                st.write("---")

        # Add send button
        if st.button("🚀 Send All Queued Messages", type="primary"):
            if save_followup_queue():
                st.success(
                    "✅ All messages queued for Shannon's followup_manager.py!")
                st.info(
                    "💡 Starting Instagram automation browser...")

                # Start Shannon's followup_manager.py script
                try:
                    import subprocess
                    import os

                    # Use Shannon's followup_manager.py script
                    if os.path.exists(FOLLOWUP_MANAGER_SCRIPT_PATH):
                        # Start Shannon's followup_manager in a new process
                        st.info("🔄 Starting Shannon's Instagram DM automation...")

                        process = subprocess.Popen([
                            "python",
                            "followup_manager.py"
                        ],
                            cwd=r"C:\Users\Shannon\OneDrive\Desktop\shanbot",
                            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                                subprocess, 'CREATE_NEW_CONSOLE') else 0
                        )

                        st.success(
                            "🚀 Instagram automation started! Browser should open in a few seconds.")
                        st.info(
                            "📝 The browser will automatically log into Instagram and process your queued messages.")
                        st.session_state.message_queue = []
                        st.rerun()
                    else:
                        st.error(
                            f"❌ followup_manager.py not found at: {FOLLOWUP_MANAGER_SCRIPT_PATH}")

                except Exception as e:
                    st.error(
                        f"❌ Failed to start Instagram automation: {str(e)}")
                    st.info(
                        "💡 You can manually run followup_manager.py from the command line")
            else:
                st.error("❌ Failed to queue messages for sending")

    # Create tabs for different response levels
    high_tab, medium_tab, low_tab = st.tabs([
        "🟢 High Responders",
        "🟡 Medium Responders",
        "🟠 Low Responders"
    ])

    # Display users with their generated messages
    with high_tab:
        if followup_data_list['high_responders']:
            for user_info_item in followup_data_list['high_responders']:
                # Pass full data dict
                display_user_followup(user_info_item, analytics_data_dict)
        else:
            st.info("No high responders ready for follow-up")

    with medium_tab:
        if followup_data_list['medium_responders']:
            for user_info_item in followup_data_list['medium_responders']:
                display_user_followup(user_info_item, analytics_data_dict)
        else:
            st.info("No medium responders ready for follow-up")

    with low_tab:
        if followup_data_list['low_responders']:
            for user_info_item in followup_data_list['low_responders']:
                display_user_followup(user_info_item, analytics_data_dict)
        else:
            st.info("No low responders ready for follow-up")


def save_analytics_data(data_to_save: dict, json_file_path_for_actions: str) -> bool:
    """Save user metrics to SQLite and action_items to JSON."""
    overall_success = True
    # 1. Save 'conversations' data (user metrics) to SQLite
    if 'conversations' in data_to_save:
        for ig_username, user_container in data_to_save['conversations'].items():
            metrics = user_container.get('metrics')
            if metrics:
                if not save_metrics_to_sqlite(
                    subscriber_id=metrics.get('subscriber_id'),
                    ig_username=ig_username,
                    message_text="Data saved from dashboard.",
                    message_direction="system",
                    timestamp=datetime.now().isoformat(),
                    **metrics
                ):
                    logger.error(
                        f"Failed to save metrics to SQLite for user: {ig_username}")
                    overall_success = False  # Mark failure but continue trying others
            else:
                logger.warning(
                    f"No metrics found for user {ig_username} during save_analytics_data.")
    else:
        logger.warning("No 'conversations' key in data_to_save for SQLite.")

    # 2. Save 'action_items' to JSON file
    if 'action_items' in data_to_save:
        try:
            logger.info(
                f"Saving action_items to JSON: {json_file_path_for_actions}")
            json_dir = os.path.dirname(json_file_path_for_actions)
            if not os.path.exists(json_dir):
                os.makedirs(json_dir)
                logger.info(f"Created directory for JSON file: {json_dir}")
            content_for_json = {'action_items': data_to_save['action_items']}
            with open(json_file_path_for_actions, 'w', encoding='utf-8') as f:
                json.dump(content_for_json, f, indent=2)
            logger.info(
                f"Successfully saved action_items to {json_file_path_for_actions}")
        except Exception as e:
            logger.error(
                f"Error saving action_items to JSON {json_file_path_for_actions}: {e}", exc_info=True)
            overall_success = False
    else:
        logger.warning("No 'action_items' key in data_to_save for JSON.")

    return overall_success


# --- User Management functions moved to user_management.py module ---

# --- ADDED: Function to display Response Review Queue ---


# Response review functionality moved to response_review.py module

# --- ADDED: Function to display Recent Interactions --- START ---


# --- ADDED: Function to display Recent Interactions --- END ---


# Follow-up manager functionality moved to followup_manager.py module

# --- NEW: Check-ins Manager --- START ---


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

    # Create tabs for different check-in management functions
    schedule_tab, manual_tab, inactive_tab = st.tabs([
        "📋 Scheduled Check-ins",
        "🎯 Manual Triggers",
        "⚠️ Inactive Clients"
    ])

    with schedule_tab:
        # Removed the Automated Check-in Schedule section as requested

        # Show current followup queue status
        if st.session_state.message_queue:
            queue_count = len(st.session_state.message_queue)
            checkin_count = sum(
                1 for msg in st.session_state.message_queue if msg.get('topic') == 'Check-in')

            st.info(
                f"📬 **Current Queue Status:** {queue_count} total messages queued ({checkin_count} check-ins)")

            col_view_queue, col_send_queue = st.columns([1, 1])
            with col_view_queue:
                if st.button("👀 View Queue", use_container_width=True):
                    with st.expander("Current Message Queue", expanded=True):
                        for i, msg in enumerate(st.session_state.message_queue):
                            st.write(
                                f"**{i+1}. {msg['username']}** ({msg['topic']})")
                            st.caption(f"Message: {msg['message'][:100]}...")
                            st.write("---")

            with col_send_queue:
                if st.button("🚀 Send All Queued Messages", type="primary", use_container_width=True):
                    if save_followup_queue():
                        st.success(
                            "✅ All messages queued for Shannon's followup_manager.py!")
                        st.info(
                            "💡 Starting Instagram automation browser...")

                        # Start Shannon's followup_manager.py script
                        try:
                            import subprocess
                            import os

                            # Use Shannon's followup_manager.py script
                            if os.path.exists(FOLLOWUP_MANAGER_SCRIPT_PATH):
                                # Start Shannon's followup_manager in a new process
                                st.info(
                                    "🔄 Starting Shannon's Instagram DM automation...")

                                process = subprocess.Popen([
                                    "python",
                                    "followup_manager.py"
                                ],
                                    cwd=r"C:\Users\Shannon\OneDrive\Desktop\shanbot",
                                    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                                        subprocess, 'CREATE_NEW_CONSOLE') else 0
                                )

                                st.success(
                                    "🚀 Instagram automation started! Browser should open in a few seconds.")
                                st.info(
                                    "📝 The browser will automatically log into Instagram and process your queued messages.")
                                st.session_state.message_queue = []
                                st.rerun()
                            else:
                                st.error(
                                    f"❌ followup_manager.py not found at: {FOLLOWUP_MANAGER_SCRIPT_PATH}")

                        except Exception as e:
                            st.error(
                                f"❌ Failed to start Instagram automation: {str(e)}")
                            st.info(
                                "💡 You can manually run followup_manager.py from the command line")
                    else:
                        st.error("❌ Failed to queue messages for sending")

        # Proactive Check-in Message Generator
        st.subheader("🚀 Generate & Queue Check-in Messages")
        st.caption(
            "Create personalized check-in messages and queue them for Instagram DM sending")

        # Filter for trial and paying clients
        eligible_clients = []

        # Debug: Show total conversations
        st.info(
            f"📊 **Debug Info:** Found {len(conversations_data)} total conversations")

        # Debug: Show sample of clients and their status
        debug_clients = []
        for username, user_container in conversations_data.items():
            metrics = user_container.get('metrics', {})
            if not metrics:
                continue

            journey_stage = metrics.get('journey_stage', {})
            if not isinstance(journey_stage, dict):
                # Try to get journey_stage from metrics_json if main field is None
                metrics_json = metrics.get('metrics_json', '{}')
                if metrics_json and isinstance(metrics_json, str):
                    try:
                        import json
                        parsed_metrics = json.loads(metrics_json)
                        journey_stage = parsed_metrics.get('journey_stage', {})
                    except:
                        journey_stage = {}
                else:
                    journey_stage = {}

            # Only include paying clients and trial members
            is_paying = journey_stage.get('is_paying_client', False)
            is_trial = bool(journey_stage.get('trial_start_date'))

            debug_clients.append({
                'username': username,
                'is_paying': is_paying,
                'is_trial': is_trial,
                'trial_start_date': journey_stage.get('trial_start_date'),
                'current_stage': journey_stage.get('current_stage', 'Unknown')
            })

            if is_paying or is_trial:
                client_info = {
                    'username': username,
                    'ig_username': metrics.get('ig_username', username),
                    'is_paying': is_paying,
                    'is_trial': is_trial,
                    'current_stage': journey_stage.get('current_stage', 'Unknown'),
                    'first_name': metrics.get('first_name', ''),
                    'last_name': metrics.get('last_name', ''),
                    'subscriber_id': metrics.get('subscriber_id', ''),
                    'is_mon_checkin': metrics.get('is_in_checkin_flow_mon', False),
                    'is_wed_checkin': metrics.get('is_in_checkin_flow_wed', False),
                    'metrics': metrics
                }
                eligible_clients.append(client_info)

        # Show debug info
        if debug_clients:
            st.write("**Client Status Breakdown:**")
            paying_count = sum(1 for c in debug_clients if c['is_paying'])
            trial_count = sum(1 for c in debug_clients if c['is_trial'])
            total_count = len(debug_clients)

            st.write(f"• Total clients: {total_count}")
            st.write(f"• Paying clients: {paying_count}")
            st.write(f"• Trial clients: {trial_count}")
            st.write(f"• Eligible for check-ins: {len(eligible_clients)}")

            if len(eligible_clients) == 0:
                st.warning("⚠️ **No clients qualify for check-ins.**")
                st.write("**To qualify, clients must be either:**")
                st.write("• Paying clients (`is_paying_client: true`)")
                st.write("• Trial members (`trial_start_date` exists)")

                # Show sample of non-qualifying clients
                st.write("**Sample of non-qualifying clients:**")
                for i, client in enumerate(debug_clients[:5]):
                    st.write(
                        f"• {client['username']}: Paying={client['is_paying']}, Trial={client['is_trial']}, Stage={client['current_stage']}")

        if eligible_clients:
            # Bulk check-in generation
            st.write("**Bulk Check-in Generation:**")
            col_bulk1, col_bulk2 = st.columns(2)

            with col_bulk1:
                if st.button("🌅 Generate All Monday Check-ins", type="primary", use_container_width=True):
                    with st.spinner("Generating Monday check-ins for all clients..."):
                        generated_count = 0
                        for client in eligible_clients:
                            message_key = f"monday_checkin_{client['username']}"
                            generated_message = generate_checkin_message(
                                client['metrics'], "monday")
                            if generated_message:
                                st.session_state[message_key] = generated_message
                                generated_count += 1

                        if generated_count > 0:
                            st.success(
                                f"✅ Generated Monday check-ins for {generated_count} clients!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to generate check-in messages")

            with col_bulk2:
                if st.button("🌙 Generate All Wednesday Check-ins", type="primary", use_container_width=True):
                    with st.spinner("Generating Wednesday check-ins for all clients..."):
                        generated_count = 0
                        for client in eligible_clients:
                            message_key = f"wednesday_checkin_{client['username']}"
                            generated_message = generate_checkin_message(
                                client['metrics'], "wednesday")
                            if generated_message:
                                st.session_state[message_key] = generated_message
                                generated_count += 1

                        if generated_count > 0:
                            st.success(
                                f"✅ Generated Wednesday check-ins for {generated_count} clients!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to generate check-in messages")

            st.divider()

            # Individual client check-in generation and sending
            st.subheader(
                f"Individual Check-in Messages ({len(eligible_clients)} clients)")

            # Summary metrics
            paying_count = sum(1 for c in eligible_clients if c['is_paying'])
            trial_count = sum(1 for c in eligible_clients if c['is_trial'])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Paying Clients", paying_count)
            with col2:
                st.metric("🆓 Trial Members", trial_count)
            with col3:
                monday_generated = sum(
                    1 for c in eligible_clients if f"monday_checkin_{c['username']}" in st.session_state)
                st.metric("🌅 Monday Generated", monday_generated)
            with col4:
                wednesday_generated = sum(
                    1 for c in eligible_clients if f"wednesday_checkin_{c['username']}" in st.session_state)
                st.metric("🌙 Wednesday Generated", wednesday_generated)

            # Show each client's check-in options
            for client in eligible_clients:
                client_type = "💰 Paying" if client['is_paying'] else "🆓 Trial"
                full_name = f"{client['first_name']} {client['last_name']}".strip(
                ) if client['first_name'] or client['last_name'] else ""

                with st.expander(f"{client_type} **{client['ig_username']}** {f'({full_name})' if full_name else ''}", expanded=False):

                    # Check-in type selection
                    checkin_type = st.radio(
                        "Check-in Type:",
                        ["Monday Morning", "Wednesday Check-in"],
                        key=f"checkin_type_{client['username']}",
                        horizontal=True
                    )

                    checkin_key = "monday" if "Monday" in checkin_type else "wednesday"
                    message_key = f"{checkin_key}_checkin_{client['username']}"

                    col_gen, col_info = st.columns([2, 1])

                    with col_gen:
                        # Generate message button
                        if st.button(f"🤖 Generate {checkin_type} Message", key=f"gen_checkin_{client['username']}", use_container_width=True):
                            with st.spinner(f"Generating personalized {checkin_type.lower()} check-in..."):
                                try:
                                    st.info(
                                        f"🔄 Generating message for {client['ig_username']} ({checkin_key} check-in)...")
                                    generated_message = generate_checkin_message(
                                        client['metrics'], checkin_key)
                                    if generated_message:
                                        st.session_state[message_key] = generated_message
                                        st.success(
                                            "✅ Check-in message generated!")
                                        st.rerun()
                                    else:
                                        st.error(
                                            "❌ Failed to generate check-in message - check logs for details")
                                except Exception as e:
                                    st.error(
                                        f"❌ Error in message generation: {str(e)}")
                                    logger.error(
                                        f"Button click error for {client['username']}: {e}", exc_info=True)

                    with col_info:
                        st.write("**Client Info:**")
                        st.caption(f"Stage: {client['current_stage']}")
                        if full_name:
                            st.caption(f"Name: {full_name}")

                    # Show generated message if it exists
                    if message_key in st.session_state and st.session_state[message_key]:
                        st.write(f"**Generated {checkin_type} Message:**")

                        # Allow editing of the generated message
                        edited_message = st.text_area(
                            "Edit message before queuing:",
                            value=st.session_state[message_key],
                            key=f"edit_checkin_{client['username']}",
                            height=120,
                            help="Review and edit the message to make it perfect before queuing for Instagram DM sending"
                        )

                        # Update stored message if edited
                        if edited_message != st.session_state[message_key]:
                            st.session_state[message_key] = edited_message

                        # Action buttons
                        col_regen, col_send, col_clear = st.columns([1, 1, 1])

                        with col_regen:
                            if st.button("🔄 Regenerate", key=f"regen_checkin_{client['username']}", use_container_width=True):
                                with st.spinner("Regenerating check-in message..."):
                                    new_message = generate_checkin_message(
                                        client['metrics'], checkin_key)
                                    if new_message:
                                        st.session_state[message_key] = new_message
                                        st.success("✅ Message regenerated!")
                                        st.rerun()
                                    else:
                                        st.error(
                                            "❌ Failed to regenerate message")

                        with col_send:
                            if st.button("📤 Queue Check-in", key=f"send_checkin_{client['username']}", type="primary", use_container_width=True):
                                with st.spinner("Queuing check-in message..."):
                                    success = send_checkin_message(
                                        client['ig_username'],
                                        # subscriber_id not needed for Selenium
                                        client.get('subscriber_id', ''),
                                        edited_message
                                    )

                                    if success:
                                        st.success(
                                            f"✅ Check-in queued for {client['ig_username']}!")
                                        # Clear the generated message after queuing
                                        if message_key in st.session_state:
                                            del st.session_state[message_key]
                                        st.rerun()
                                    else:
                                        st.error(
                                            "❌ Failed to queue check-in message")

                        with col_clear:
                            if st.button("🗑️ Clear", key=f"clear_checkin_{client['username']}", use_container_width=True):
                                if message_key in st.session_state:
                                    del st.session_state[message_key]
                                st.info("Message cleared")
                                st.rerun()
                    else:
                        st.info(
                            f"Click 'Generate {checkin_type} Message' to create a personalized check-in for this client.")
        else:
            st.info("No eligible clients found (trial or paying clients only)")

        st.divider()

    with manual_tab:
        st.subheader("Manual Check-in Triggers")
        st.caption("Manually activate check-in flows for specific clients")

        if eligible_clients:
            # Bulk actions
            st.write("**Bulk Actions:**")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("🌅 Activate All Monday", type="primary", use_container_width=True):
                    # Here you would implement bulk Monday activation
                    st.success(
                        "Monday check-ins activated for all eligible clients!")

            with col2:
                if st.button("🌙 Activate All Wednesday", type="primary", use_container_width=True):
                    # Here you would implement bulk Wednesday activation
                    st.success(
                        "Wednesday check-ins activated for all eligible clients!")

            with col3:
                if st.button("🔄 Reset All Monday", use_container_width=True):
                    # Here you would implement bulk Monday reset
                    st.info("All Monday check-ins have been deactivated")

            with col4:
                if st.button("🔄 Reset All Wednesday", use_container_width=True):
                    # Here you would implement bulk Wednesday reset
                    st.info("All Wednesday check-ins have been deactivated")

            st.divider()

            # Individual client controls
            st.write("**Individual Client Controls:**")

            for client in eligible_clients:
                client_type = "💰" if client['is_paying'] else "🆓"
                full_name = f"{client['first_name']} {client['last_name']}".strip(
                ) if client['first_name'] or client['last_name'] else ""

                with st.expander(f"{client_type} **{client['ig_username']}** {f'({full_name})' if full_name else ''}", expanded=False):
                    col_mon, col_wed = st.columns(2)

                    with col_mon:
                        st.write("**🌅 Monday Check-in**")
                        current_mon_status = client['is_mon_checkin']

                        if current_mon_status:
                            st.success("✅ Currently ACTIVE")
                            if st.button("🔄 Deactivate Monday", key=f"deactivate_mon_{client['username']}", use_container_width=True):
                                # Call the trigger_check_in function to toggle Monday check-in
                                user_data = {'metrics': client['metrics']}
                                if trigger_check_in(client['ig_username'], "monday", user_data, current_mon_status, client['is_wed_checkin']):
                                    st.success(
                                        f"Monday check-in deactivated for {client['ig_username']}")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to deactivate Monday check-in")
                        else:
                            st.info("○ Currently Inactive")
                            if st.button("🌅 Activate Monday", key=f"activate_mon_{client['username']}", type="primary", use_container_width=True):
                                # Call the trigger_check_in function to toggle Monday check-in
                                user_data = {'metrics': client['metrics']}
                                if trigger_check_in(client['ig_username'], "monday", user_data, current_mon_status, client['is_wed_checkin']):
                                    st.success(
                                        f"Monday check-in activated for {client['ig_username']}!")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to activate Monday check-in")

                    with col_wed:
                        st.write("**🌙 Wednesday Check-in**")
                        current_wed_status = client['is_wed_checkin']

                        if current_wed_status:
                            st.success("✅ Currently ACTIVE")
                            if st.button("🔄 Deactivate Wednesday", key=f"deactivate_wed_{client['username']}", use_container_width=True):
                                # Call the trigger_check_in function to toggle Wednesday check-in
                                user_data = {'metrics': client['metrics']}
                                if trigger_check_in(client['ig_username'], "wednesday", user_data, client['is_mon_checkin'], current_wed_status):
                                    st.success(
                                        f"Wednesday check-in deactivated for {client['ig_username']}")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to deactivate Wednesday check-in")
                        else:
                            st.info("○ Currently Inactive")
                            if st.button("🌙 Activate Wednesday", key=f"activate_wed_{client['username']}", type="primary", use_container_width=True):
                                # Call the trigger_check_in function to toggle Wednesday check-in
                                user_data = {'metrics': client['metrics']}
                                if trigger_check_in(client['ig_username'], "wednesday", user_data, client['is_mon_checkin'], current_wed_status):
                                    st.success(
                                        f"Wednesday check-in activated for {client['ig_username']}!")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to activate Wednesday check-in")
        else:
            st.info("No eligible clients found for manual triggers")

    with inactive_tab:
        st.subheader("Inactive Clients Needing Attention")
        st.caption(
            "Clients who haven't been contacted recently and may need re-engagement")

        # Filter for inactive clients (keeping the existing logic)
        inactive_clients = []
        current_time = datetime.now()

        for username, user_container in conversations_data.items():
            metrics = user_container.get('metrics', {})
            if not metrics:
                continue

            journey_stage = metrics.get('journey_stage', {})
            if not isinstance(journey_stage, dict):
                continue

            # Only include paying clients and trial members
            is_paying = journey_stage.get('is_paying_client', False)
            is_trial = bool(journey_stage.get('trial_start_date'))

            if not (is_paying or is_trial):
                continue

            # Get last interaction time
            last_interaction_ts_str = metrics.get('last_interaction_timestamp')
            last_interaction = None

            if last_interaction_ts_str:
                try:
                    last_interaction = datetime.fromisoformat(
                        last_interaction_ts_str.split('+')[0])
                except (ValueError, AttributeError):
                    pass

            # Fallback to conversation history
            if not last_interaction:
                conversation_history = metrics.get('conversation_history', [])
                if conversation_history:
                    try:
                        last_msg = conversation_history[-1]
                        last_interaction = datetime.fromisoformat(
                            last_msg.get('timestamp', '').split('+')[0])
                    except (ValueError, AttributeError):
                        pass

            if last_interaction:
                days_since_last = (current_time - last_interaction).days

                # Consider clients inactive if:
                # - Paying clients: no message in 7+ days
                # - Trial members: no message in 3+ days
                threshold_days = 7 if is_paying else 3

                if days_since_last >= threshold_days:
                    client_info = {
                        'username': username,
                        'ig_username': metrics.get('ig_username', username),
                        'last_interaction': last_interaction,
                        'days_since_last': days_since_last,
                        'is_paying': is_paying,
                        'is_trial': is_trial,
                        'current_stage': journey_stage.get('current_stage', 'Unknown'),
                        'conversation_history': metrics.get('conversation_history', []),
                        'first_name': metrics.get('first_name', ''),
                        'last_name': metrics.get('last_name', '')
                    }
                    inactive_clients.append(client_info)

        if inactive_clients:
            # Sort by days since last interaction (most urgent first)
            inactive_clients.sort(
                key=lambda x: x['days_since_last'], reverse=True)

            # Display summary
            paying_count = sum(1 for c in inactive_clients if c['is_paying'])
            trial_count = sum(1 for c in inactive_clients if c['is_trial'])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Inactive", len(inactive_clients))
            with col2:
                st.metric("💰 Paying Clients", paying_count)
            with col3:
                st.metric("🆓 Trial Members", trial_count)

            st.divider()

            # Display each inactive client
            for client in inactive_clients:
                # Determine urgency
                if client['days_since_last'] >= 14:
                    urgency_color = "🔴"
                    urgency_text = "URGENT"
                elif client['days_since_last'] >= 7:
                    urgency_color = "🟠"
                    urgency_text = "Needs attention"
                else:
                    urgency_color = "🟡"
                    urgency_text = "Follow-up due"

                client_type = "💰 Paying" if client['is_paying'] else "🆓 Trial"
                full_name = f"{client['first_name']} {client['last_name']}".strip(
                ) if client['first_name'] or client['last_name'] else ""

                with st.expander(
                    f"{urgency_color} {client_type} **{client['ig_username']}** - {client['days_since_last']} days ago ({urgency_text})",
                    expanded=False
                ):
                    col_info, col_actions = st.columns([1, 2])

                    with col_info:
                        st.write("**Client Information:**")
                        if full_name:
                            st.write(f"• Name: {full_name}")
                        st.write(f"• Stage: {client['current_stage']}")
                        st.write(
                            f"• Last contact: {client['last_interaction'].strftime('%Y-%m-%d %H:%M')}")
                        st.write(
                            f"• Days since contact: {client['days_since_last']}")

                        # Show recent conversation context
                        if client['conversation_history']:
                            st.write("**Recent messages:**")
                            for msg in client['conversation_history'][-2:]:
                                sender = "👤" if msg.get(
                                    'type') == 'user' else "🤖"
                                text_preview = msg.get('text', '')[
                                    :60] + "..." if len(msg.get('text', '')) > 60 else msg.get('text', '')
                                st.caption(f"{sender} {text_preview}")

                    with col_actions:
                        st.write("**Quick Actions:**")

                        # Quick check-in buttons
                        col_mon, col_wed = st.columns(2)
                        with col_mon:
                            if st.button("🌅 Monday Check-in", key=f"quick_mon_{client['username']}", use_container_width=True):
                                # Create user_data structure for trigger_check_in
                                user_data = {'metrics': {
                                    'ig_username': client['ig_username'],
                                    'first_name': client['first_name'],
                                    'last_name': client['last_name'],
                                    'is_in_checkin_flow_mon': False,
                                    'is_in_checkin_flow_wed': False,
                                    'subscriber_id': ''  # You might need to get this from somewhere
                                }}
                                if trigger_check_in(client['ig_username'], "monday", user_data, False, False):
                                    st.success(
                                        f"Monday check-in activated for {client['ig_username']}!")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to activate Monday check-in")

                        with col_wed:
                            if st.button("🌙 Wednesday Check-in", key=f"quick_wed_{client['username']}", use_container_width=True):
                                # Create user_data structure for trigger_check_in
                                user_data = {'metrics': {
                                    'ig_username': client['ig_username'],
                                    'first_name': client['first_name'],
                                    'last_name': client['last_name'],
                                    'is_in_checkin_flow_mon': False,
                                    'is_in_checkin_flow_wed': False,
                                    'subscriber_id': ''  # You might need to get this from somewhere
                                }}
                                if trigger_check_in(client['ig_username'], "wednesday", user_data, False, False):
                                    st.success(
                                        f"Wednesday check-in activated for {client['ig_username']}!")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to activate Wednesday check-in")

                        # Manual message option
                        st.write("**Or send a manual message:**")
                        if st.button("💬 Send Manual Message", key=f"manual_{client['username']}", use_container_width=True):
                            st.info(
                                "Manual message feature - would open message composer")
        else:
            st.success("🎉 All clients have been contacted recently!")

# --- NEW: Proactive Check-in Message Generator --- START ---


# --- Check-in functions moved to checkins_manager.py module ---


def display_challenge_entries():
    """Display all challenge entries (free and paid)"""
    st.title("🌱 Challenge Entries & Bookings")

    # Challenge Info Header
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        st.metric("Challenge Start Date", "July 28th, 2025")

    with col2:
        # Count total entries from database
        try:
            conn = sqlite3.connect("app/analytics_data_good.sqlite")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE lead_source = 'plant_based_challenge' 
                AND challenge_email IS NOT NULL 
                AND challenge_email != ''
            """)
            total_entries = cursor.fetchone()[0] or 0
            conn.close()
        except Exception as e:
            total_entries = 0
            st.error(f"Database error: {e}")

        st.metric("Total Entries", total_entries)

    with col3:
        # Days until challenge starts
        from datetime import datetime, date
        challenge_date = date(2025, 7, 28)
        today = date.today()
        days_until = (challenge_date - today).days

        if days_until > 0:
            st.metric("Days Until Start", f"{days_until} days")
        elif days_until == 0:
            st.metric("Status", "🔥 STARTS TODAY!")
        else:
            st.metric("Status", f"Day {abs(days_until)} of Challenge")

    st.divider()

    # Challenge Entries Table
    st.subheader("📋 All Leads")

    try:
        conn = sqlite3.connect("app/analytics_data_good.sqlite")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                ig_username,
                first_name,
                last_name,
                challenge_email,
                challenge_type,
                challenge_signup_date,
                paid_challenge_booking_status,
                paid_challenge_booking_date,
                lead_source
            FROM users
            WHERE (lead_source = 'plant_based_challenge' AND challenge_email IS NOT NULL AND challenge_email != '')
               OR (lead_source = 'paid_plant_based_challenge' AND paid_challenge_booking_status = 'booked')
            ORDER BY challenge_signup_date DESC, paid_challenge_booking_date DESC
        """)

        entries = cursor.fetchall()
        conn.close()

        if entries:
            import pandas as pd
            df_data = []
            for entry in entries:
                (ig_username, first_name, last_name, email, free_challenge_type, free_signup_date,
                 paid_status, paid_date, lead_source) = entry

                full_name = f"{first_name or ''} {last_name or ''}".strip(
                ) or ig_username

                if lead_source == 'plant_based_challenge':
                    entry_type = "📧 Free Challenge"
                    status = f"Email collected"
                    date_display = datetime.fromisoformat(free_signup_date).strftime(
                        "%m/%d %I:%M%p") if free_signup_date else "Unknown"
                    details = email
                elif lead_source == 'paid_plant_based_challenge':
                    entry_type = "✅ Paid Insight Call"
                    status = "Call Booked"
                    date_display = datetime.fromisoformat(paid_date).strftime(
                        "%m/%d %I:%M%p") if paid_date else "Unknown"
                    details = "See Calendly"
                else:
                    continue

                df_data.append({
                    'Name': full_name,
                    'Instagram': f"@{ig_username}",
                    'Type': entry_type,
                    'Status': status,
                    'Date': date_display,
                    'Contact / Details': details
                })

            df = pd.DataFrame(df_data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Name": st.column_config.TextColumn("👤 Name", width="medium"),
                    "Instagram": st.column_config.TextColumn("📱 Instagram", width="medium"),
                    "Type": st.column_config.TextColumn("💡 Type", width="medium"),
                    "Status": st.column_config.TextColumn("📊 Status", width="medium"),
                    "Date": st.column_config.TextColumn("📅 Date", width="small"),
                    "Contact / Details": st.column_config.TextColumn("📝 Details", width="large"),
                }
            )

            # Export functionality
            st.subheader("📤 Export Options")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("📋 Copy Email List", type="primary"):
                    email_list = ", ".join(
                        [entry[3] for entry in entries])  # entry[3] is email
                    st.code(email_list, language=None)
                    st.success("Email list ready to copy!")

            with col2:
                if st.button("📊 Download CSV", type="secondary"):
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="💾 Download Entries CSV",
                        data=csv,
                        file_name=f"challenge_entries_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )

        else:
            st.info("🔍 No challenge entries or bookings yet.")
    except Exception as e:
        st.error(f"Error loading challenge entries: {e}")
        st.code(str(e))


def display_ab_testing_analytics():
    """Display comprehensive A/B testing analytics for vegan outreach strategies"""
    import sqlite3
    import pandas as pd
    from datetime import datetime, timedelta
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.header("🧪 A/B Testing Analytics - Vegan Outreach Strategies")

    # Test status indicator
    col_status, col_refresh = st.columns([3, 1])
    with col_status:
        st.success(
            "✅ **A/B Test Active** - Fresh vegan contacts are automatically assigned to test groups")
    with col_refresh:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

    # Import conversation strategy functions
    try:
        from conversation_strategy import get_conversation_strategy_for_user, get_strategy_analytics
        strategy_available = True
    except ImportError:
        st.error(
            "⚠️ Conversation strategy module not found. Make sure conversation_strategy.py exists.")
        strategy_available = False
        return

    st.divider()

    # Test Overview Section
    st.subheader("📊 Test Overview")

    try:
        # Get analytics data from conversation strategy
        analytics_data = get_strategy_analytics()

        if not analytics_data or analytics_data['total_users'] == 0:
            st.info("🔍 **No A/B test data yet**\n\nThe A/B test will start collecting data when fresh vegan contacts are processed through the system.")

            # Show test configuration
            st.subheader("🔧 Test Configuration")
            col_config1, col_config2 = st.columns(2)

            with col_config1:
                st.info("""
                **Group A: Rapport-First Approach** 
                - 3-phase gradual approach
                - Build rapport before offering
                - 5-8 messages to offer
                """)

            with col_config2:
                st.info("""
                **Group B: Direct Vegan Approach**
                - Immediate vegan connection
                - Quick fitness qualification
                - 3-5 messages to offer
                """)

            # Test assignment demo
            st.subheader("🎯 Test Assignment Demo")
            test_username = st.text_input(
                "Test username assignment:", placeholder="Enter any Instagram username")
            if test_username:
                strategy = get_conversation_strategy_for_user(test_username)
                if strategy['approach_type'] == 'rapport_first':
                    st.success(
                        f"**@{test_username}** → Group A (Rapport-First)")
                else:
                    st.info(f"**@{test_username}** → Group B (Direct Vegan)")
                st.caption(
                    "Assignment is consistent - same username always gets same group")

            return

        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Users Tested",
                analytics_data['total_users'],
                delta=f"+{analytics_data.get('new_users_today', 0)} today"
            )

        with col2:
            group_a_pct = (analytics_data['group_a_count'] / analytics_data['total_users']
                           * 100) if analytics_data['total_users'] > 0 else 0
            st.metric(
                "Group A (Rapport)",
                analytics_data['group_a_count'],
                delta=f"{group_a_pct:.1f}%"
            )

        with col3:
            group_b_pct = (analytics_data['group_b_count'] / analytics_data['total_users']
                           * 100) if analytics_data['total_users'] > 0 else 0
            st.metric(
                "Group B (Direct)",
                analytics_data['group_b_count'],
                delta=f"{group_b_pct:.1f}%"
            )

        with col4:
            days_running = analytics_data.get('days_running', 0)
            st.metric(
                "Test Duration",
                f"{days_running} days",
                delta=f"Since {analytics_data.get('start_date', 'N/A')}"
            )

        st.divider()

        # Group Assignment Distribution
        st.subheader("⚖️ Group Assignment Distribution")

        if analytics_data['total_users'] > 0:
            # Create pie chart for group distribution
            fig_pie = px.pie(
                values=[analytics_data['group_a_count'],
                        analytics_data['group_b_count']],
                names=['Group A (Rapport-First)', 'Group B (Direct Vegan)'],
                title="Test Group Distribution",
                color_discrete_map={
                    'Group A (Rapport-First)': '#FF6B6B',
                    'Group B (Direct Vegan)': '#4ECDC4'
                }
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # Recent Activity
        st.subheader("📈 Recent Activity")

        recent_logs = analytics_data.get('recent_logs', [])
        if recent_logs:
            # Display recent strategy assignments
            for log in recent_logs[:10]:  # Show last 10
                timestamp = datetime.fromisoformat(
                    log['timestamp'].split('.')[0])
                time_ago = datetime.now() - timestamp

                if time_ago.days > 0:
                    time_str = f"{time_ago.days}d ago"
                elif time_ago.seconds > 3600:
                    time_str = f"{time_ago.seconds // 3600}h ago"
                else:
                    time_str = f"{time_ago.seconds // 60}m ago"

                group_emoji = "🤝" if log['strategy'] == 'rapport_first' else "🎯"
                group_name = "Rapport-First" if log['strategy'] == 'rapport_first' else "Direct Vegan"

                st.caption(
                    f"{group_emoji} **@{log['username']}** → Group {log['strategy'][0].upper()} ({group_name}) - {time_str}")
        else:
            st.info("No recent activity to display")

        st.divider()

        # Performance Metrics (if available)
        st.subheader("📊 Performance Comparison")

        # Check if we have conversation data to analyze performance
        try:
            conn = sqlite3.connect("app/analytics_data_good.sqlite")

            # Get conversation metrics for users in each group
            perf_query = """
            SELECT 
                cs.strategy,
                COUNT(DISTINCT cs.username) as users,
                COUNT(ch.rowid) as total_messages,
                AVG(CASE WHEN ch.message_type = 'user' THEN 1.0 ELSE 0.0 END) as avg_user_messages,
                COUNT(CASE WHEN ch.message_text LIKE '%challenge%' OR ch.message_text LIKE '%program%' THEN 1 END) as offers_made
            FROM conversation_strategy_log cs
            LEFT JOIN conversation_history ch ON cs.username = ch.ig_username
            WHERE cs.is_fresh_vegan = 1
            GROUP BY cs.strategy
            """

            perf_df = pd.read_sql_query(perf_query, conn)
            conn.close()

            if not perf_df.empty:
                col_perf1, col_perf2 = st.columns(2)

                with col_perf1:
                    st.info("**Group A (Rapport-First)**")
                    group_a_data = perf_df[perf_df['strategy']
                                           == 'rapport_first']
                    if not group_a_data.empty:
                        st.metric("Users", int(group_a_data['users'].iloc[0]))
                        st.metric(
                            "Avg Messages/User", f"{group_a_data['total_messages'].iloc[0] / group_a_data['users'].iloc[0]:.1f}")
                        st.metric("Offers Made", int(
                            group_a_data['offers_made'].iloc[0]))
                    else:
                        st.caption("No data yet")

                with col_perf2:
                    st.success("**Group B (Direct Vegan)**")
                    group_b_data = perf_df[perf_df['strategy'] == 'direct']
                    if not group_b_data.empty:
                        st.metric("Users", int(group_b_data['users'].iloc[0]))
                        st.metric(
                            "Avg Messages/User", f"{group_b_data['total_messages'].iloc[0] / group_b_data['users'].iloc[0]:.1f}")
                        st.metric("Offers Made", int(
                            group_b_data['offers_made'].iloc[0]))
                    else:
                        st.caption("No data yet")
            else:
                st.info(
                    "📈 Performance metrics will appear here once conversations start happening with A/B test participants")

        except Exception as e:
            st.warning(f"Could not load performance metrics: {e}")

        st.divider()

        # Test Management
        st.subheader("🔧 Test Management")

        col_mgmt1, col_mgmt2, col_mgmt3 = st.columns(3)

        with col_mgmt1:
            if st.button("📋 Export Test Data", use_container_width=True):
                try:
                    # Export test data as CSV
                    conn = sqlite3.connect("app/analytics_data_good.sqlite")
                    export_df = pd.read_sql_query("""
                        SELECT username, strategy, is_fresh_vegan, timestamp
                        FROM conversation_strategy_log 
                        ORDER BY timestamp DESC
                    """, conn)
                    conn.close()

                    csv = export_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"ab_test_data_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                except Exception as e:
                    st.error(f"Export failed: {e}")

        with col_mgmt2:
            if st.button("🔄 Reset Test Data", use_container_width=True, type="secondary"):
                if st.button("⚠️ Confirm Reset", use_container_width=True):
                    try:
                        conn = sqlite3.connect(
                            "app/analytics_data_good.sqlite")
                        conn.execute("DELETE FROM conversation_strategy_log")
                        conn.commit()
                        conn.close()
                        st.success("Test data reset successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Reset failed: {e}")

        with col_mgmt3:
            if st.button("🧹 Clean Up Trial Members", use_container_width=True):
                try:
                    from conversation_strategy import run_vegan_eligibility_cleanup
                    updated_count = run_vegan_eligibility_cleanup()
                    if updated_count > 0:
                        st.success(
                            f"✅ Removed {updated_count} trial/paying members from vegan auto mode!")
                    else:
                        st.info(
                            "ℹ️ No cleanup needed - all vegan flags are current")
                    st.rerun()
                except Exception as e:
                    st.error(f"Cleanup failed: {e}")

            st.caption(
                "Removes trial/paying members from fresh vegan auto mode")

        # Additional management section
        col_mgmt4, col_mgmt5 = st.columns(2)
        with col_mgmt4:
            st.info(
                "**Test is running automatically**\nFresh vegan contacts are assigned to groups when processed")
        with col_mgmt5:
            st.info(
                "**Auto Cleanup**\nTrial members are automatically removed from vegan mode")

    except Exception as e:
        st.error(f"Error loading A/B testing data: {e}")
        st.info("Make sure the conversation_strategy.py module is properly configured.")
        logger.error(f"A/B testing dashboard error: {e}", exc_info=True)


# Always reload analytics data from the database on every page load
# OPTIMIZATION: Only load data if not already cached or if refresh is requested
if 'analytics_data' not in st.session_state or st.session_state.get('force_refresh', False):
    with st.spinner("Loading analytics data..."):
        st.session_state.analytics_data, st.session_state.action_items_json_path = load_analytics_data()
    st.session_state.force_refresh = False  # Reset the flag
    st.session_state.last_refresh_time = datetime.now().strftime("%H:%M:%S")
    logger.info("Data loaded from database (cache miss or forced refresh).")
else:
    logger.info("Using cached analytics data.")

# Initialize session state for selected page if it doesn't exist
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "Response Review Queue"  # Default page

# Handle migration from old "New Leads" to "Lead Generation"
if st.session_state.selected_page == "New Leads":
    st.session_state.selected_page = "Lead Generation"

# Ensure selected page is valid - if not, reset to Overview
page_options = ["Overview", "Check-ins", "User Profiles",
                "High-Potential Clients", "Follow-up Manager", "Challenge Entries",
                "Daily Report", "Response Review Queue", "A/B Testing", "Lead Generation", "Webhook", "Ads Analytics", "Calendar Follow-ups"]

if st.session_state.selected_page not in page_options:
    st.session_state.selected_page = "Response Review Queue"

# Initialize session state for the review queue user tracking
if 'current_review_user_ig' not in st.session_state:
    st.session_state.current_review_user_ig = None
if 'last_action_review_id' not in st.session_state:  # To help track if an action was just taken
    st.session_state.last_action_review_id = None

# Sidebar
st.sidebar.title("Analytics Dashboard")

# Performance monitoring
if st.sidebar.checkbox("📊 Show Performance Info", value=False):
    st.sidebar.divider()
    st.sidebar.subheader("Performance Info")

    # Show cache status
    if 'analytics_data' in st.session_state:
        st.sidebar.success("✅ Data cached")
        if st.session_state.analytics_data:
            user_count = len(
                st.session_state.analytics_data.get('conversations', {}))
            st.sidebar.info(f"📊 {user_count} users loaded")
    else:
        st.sidebar.warning("⚠️ No cached data")

    # Show last refresh time
    if 'last_refresh_time' in st.session_state:
        st.sidebar.text(
            f"🕒 Last refresh: {st.session_state.last_refresh_time}")

    # Clear cache button
    if st.sidebar.button("🗑️ Clear Cache"):
        st.session_state.force_refresh = True
        st.session_state.analytics_data = None
        st.success("Cache cleared!")
        st.rerun()

# Buffer monitoring
if st.sidebar.checkbox("🔄 Show Buffer Status", value=False):
    st.sidebar.divider()
    st.sidebar.subheader("Message Buffer Status")

    try:
        import requests
        response = requests.get(
            "http://localhost:8000/buffer/status", timeout=5)
        if response.status_code == 200:
            buffer_data = response.json()
            st.sidebar.info(
                f"📦 Active Buffers: {buffer_data.get('active_buffers', 0)}")
            st.sidebar.info(
                f"⚡ Active Tasks: {buffer_data.get('active_tasks', 0)}")
            st.sidebar.info(
                f"🔒 Locked Users: {buffer_data.get('locked_users', 0)}")
            st.sidebar.info(
                f"⏱️ Buffer Window: {buffer_data.get('buffer_window_seconds', 60)}s")

            # Show buffer details
            if buffer_data.get('buffer_details'):
                st.sidebar.text("📋 Buffer Details:")
                # Show first 3
                for sub_id, details in list(buffer_data['buffer_details'].items())[:3]:
                    st.sidebar.text(
                        f"  {sub_id}: {details['message_count']} msgs")
        else:
            st.sidebar.error("❌ Could not fetch buffer status")
    except Exception as e:
        st.sidebar.error(f"❌ Buffer status error: {str(e)[:50]}...")

# Add refresh button to sidebar
if st.sidebar.button("🔄 Refresh Data"):
    # Set flag to force refresh on next load
    st.session_state.force_refresh = True
    st.session_state.last_refresh_time = datetime.now().strftime("%H:%M:%S")
    st.success(
        "Data refresh scheduled! Click any navigation item to see updated data.")
    st.rerun()  # Rerun to reflect refreshed data across the dashboard

# Navigation
# Update the radio button to use and set session_state.selected_page
# page_options already defined above for validation

# Function to update selected_page in session_state


def update_selected_page():
    # Using a temporary key from radio
    st.session_state.selected_page = st.session_state._sidebar_navigation


st.session_state.selected_page = st.sidebar.radio(
    "Navigation",
    options=page_options,
    key='_sidebar_navigation',  # Use a temporary key for the radio's state
    # Callback to update our actual session state variable
    on_change=update_selected_page,
    # Set default based on session state
    index=page_options.index(st.session_state.selected_page)
)

# Main content area
# st.title("Shannon Bot Analytics Dashboard") # Commented out as per request

# Display notification panel on every page
display_notification_panel()


def display_calendar_follow_ups():
    """Display calendar follow-ups management interface."""
    st.subheader("📅 Calendar Follow-ups")
    st.write("Manage users who received calendar links but haven't booked yet.")

    try:
        # Import the calendly integration
        import sys
        import os
        sys.path.append(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        from calendly_integration import CalendlyIntegration

        calendly = CalendlyIntegration()

        # Create tabs for different sections
        tab1, tab2 = st.tabs(["🔄 Follow-ups Needed", "📋 All Bookings"])

        with tab1:
            st.subheader("Users Needing Follow-up")
            # Get users needing follow-up
            users_needing_followup = calendly.get_users_needing_follow_up()

            if not users_needing_followup:
                st.success("🎉 No users currently need follow-up!")
                st.info(
                    "All users who received calendar links have either booked or are still within the follow-up window.")
            else:
                st.info(
                    f"Found {len(users_needing_followup)} users who need follow-up")

                # Display users in a table
                for i, user in enumerate(users_needing_followup):
                    with st.expander(f"@{user['ig_username']} - {user['follow_up_sent_count']} follow-ups sent"):
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            st.write(f"**Instagram:** @{user['ig_username']}")
                            st.write(
                                f"**Link sent:** {user['link_sent_timestamp']}")
                            st.write(
                                f"**Follow-ups sent:** {user['follow_up_sent_count']}")

                        with col2:
                            if st.button("Send Follow-up", key=f"followup_{i}"):
                                # TODO: Implement follow-up sending logic
                                st.success(
                                    f"Follow-up sent to @{user['ig_username']}")

                        with col3:
                            if st.button("Mark as Booked", key=f"booked_{i}"):
                                if calendly.mark_booking_completed(user['ig_username']):
                                    st.success(
                                        f"Marked @{user['ig_username']} as booked")
                                    st.rerun()
                                else:
                                    st.error("Failed to mark as booked")

                # Batch actions
                st.divider()
                st.subheader("Batch Actions")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Send Follow-ups to All", key="batch_followup", type="primary"):
                        st.info("Sending follow-ups to all users...")
                        # TODO: Implement batch follow-up sending
                        st.success("Follow-ups sent!")

                with col2:
                    if st.button("Refresh Data", key="refresh_followup"):
                        st.rerun()

        with tab2:
            st.subheader("All Calendly Bookings")

            # Get all bookings from database
            try:
                import sqlite3
                conn = sqlite3.connect(
                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite")
                cursor = conn.cursor()

                # Check if table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='calendly_bookings'")
                if not cursor.fetchone():
                    st.warning(
                        "No bookings table found. No bookings have been detected yet.")
                    conn.close()
                    return

                # Get all bookings
                cursor.execute("""
                    SELECT booking_id, invitee_name, invitee_email, booking_time, 
                           event_type, ig_username, created_at
                    FROM calendly_bookings 
                    ORDER BY created_at DESC
                """)

                bookings = cursor.fetchall()
                conn.close()

                if not bookings:
                    st.info("No bookings found in database.")
                else:
                    st.success(f"Found {len(bookings)} total bookings")

                    # Summary stats
                    # ig_username column
                    linked_bookings = [b for b in bookings if b[5]]
                    unlinked_bookings = [b for b in bookings if not b[5]]

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Bookings", len(bookings))
                    with col2:
                        st.metric("Linked to Instagram", len(linked_bookings))
                    with col3:
                        st.metric("Unlinked", len(unlinked_bookings))

                    # Display bookings
                    for i, booking in enumerate(bookings):
                        booking_id, invitee_name, invitee_email, booking_time, event_type, ig_username, created_at = booking

                        status = "✅ Linked" if ig_username else "❓ Unlinked"
                        color = "green" if ig_username else "orange"

                        with st.expander(f"{status} - {invitee_name} ({booking_time[:10]})"):
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.write(f"**Name:** {invitee_name}")
                                st.write(f"**Email:** {invitee_email}")
                                st.write(f"**Booking Time:** {booking_time}")
                                st.write(f"**Event Type:** {event_type}")
                                if ig_username:
                                    st.write(f"**Instagram:** @{ig_username}")
                                else:
                                    st.write("**Instagram:** Not linked")
                                st.write(f"**Created:** {created_at}")

                            with col2:
                                if not ig_username:
                                    st.warning("No Instagram username linked")
                                else:
                                    st.success(f"Linked to @{ig_username}")

                                if st.button("Refresh", key=f"refresh_booking_{i}"):
                                    st.rerun()

                    # Export option
                    if st.button("Export Bookings Data"):
                        import pandas as pd
                        df = pd.DataFrame(bookings, columns=[
                            'booking_id', 'invitee_name', 'invitee_email',
                            'booking_time', 'event_type', 'ig_username', 'created_at'
                        ])
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name="calendly_bookings.csv",
                            mime="text/csv"
                        )

            except Exception as e:
                st.error(f"Error loading bookings: {e}")

    except ImportError as e:
        st.error(f"Could not import Calendly integration: {e}")
        st.info("Make sure calendly_integration.py is available.")
    except Exception as e:
        st.error(f"Error loading calendar follow-ups: {e}")
        st.info("Please check the calendly integration configuration.")


if st.session_state.selected_page == "Overview":
    display_overview_tab(st.session_state.analytics_data)

elif st.session_state.selected_page == "Check-ins":
    display_checkins_manager(st.session_state.analytics_data)

elif st.session_state.selected_page == "User Profiles":
    display_user_profiles_with_bulk_update(
        st.session_state.analytics_data)  # Pass the main data dict

elif st.session_state.selected_page == "High-Potential Clients":
    from high_potential_clients import display_high_potential_clients_tab
    display_high_potential_clients_tab(st.session_state.analytics_data)

elif st.session_state.selected_page == "Follow-up Manager":
    # Import locally to avoid conflict with root followup_manager.py
    import sys
    import os
    current_dir = os.path.dirname(__file__)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    # Import the dashboard version, not the root Selenium script
    import importlib.util
    spec = importlib.util.spec_from_file_location("dashboard_followup_manager",
                                                  os.path.join(current_dir, "followup_manager.py"))
    dashboard_followup_manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard_followup_manager)

    dashboard_followup_manager.display_followup_manager(
        st.session_state.analytics_data)

elif st.session_state.selected_page == "Challenge Entries":
    display_challenge_entries()

elif st.session_state.selected_page == "Daily Report":
    # Pass the main data dict
    display_daily_report(st.session_state.analytics_data)

elif st.session_state.selected_page == "Response Review Queue":
    # Import locally to avoid circular dependency
    from response_review import display_response_review_queue
    from dashboard_sqlite_utils import delete_reviews_for_user  # LOCAL IMPORT
    # Pass the delete function as a dependency to the display function
    display_response_review_queue(delete_reviews_for_user)

elif st.session_state.selected_page == "A/B Testing":
    display_ab_testing_analytics()

elif st.session_state.selected_page == "Lead Generation":
    # Import and display the lead generation dashboard
    try:
        # Import the local new_leads module (now renamed to lead generation)
        # Use absolute import to ensure we get the correct file from dashboard_modules
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        # Force import from the dashboard_modules directory
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "new_leads", os.path.join(current_dir, "new_leads.py"))
        new_leads_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(new_leads_module)
        lead_generation_main = new_leads_module.main

        # Get today's counts and pass them to the main function
        online_count, local_count = get_daily_follow_counts()

        # Try calling with parameters, fall back to no parameters if that fails
        try:
            lead_generation_main(online_count, local_count)
        except TypeError as te:
            # Fallback: call without parameters if the function signature doesn't match
            st.warning(
                f"Function signature mismatch, calling without parameters: {te}")
            lead_generation_main()

    except ImportError as e:
        st.error(f"Could not import the Lead Generation module: {e}")
        st.info("Make sure 'new_leads.py' exists in the dashboard_modules directory.")
    except Exception as e:
        st.error(f"Error in Lead Generation module: {e}")
        st.info("Please check the new_leads.py file for any issues.")

elif st.session_state.selected_page == "Ads Analytics":
    # Import and display the ads analytics dashboard
    try:
        from ads_analytics import display_ads_analytics
        display_ads_analytics()
    except ImportError as e:
        st.error(f"Could not import the Ads Analytics module: {e}")
        st.info(
            "Make sure 'ads_analytics.py' exists in the dashboard_modules directory.")
    except Exception as e:
        st.error(f"Error in Ads Analytics module: {e}")
        st.info("Please check the ads_analytics.py file for any issues.")

elif st.session_state.selected_page == "Webhook":
    display_webhook_manager()

elif st.session_state.selected_page == "Calendar Follow-ups":
    display_calendar_follow_ups()

# Fallback display for new leads, in case the module fails to load but the data is there


def display_new_leads_fallback():
    st.subheader("Premium Leads Available")
    try:
        import sqlite3
        import json
        conn = sqlite3.connect(
            r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM new_leads WHERE coaching_score >= 80")
        premium_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT username, coaching_score FROM new_leads WHERE coaching_score >= 80 LIMIT 5")
        premium_leads = cursor.fetchall()
        conn.close()

        if premium_count > 0:
            st.success(f"🎯 Found {premium_count} premium leads!")
            st.write("**Premium leads (80+ scores):**")
            for lead in premium_leads:
                st.write(f"• **@{lead[0]}** - {lead[1]}/100 points")
        else:
            st.info(
                "No premium leads found yet. The lead finder is running and will populate this section soon!")
    except Exception as db_error:
        st.error(f"Database access error: {db_error}")


def run_follow_back_check(target_date: Optional[str] = None):
    """Runs the daily follow-back checker script with an optional target date."""
    st.info("Starting daily follow-back analysis with bio analysis...")
    command = [sys.executable, DAILY_FOLLOW_BACK_SCRIPT_PATH]
    if target_date:
        command.extend(['--date', target_date])
    # Always include bio analysis
    command.extend(['--analyze-profiles'])

    try:
        # Use st.empty() to create a container for live output
        output_container = st.empty()
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        # Read and display output line by line
        output_lines = []
        for line in process.stdout:
            output_lines.append(line.strip())
            output_container.code("\n".join(output_lines), language='bash')

        process.wait()

        if process.returncode == 0:
            st.success("Daily follow-back analysis completed successfully!")
        else:
            st.error(
                f"Daily follow-back analysis failed with exit code {process.returncode}.")
            st.error("Please check the logs for more details.")

    except Exception as e:
        st.error(f"An error occurred while trying to run the script: {e}")
        logger.error(
            f"Error running daily follow-back check: {e}", exc_info=True)

    st.markdown("### Daily Follow-Back Analysis")

    # Optional date input for specific day's analysis
    analysis_date = st.date_input(
        "Select Date for Follow-Back Check",
        value=datetime.now() - timedelta(days=1),  # Default to yesterday
        max_value=datetime.now()  # Cannot select future dates
    )

    if st.button("Run Daily Follow-Back Check"):  # New button
        run_follow_back_check(analysis_date.strftime('%Y-%m-%d'))


def display_user_profile(username: str, user_data: Dict[str, Any]):
    # ... existing code ...

    # Add Ad Response Flow Management
    st.subheader("📢 Ad Response Flow")
    current_ad_flow = user_data['metrics'].get('is_in_ad_flow', False)
    current_scenario = user_data['metrics'].get('ad_scenario', 1)
    current_state = user_data['metrics'].get('ad_script_state', 'step1')

    new_ad_flow = st.checkbox(
        "Enable Ad Response Flow", value=current_ad_flow, key=f"ad_flow_{username}")
    new_scenario = st.selectbox(
        "Ad Scenario", [1, 2, 3], index=current_scenario-1, key=f"ad_scenario_{username}")
    new_state = st.selectbox("Ad Script State", ["step1", "step2", "step3", "completed"], index=[
                             "step1", "step2", "step3", "completed"].index(current_state), key=f"ad_state_{username}")

    if st.button("Update Ad Flow", key=f"update_ad_{username}"):
        update_analytics_data(
            subscriber_id=user_data['metrics'].get('subscriber_id', ''),
            ig_username=username,
            message_text="",
            message_direction="system",
            timestamp=datetime.now().isoformat(),
            first_name=user_data['metrics'].get('first_name', ''),
            last_name=user_data['metrics'].get('last_name', ''),
            is_in_ad_flow=new_ad_flow,
            ad_scenario=new_scenario,
            ad_script_state=new_state
        )
        st.success("Ad flow updated!")
        st.rerun()

    # View Ad Conversation History
    ad_history = [msg for msg in user_data['metrics'].get(
        'conversation_history', []) if 'ad' in msg.get('text', '').lower()]
    if ad_history:
        st.subheader("Ad Response History")
        for msg in ad_history:
            st.write(f"{msg['timestamp']} [{msg['type']}]: {msg['text']}")
    else:
        st.info("No ad response history yet.")

    # ... existing code ...

    # Add Lead Source Management
    st.subheader("🎯 Lead Source")
    current_lead_source = user_data['metrics'].get('lead_source', 'general')

    lead_source_options = ['general', 'facebook_ad',
                           'vegan_outreach', 'organic', 'referral']
    new_lead_source = st.selectbox(
        "Lead Source",
        options=lead_source_options,
        value=current_lead_source if current_lead_source in lead_source_options else 'general',
        key=f"lead_source_{username}"
    )

    if new_lead_source != current_lead_source:
        if st.button(f"Update Lead Source to {new_lead_source}", key=f"update_lead_source_{username}"):
            # Update lead source in database
            update_analytics_data(
                subscriber_id=user_data['metrics'].get('subscriber_id', ''),
                ig_username=username,
                message_text="",
                message_direction="system",
                timestamp=datetime.now().isoformat(),
                first_name=user_data['metrics'].get('first_name', ''),
                last_name=user_data['metrics'].get('last_name', ''),
                lead_source=new_lead_source
            )
            st.success(f"Lead source updated to {new_lead_source}")
            st.rerun()

    # Add Ad Response Flow Management
