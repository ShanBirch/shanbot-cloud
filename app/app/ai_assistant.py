import streamlit as st
import json
import logging
import subprocess
import os
import sys
from datetime import datetime, timezone, timedelta

# Import necessary utilities
from .dashboard_utils import call_gemini_with_retries, is_user_active

# Import components from other modules
from .user_profiles import display_conversation
from .followup_service import (
    load_scheduled_followups,
    save_scheduled_followups,
    process_scheduled_followups
)

# Set up logging for this module
logger = logging.getLogger(__name__)


def run_external_command(command, working_dir=None):
    """Run an external command and return the output."""
    try:
        # Log the command being executed
        logger.info(f"Executing command: {command}")

        # Set up the process with appropriate working directory
        process_args = {
            "shell": True,
            "capture_output": True,
            "text": True,
            "check": False
        }

        if working_dir:
            process_args["cwd"] = working_dir

        result = subprocess.run(command, **process_args)

        # Log command completion
        logger.info(f"Command completed with exit code: {result.returncode}")
        if result.returncode != 0:
            logger.warning(f"Command stderr: {result.stderr}")

        return result.stdout + result.stderr
    except Exception as e:
        logger.error(f"Command execution error: {e}", exc_info=True)
        return f"Error executing command: {str(e)}"


def run_shanbot_component(component_name):
    """Run a specific Shanbot component and return the result."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    component_commands = {
        "followersbot1": "python followersbot.py",
        "followersbot2": "python followersbot2.py",
        "followersbot3": "python followersbot3.py",
        "story": "python story1.py",
        "checkin": "python checkin_current.py",
        "video": "python simple_blue_video.py",
        "webhook": "python -m uvicorn manychat_webhook_fixed:app --host 0.0.0.0 --port 8000"
    }

    if component_name not in component_commands:
        return f"Unknown component: {component_name}. Available components: {', '.join(component_commands.keys())}"

    command = component_commands[component_name]
    return run_external_command(command, working_dir=base_dir)


def handle_user_command(command, conversation_metrics):
    """Process user commands and return appropriate responses."""
    command = command.lower().strip()

    # Command to view user profile
    if command.startswith("show user") or command.startswith("get user") or command.startswith("view user"):
        user_id = command.split("user", 1)[1].strip()
        # Check if this is a username or ID
        for uid, data in conversation_metrics.items():
            username = data.get("ig_username", "").lower()
            if user_id == uid or user_id == username:
                st.session_state.view_profile = uid
                return f"Setting view to user profile: {username or uid}. Please navigate to the User Profiles tab."
        return f"User '{user_id}' not found in the database."

    # Command to run Shanbot components
    elif "run" in command and any(bot in command for bot in ["followersbot", "story", "checkin", "video", "webhook"]):
        component_to_run = None

        # Determine which component to run
        if "followersbot3" in command:
            component_to_run = "followersbot3"
        elif "followersbot2" in command:
            component_to_run = "followersbot2"
        elif "followersbot" in command:
            component_to_run = "followersbot1"
        elif "story" in command:
            component_to_run = "story"
        elif "checkin" in command:
            component_to_run = "checkin"
        elif "video" in command:
            component_to_run = "video"
        elif "webhook" in command:
            component_to_run = "webhook"

        if component_to_run:
            return f"Starting {component_to_run}...\n\n{run_shanbot_component(component_to_run)}"
        else:
            return "Could not determine which Shanbot component to run. Please specify."

    # Command to schedule a follow-up
    elif "schedule follow" in command or "create follow" in command:
        parts = command.split("for user", 1)
        if len(parts) < 2:
            return "Please specify a user. Format: schedule follow-up for user [username] in [hours] with message [text]"

        user_part = parts[1].strip()
        user_id = None
        username = None
        hours = 1.0  # Default
        message = f"Hey! This is an automatic follow-up created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Extract user
        for uid, data in conversation_metrics.items():
            name = data.get("ig_username", "").lower()
            if name and name in user_part.lower():
                user_id = uid
                username = name
                break

        if not user_id:
            # Try direct ID match
            for uid in conversation_metrics.keys():
                if uid in user_part:
                    user_id = uid
                    username = conversation_metrics[uid].get(
                        "ig_username", uid)
                    break

        if not user_id:
            return "User not found. Please check the username or ID."

        # Extract time if specified
        if "in " in user_part and " hour" in user_part:
            try:
                time_part = user_part.split(
                    "in ", 1)[1].split(" hour")[0].strip()
                hours = float(time_part)
            except:
                pass

        # Extract message if specified
        if "message " in user_part:
            message = user_part.split("message ", 1)[1].strip()

        # Create follow-up
        try:
            scheduled_time = (datetime.now(timezone.utc) +
                              timedelta(hours=hours)).isoformat()

            followups = load_scheduled_followups()
            followups[user_id] = {
                "username": username,
                "scheduled_time": scheduled_time,
                "message": message,
                "user_id": user_id
            }
            save_scheduled_followups(followups)
            return f"Follow-up scheduled for {username} in {hours} hours with message: {message}"
        except Exception as e:
            return f"Error scheduling follow-up: {str(e)}"

    # Command to process follow-ups
    elif "process follow" in command:
        try:
            result = process_scheduled_followups()
            return f"Processed scheduled follow-ups. Sent: {result.get('sent', 0)}, Failed: {result.get('failed', 0)}"
        except Exception as e:
            return f"Error processing follow-ups: {str(e)}"

    # Command to get stats/analytics
    elif "stats" in command or "analytics" in command:
        if "active" in command:
            active_count = sum(1 for data in conversation_metrics.values()
                               if is_user_active(data.get("last_message_timestamp")))
            return f"Currently {active_count} active users out of {len(conversation_metrics)} total users."

        if "signup" in command or "conversion" in command:
            total_signups = sum(1 for data in conversation_metrics.values()
                                if data.get("signup_recorded", False))
            total_offers = sum(1 for data in conversation_metrics.values()
                               if data.get("offer_mentioned_in_conv", False))
            conversion = (total_signups / total_offers *
                          100) if total_offers > 0 else 0
            return f"Total signups: {total_signups}, Conversion rate: {conversion:.1f}%"

        # Default stats
        return f"Total users: {len(conversation_metrics)}, Total follow-ups: {len(load_scheduled_followups())}"

    # Command to list all available Shanbot components
    elif "list components" in command or "list bots" in command:
        return """
        Available Shanbot components:
        
        - followersbot1 - Basic Instagram followers bot
        - followersbot2 - Advanced Instagram DM bot
        - followersbot3 - Alternative Instagram bot
        - story - Instagram Story interaction bot
        - checkin - Trainerize check-in automation
        - video - Client personalized video generator
        - webhook - ManyChat webhook handler
        
        Use 'run [component]' to start any of these components.
        """

    # Help command
    elif "help" in command:
        help_text = """
        Available commands:
        - show/view user [username or ID] - View a user profile
        - run followersbot[1/2/3] - Run Instagram follower automation
        - run story - Run Instagram story interaction bot
        - run checkin - Run Trainerize check-in automation
        - run video - Generate personalized client videos
        - run webhook - Start ManyChat webhook handler
        - list components - List all available Shanbot components
        - schedule follow-up for user [username] in [hours] with message [text] - Create a follow-up
        - process follow-ups - Process all scheduled follow-ups
        - stats/analytics [type] - Show statistics (active, signups, etc.)
        - help - Show this help message
        """
        return help_text

    # Unknown command - use Gemini for general queries
    else:
        # Prepare data context
        global_data_str = json.dumps(st.session_state.global_metrics, indent=2)
        conv_summary = f"Total conversations: {len(conversation_metrics)}"

        gemini_prompt = f"""
You are Shanbot, a powerful AI assistant with full access to Instagram analytics data. 
Answer questions or respond to commands based on the provided data.

**Data Context:**
**1. Global Metrics:**
```json
{global_data_str}
```

**2. Conversation Data Summary:**
{conv_summary}

**User Input:**
{command}

**Response:**
"""

        try:
            ai_response = call_gemini_with_retries(
                prompt=gemini_prompt,
                purpose="shanbot assistant"
            )

            if ai_response is None:
                ai_response = "Sorry, I couldn't process that. Please try a different command or question."

            return ai_response

        except Exception as e:
            logger.error(f"AI Error: {e}", exc_info=True)
            return f"Error processing your request: {str(e)}"


def display_ai_assistant_page():
    """Renders the minimalist AI assistant page."""

    # Use custom CSS to center content and create minimalist design
    st.markdown("""
    <style>
    /* Hide ALL interface elements */
    .stApp header {display: none;}
    header {visibility: hidden;} 
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    h1, h2, h3, h4, h5, h6 {display: none;}
    .stMarkdown {display: none;}
    hr {display: none;}
    
    /* Override specific footer elements */
    .element-container:has(hr) {display: none !important;}
    .element-container:has(.stMarkdown) {display: none !important;}
    
    /* Remove bottom padding from the main container */
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        height: 100vh;
        max-width: 100% !important;
    }
    
    /* Center the input exactly in the middle of the screen */
    .center-input {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        width: 100%;
        position: fixed;
        top: 0;
        left: 0;
        z-index: 1000;
    }
    
    /* Style the input field container */
    .input-container {
        width: 70%;
        max-width: 600px;
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    /* Style the chat history - show when there are messages */
    .chat-history {
        width: 90%;
        max-width: 800px;
        margin: 20px auto;
        overflow-y: auto;
        max-height: 40vh;
        padding: 15px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        position: absolute;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 100;
    }
    
    /* Message styling */
    .user-message {
        background: #f0f7ff;
        padding: 10px 15px;
        border-radius: 18px 18px 18px 0;
        margin: 5px 0;
        max-width: 80%;
        align-self: flex-start;
    }
    
    .bot-message {
        background: #e6f7f2;
        padding: 10px 15px;
        border-radius: 18px 18px 0 18px;
        margin: 5px 0;
        max-width: 80%;
        align-self: flex-end;
        margin-left: auto;
    }
    
    /* Show spinner more prominently */
    .stSpinner {
        display: flex;
        justify-content: center;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Hide the footer
    hide_footer = """
    <style>
    footer {visibility: hidden !important;}
    footer:after {visibility: hidden !important; content: "" !important;}
    .element-container:nth-last-child(-n+2) {display: none !important;}
    </style>
    """
    st.markdown(hide_footer, unsafe_allow_html=True)

    # Initialize chat history in session state if it doesn't exist
    if "ai_assistant_messages" not in st.session_state:
        st.session_state.ai_assistant_messages = []

    # Initialize processing state
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    # Create a container for chat history at the top
    chat_container = st.container()

    # Display chat history if there are messages
    if st.session_state.ai_assistant_messages:
        with chat_container:
            st.markdown('<div class="chat-history">', unsafe_allow_html=True)
            for message in st.session_state.ai_assistant_messages:
                if message["role"] == "user":
                    st.markdown(
                        f'<div class="user-message">**You:** {message["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="bot-message">**Shanbot:** {message["content"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # Place the input field in the center of the screen
    st.markdown('<div class="center-input"><div class="input-container">',
                unsafe_allow_html=True)
    prompt = st.text_input("", placeholder="Hey ShanBot",
                           key="shanbot_input", label_visibility="collapsed")
    st.markdown('</div></div>', unsafe_allow_html=True)

    # Empty container to push footer content out
    st.markdown('<div style="height:500px;"></div>', unsafe_allow_html=True)

    if prompt and not st.session_state.is_processing:
        st.session_state.is_processing = True

        # Add user message to chat history
        st.session_state.ai_assistant_messages.append(
            {"role": "user", "content": prompt})

        # Process the command
        try:
            with st.spinner("Processing..."):
                response = handle_user_command(
                    prompt, st.session_state.conversation_metrics)

                # Add assistant response to chat history
                st.session_state.ai_assistant_messages.append(
                    {"role": "assistant", "content": response})
        except Exception as e:
            # Handle errors and add error message to chat
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            if "quota" in str(e).lower():
                error_msg = "Sorry, I've reached my API quota limit. Please try again in a few minutes."

            st.session_state.ai_assistant_messages.append(
                {"role": "assistant", "content": error_msg})

        # Reset processing state
        st.session_state.is_processing = False

        # Force a rerun to update the display
        st.rerun()
