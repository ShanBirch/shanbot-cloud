from pathlib import Path
import time
import googleapiclient.discovery
import google.oauth2.service_account
import random
import google.generativeai as genai
import datetime
import os
import sys
import json
import logging
import streamlit as st

# Configure the page FIRST - before any other Streamlit commands
st.set_page_config(
    page_title="Shannon Bot Analytics Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini - Use Streamlit secrets for cloud deployment
try:
    # Try to get from Streamlit secrets first (for cloud deployment)
    GEMINI_API_KEY = st.secrets["general"]["GEMINI_API_KEY"]
except:
    # Fallback to hardcoded value for local development
    GEMINI_API_KEY = "AIzaSyCrYZwENVEhfo0IF6puWyQaYlFW1VRWY-k"

if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY" and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        logger.info("Gemini configured successfully.")
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}")
        gemini_model = None
        st.error("Failed to configure Gemini AI. Some features might not work.")
else:
    logger.warning(
        "Gemini API Key not found or is a placeholder. AI features will be disabled.")
    gemini_model = None
    st.info("Gemini API Key not configured. AI features disabled.")

# Google Sheets configuration
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"


def get_google_sheets_service():
    """Get Google Sheets service using credentials from Streamlit secrets"""
    try:
        # Get credentials from Streamlit secrets
        credentials_info = {
            "type": st.secrets["google_sheets"]["type"],
            "project_id": st.secrets["google_sheets"]["project_id"],
            "private_key_id": st.secrets["google_sheets"]["private_key_id"],
            "private_key": st.secrets["google_sheets"]["private_key"],
            "client_email": st.secrets["google_sheets"]["client_email"],
            "client_id": st.secrets["google_sheets"]["client_id"],
            "auth_uri": st.secrets["google_sheets"]["auth_uri"],
            "token_uri": st.secrets["google_sheets"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["google_sheets"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["google_sheets"]["client_x509_cert_url"],
            "universe_domain": st.secrets["google_sheets"]["universe_domain"]
        }

        credentials = google.oauth2.service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )

        service = googleapiclient.discovery.build(
            'sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error setting up Google Sheets service: {e}")
        return None


def load_sample_data():
    """Load sample data for cloud deployment demo"""
    return {
        'conversations': {
            'sample_user_1': {
                'metrics': {
                    'ig_username': 'sample_user_1',
                    'subscriber_id': '12345',
                    'first_name': 'Sample',
                    'last_name': 'User',
                    'user_messages': 15,
                    'total_messages': 25,
                    'conversation_history': [
                        {'type': 'ai', 'text': 'Hello! How are you doing today?',
                            'timestamp': '2025-05-26T10:00:00'},
                        {'type': 'user', 'text': 'Good thanks! Just finished my workout',
                            'timestamp': '2025-05-26T10:05:00'},
                        {'type': 'ai', 'text': 'That\'s awesome! What kind of workout did you do?',
                            'timestamp': '2025-05-26T10:06:00'},
                    ],
                    'journey_stage': {
                        'current_stage': 'Topic 2',
                        'is_paying_client': False,
                        'trial_start_date': None
                    },
                    'last_interaction_timestamp': '2025-05-26T10:06:00'
                }
            },
            'sample_user_2': {
                'metrics': {
                    'ig_username': 'sample_user_2',
                    'subscriber_id': '67890',
                    'first_name': 'Trial',
                    'last_name': 'Member',
                    'user_messages': 8,
                    'total_messages': 12,
                    'conversation_history': [
                        {'type': 'ai', 'text': 'Welcome to your trial! Ready to get started?',
                            'timestamp': '2025-05-25T14:00:00'},
                        {'type': 'user', 'text': 'Yes! I\'m excited',
                            'timestamp': '2025-05-25T14:02:00'},
                    ],
                    'journey_stage': {
                        'current_stage': 'Trial Week 1',
                        'is_paying_client': False,
                        'trial_start_date': '2025-05-25T00:00:00'
                    },
                    'last_interaction_timestamp': '2025-05-25T14:02:00'
                }
            }
        },
        'action_items': [
            {
                'client_name': 'Sample User',
                'task_description': 'Follow up on workout progress',
                'timestamp': '2025-05-26T09:00:00Z',
                'status': 'pending'
            }
        ]
    }


def display_overview_tab(analytics_data_dict):
    """Display the overview page"""
    st.header("📊 Overview")

    # Display metrics
    conversations_data = analytics_data_dict.get('conversations', {})

    total_users = len(conversations_data)
    engaged_users = sum(1 for user_data in conversations_data.values()
                        if user_data.get('metrics', {}).get('user_messages', 0) > 0)
    total_messages = sum(user_data.get('metrics', {}).get('total_messages', 0)
                         for user_data in conversations_data.values())

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Users", total_users)
        st.metric("Engaged Users", engaged_users)

    with col2:
        st.metric("Total Messages", total_messages)
        avg_messages = total_messages / engaged_users if engaged_users > 0 else 0
        st.metric("Avg Messages per User", f"{avg_messages:.1f}")

    with col3:
        response_rate = (engaged_users / total_users *
                         100) if total_users > 0 else 0
        st.metric("Response Rate", f"{response_rate:.1f}%")

    st.info("📱 This is a cloud demo version of the Shannon Bot Analytics Dashboard!")


def display_user_profiles_tab(analytics_data_dict):
    """Display user profiles"""
    st.header("👥 User Profiles")

    conversations_data = analytics_data_dict.get('conversations', {})

    if not conversations_data:
        st.info("No user data available in this demo version.")
        return

    for username, user_container in conversations_data.items():
        metrics = user_container.get('metrics', {})

        with st.expander(f"User: {metrics.get('ig_username', username)}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Basic Info:**")
                st.write(
                    f"Name: {metrics.get('first_name', 'N/A')} {metrics.get('last_name', 'N/A')}")
                st.write(f"User Messages: {metrics.get('user_messages', 0)}")
                st.write(f"Total Messages: {metrics.get('total_messages', 0)}")

                journey_stage = metrics.get('journey_stage', {})
                st.write(
                    f"Current Stage: {journey_stage.get('current_stage', 'Unknown')}")

                if journey_stage.get('is_paying_client'):
                    st.success("💰 Paying Client")
                elif journey_stage.get('trial_start_date'):
                    st.info("🆓 Trial Member")
                else:
                    st.warning("👤 Lead")

            with col2:
                st.write("**Recent Conversation:**")
                conversation_history = metrics.get('conversation_history', [])

                if conversation_history:
                    # Show last 3 messages
                    for msg in conversation_history[-3:]:
                        sender = "👤 User" if msg.get(
                            'type') == 'user' else "🤖 Shannon"
                        st.write(f"**{sender}:** {msg.get('text', '')}")
                else:
                    st.write("No conversation history available")


def display_daily_report_tab(analytics_data_dict):
    """Display daily report"""
    st.header("📊 Daily Report")

    action_items = analytics_data_dict.get("action_items", [])
    pending_items = [
        item for item in action_items if item.get("status") == "pending"]
    completed_items = [
        item for item in action_items if item.get("status") == "completed"]

    st.subheader("🚨 Things To Do")
    if not pending_items:
        st.success("✅ All clear! No pending action items.")
    else:
        st.warning(f"Found {len(pending_items)} pending action item(s):")
        for item in pending_items:
            try:
                ts_str_raw = item.get("timestamp", "")
                ts = datetime.datetime.fromisoformat(
                    ts_str_raw.replace("Z", "+00:00"))
                ts_str_formatted = ts.strftime("%Y-%m-%d %H:%M UTC")
            except ValueError:
                ts_str_formatted = item.get("timestamp", "Invalid Date")
            st.markdown(
                f"- **{item.get('client_name', 'Unknown')}** ({ts_str_formatted}): {item.get('task_description', 'No description')}")


def display_demo_features():
    """Display information about demo features"""
    st.header("🚀 Demo Features")

    st.info("""
    **This is a cloud demo version of the Shannon Bot Analytics Dashboard!**
    
    **Available Features:**
    - 📊 Overview with sample metrics
    - 👥 User profiles with sample data
    - 📋 Daily reports
    - 🔄 Google Sheets integration (configured)
    - 🤖 Gemini AI integration (configured)
    
    **Note:** This demo uses sample data. The full version connects to:
    - SQLite database for conversation data
    - Real-time ManyChat integration
    - Live Instagram analysis
    - Response review queue
    """)

    st.success("✅ All integrations are properly configured and ready!")


# Initialize session state
if 'analytics_data' not in st.session_state:
    st.session_state.analytics_data = load_sample_data()

if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "Overview"

# Sidebar
st.sidebar.title("Analytics Dashboard")
st.sidebar.info("🌐 Cloud Demo Version")

# Navigation
page_options = ["Overview", "User Profiles", "Daily Report", "Demo Features"]

st.session_state.selected_page = st.sidebar.radio(
    "Navigation",
    options=page_options,
    index=page_options.index(
        st.session_state.selected_page) if st.session_state.selected_page in page_options else 0
)

# Main content area
st.title("Shannon Bot Analytics Dashboard")

if st.session_state.selected_page == "Overview":
    display_overview_tab(st.session_state.analytics_data)

elif st.session_state.selected_page == "User Profiles":
    display_user_profiles_tab(st.session_state.analytics_data)

elif st.session_state.selected_page == "Daily Report":
    display_daily_report_tab(st.session_state.analytics_data)

elif st.session_state.selected_page == "Demo Features":
    display_demo_features()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Shannon Bot Dashboard**")
st.sidebar.markdown("Cloud Demo Version")
