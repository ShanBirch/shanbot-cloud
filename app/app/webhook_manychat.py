# from .schemas.manychat import ManyChat_Webhook_Payload # Removed/Commented out
from typing import Dict, Any, List, Optional, Tuple, Union
import json
import requests
import logging
import hashlib
import hmac
import os
import uvicorn
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi import FastAPI, Request, HTTPException, Header, Depends
import google.generativeai as genai  # Added Gemini import
# Add Google Sheets imports
import google.oauth2.service_account
import googleapiclient.discovery
import re
from datetime import datetime, timezone
import pytz  # Make sure pytz is imported
from app import prompts  # Import prompts from the app package
import time
from fastapi.middleware.cors import CORSMiddleware  # Add this import
import asyncio  # Added to allow async delays between messages
from collections import defaultdict
import dateutil.parser as parser
import httpx
from checkin_new_1904 import TrainerizeAutomation
from pydantic import BaseModel, Field
from google.cloud import speech_v1
import io
import tempfile

# Set up logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("manychat_webhook")
logger.info("Logging configured.")  # Confirm logging setup

# Initialize audio processing flag
AUDIO_PROCESSING_AVAILABLE = False
try:
    import subprocess
    import tempfile
    AUDIO_PROCESSING_AVAILABLE = True
    logger.info("Audio processing is available using ffmpeg")
except ImportError:
    logger.warning(
        "Audio processing is not available - voice messages will be handled differently")

# Configure FFmpeg paths
FFMPEG_PATH = r"C:\ffmpeg\ffmpeg.exe"
FFPROBE_PATH = r"C:\ffmpeg\ffprobe.exe"
os.environ["FFMPEG_BINARY"] = FFMPEG_PATH
os.environ["FFPROBE_BINARY"] = FFPROBE_PATH

# Download FFmpeg if not present
if not os.path.exists(FFMPEG_PATH) or not os.path.exists(FFPROBE_PATH):
    try:
        import urllib.request
        import zipfile

        # Download FFmpeg
        ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        zip_path = r"C:\ffmpeg\ffmpeg.zip"

        if not os.path.exists(r"C:\ffmpeg"):
            os.makedirs(r"C:\ffmpeg")

        print("Downloading FFmpeg...")
        urllib.request.urlretrieve(ffmpeg_url, zip_path)

        print("Extracting FFmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(r"C:\ffmpeg")

        # Move files to correct location
        import shutil
        ffmpeg_dir = next(d for d in os.listdir(
            r"C:\ffmpeg") if d.startswith("ffmpeg"))
        shutil.move(os.path.join(r"C:\ffmpeg", ffmpeg_dir,
                    "bin", "ffmpeg.exe"), FFMPEG_PATH)
        shutil.move(os.path.join(r"C:\ffmpeg", ffmpeg_dir,
                    "bin", "ffprobe.exe"), FFPROBE_PATH)

        print("FFmpeg setup complete!")
    except Exception as e:
        print(f"Error setting up FFmpeg: {e}")

ig_usernames: Dict[str, str] = {}

# --- Add PIL for image type check ---
# Make sure these are added near the top with other imports
try:
    import PIL
    from PIL import Image
    import io
    PIL_AVAILABLE = True
    logger.info("PIL library found. Image verification enabled.")
except ImportError:
    PIL_AVAILABLE = False
    logger.warning(
        "PIL library not found. Image verification will be skipped.")
# --- End PIL Import ---

# --- Pydantic Models for Trainerize Actions ---


class ExerciseDefinition(BaseModel):
    name: str
    sets: str
    reps: str


class WorkoutDefinition(BaseModel):
    day_type: str = Field(..., description="Type of workout day. Supported values: 'back', 'chest_tris', 'shoulders_core', 'legs', 'arms_core'.")
    exercises_list: List[ExerciseDefinition]


class BuildProgramRequest(BaseModel):
    client_name: str
    program_name: str
    workout_definitions: List[WorkoutDefinition]


# --- Initialize Trainerize Automation ---
# This creates a single instance when the FastAPI app starts
# It will manage the persistent Selenium browser session
logger.info("Initializing TrainerizeAutomation instance...")
try:
    # Pass None for API key for now, assuming core Selenium doesn't need it immediately
    trainerize_instance = TrainerizeAutomation(openai_api_key=None)
    # Optionally, trigger login immediately upon startup (or handle it lazily later)
    # logger.info("Attempting initial Trainerize login...")
    # login_success = trainerize_instance.login(USERNAME, PASSWORD) # You'd need USERNAME/PASSWORD constants defined
    # if not login_success:
    #     logger.error("Initial Trainerize login failed on startup!")
    # else:
    #     logger.info("Initial Trainerize login successful.")
    logger.info("TrainerizeAutomation instance created.")
except Exception as e:
    logger.error(
        f"Failed to initialize TrainerizeAutomation: {e}", exc_info=True)
    trainerize_instance = None  # Set to None if initialization fails

# --- FastAPI App Definition ---
app = FastAPI(title="Instagram Webhook Receiver")  # Renamed title

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Your ManyChat API key
MANYCHAT_API_KEY = "996573:5b6dc180662de1be343655db562ee918"
# Instagram Graph API token (reuse your Page token) for username lookups
IG_GRAPH_ACCESS_TOKEN = "EAAJaUdyYIDgBO2TVUXn3nZChZBUEyJlkUi5oZCbVKm5TOMZA3l33bQaMZCRkiLNsZACYnxg8B1LarhVHeb0HmPQoAZBSEHfAw3B0ZAPHp1jx5Etp7TmarfSlfb5QJmMZCfIY7lDmRaqzhxtgxxGlniEukynpJoQHBKVK6ppbkRDjGTfUzVGwNvPEajwYScllwZACYZD"

# --- Google Sheets Configuration START ---
# Path to your credentials file
SHEETS_CREDENTIALS_PATH = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\sheets_credentials.json"
# The ID of your spreadsheet (General Chat)
SPREADSHEET_ID = "1nDVn6jhkYBubVTQqbYU3PKo_WooeuTsQzsaNNcQdJlo"
# The range containing the data - CHANGED to include Column E
RANGE_NAME = "Sheet1!A:E"

# Onboarding Google Sheets Configuration
# Use the Coaching Onboarding Form spreadsheet ID
# Correct Coaching Onboarding Form
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
# Update range to include all columns from A to AAF in the Coaching Onboarding Form
# Make sure this points to the correct sheet tab name
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"

# Define the scopes required - Read-only is sufficient
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
# --- Google Sheets Configuration END ---

# --- Gemini Configuration START ---
# WARNING: Load API Key from environment variable for security!
# Using your provided key as fallback
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y")
if not GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY environment variable not set. Gemini calls will fail.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to configure Gemini API: {e}", exc_info=True)

# Choose your Gemini model
# Main model (set to fast, reliable flash-lite)
GEMINI_MODEL_PRO = "gemini-2.5-flash-lite"
# First fallback model (flash thinking)
GEMINI_MODEL_FLASH = "gemini-2.0-flash-thinking-exp-01-21"
# Second fallback model (standard flash)
GEMINI_MODEL_FLASH_STANDARD = "gemini-2.0-flash"
RETRY_DELAY = 16  # Seconds to wait before retry
MAX_RETRIES = 3  # Maximum number of retry attempts


def call_gemini_with_retry(model_name: str, prompt: str, retry_count: int = 0) -> Optional[str]:
    """
    Call Gemini API with retry logic and multiple fallback models.

    Args:
        model_name: Name of the Gemini model to use
        prompt: The prompt to send to Gemini
        retry_count: Current retry attempt number

    Returns:
        Generated text or None if all retries fail
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) and retry_count < MAX_RETRIES:
            # Rate limit: if primary model, fallback to flash-thinking; otherwise retry same model
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Rate limit hit for {model_name}. Falling back to flash-thinking model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            else:
                wait_time = RETRY_DELAY * (retry_count + 1)
                logger.warning(
                    f"Rate limit hit. Waiting {wait_time} seconds before retry {retry_count + 1} on {model_name}")
                time.sleep(wait_time)
                return call_gemini_with_retry(model_name, prompt, retry_count + 1)
        elif retry_count < MAX_RETRIES:  # Other errors, try fallback models
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Main model failed: {e}. Trying first fallback model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            elif model_name == GEMINI_MODEL_FLASH:
                logger.warning(
                    f"First fallback model failed: {e}. Trying second fallback model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry(GEMINI_MODEL_FLASH_STANDARD, prompt, retry_count + 1)
        logger.error(f"All Gemini attempts failed: {e}")
        return None
# --- Gemini Configuration END ---


def split_response_into_messages(text: str) -> List[str]:
    """Split response text into up to 3 messages of roughly equal length."""
    logger.info(f"Splitting response of length {len(text)}")

    # If text is short enough, return as single message
    if len(text) <= 150:
        return [text]

    # Split into sentences while preserving punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # If only 1-2 sentences, return as is
    if len(sentences) <= 2:
        return sentences

    # For 3+ sentences, combine into up to 3 messages
    result = []
    current_message = ""
    target_length = len(text) / 3  # Aim for roughly equal thirds

    for sentence in sentences:
        if len(current_message) + len(sentence) <= target_length or not current_message:
            if current_message:
                current_message += " "
            current_message += sentence
        else:
            result.append(current_message)
            current_message = sentence

        # Don't exceed 3 messages
        if len(result) == 2:
            result.append(current_message + " " +
                          " ".join(sentences[sentences.index(sentence)+1:]))
            break

    # Handle case where we haven't hit 3 messages yet
    if current_message and len(result) < 3:
        result.append(current_message)

    logger.info(f"Split into {len(result)} messages")
    for i, msg in enumerate(result):
        logger.info(f"Message {i+1} length: {len(msg)}")

    return result


def format_conversation_history(history_list: List[Dict[str, str]]) -> str:
    """Formats the conversation history list into a readable string."""
    formatted_lines = []
    for entry in history_list:
        timestamp = entry.get("timestamp", "")
        msg_type = entry.get("type", "unknown").capitalize()
        text = entry.get("text", "")
        # Format timestamp nicely if possible (optional)
        try:
            # Attempt to parse and format timestamp
            dt_object = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00"))
            formatted_ts = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            formatted_ts = timestamp  # Fallback to original string

        formatted_lines.append(f"{formatted_ts} [{msg_type}]: {text}")
    return "\n".join(formatted_lines)


def get_user_data(ig_username: str) -> tuple[str, str, list, str, float]:
    """
    Load user data from analytics_data.json
    Returns: (formatted_conversation_history,
              bio, conversation_topics, interests, last_bot_timestamp)
    """
    logger.info(f"---> [get_user_data] Searching for user: '{ig_username}'")
    if not ig_username:
        logger.warning(
            "---> [get_user_data] No ig_username provided, returning empty data.")
        return "", "", [], "", 0

    analytics_file_path = r"C:\Users\Shannon\analytics_data.json"
    logger.info(
        f"---> [get_user_data] Attempting to load data from: {analytics_file_path}")

    try:
        with open(analytics_file_path, "r") as f:
            analytics_data = json.load(f)
            logger.info(
                f"---> [get_user_data] Successfully loaded {analytics_file_path}")

        conversations_data = analytics_data.get('conversations')
        if not isinstance(conversations_data, dict):
            logger.error(
                f"---> [get_user_data] 'conversations' key not found or is not a dictionary in analytics_data.json.")
            return "", "", [], "", 0

        search_ig_username_lower = ig_username.strip().lower()
        logger.info(
            f"---> [get_user_data] Searching for normalized username: '{search_ig_username_lower}' within 'conversations' data.")

        user_found = False
        for user_id, user_data in conversations_data.items():
            if not isinstance(user_data, dict):
                logger.warning(
                    f"---> [get_user_data] Skipping item for user_id '{user_id}' in 'conversations', not a dictionary.")
                continue

            # *** Access the nested 'metrics' dictionary ***
            metrics_data = user_data.get("metrics", {})
            if not isinstance(metrics_data, dict):
                logger.warning(
                    f"---> [get_user_data] No valid 'metrics' dictionary found for user_id '{user_id}'.")
                continue

            # *** Get ig_username from metrics_data ***
            json_ig_username = metrics_data.get("ig_username", None)
            logger.debug(
                f"---> [get_user_data] RAW username from JSON metrics for user '{user_id}': '{json_ig_username}' (Type: {type(json_ig_username)})")

            if isinstance(json_ig_username, str):
                json_ig_username_normalized = json_ig_username.strip().lower()
                logger.debug(
                    f"---> [get_user_data] Comparing '{search_ig_username_lower}' with JSON user '{json_ig_username}' (Normalized: '{json_ig_username_normalized}')")

                if json_ig_username_normalized == search_ig_username_lower:
                    user_found = True
                    logger.info(
                        f"---> [get_user_data] MATCH FOUND for '{ig_username}' (User ID: {user_id})")

                    # *** Get other data from metrics_data ***
                    history_list = metrics_data.get("conversation_history", [])
                    bio = metrics_data.get("bio", "")
                    topics = metrics_data.get("conversation_topics", [])
                    interests = metrics_data.get("interests", "")

                    # Get last bot response timestamp
                    last_bot_timestamp = 0
                    if history_list:
                        # Look through history in reverse to find last bot response
                        for entry in reversed(history_list):
                            if entry.get("type") == "ai":
                                try:
                                    timestamp_str = entry.get("timestamp", "")
                                    if timestamp_str:
                                        dt = parser.isoparse(timestamp_str)
                                        last_bot_timestamp = dt.timestamp()
                                        logger.info(
                                            f"---> [get_user_data] Found last bot response timestamp: {timestamp_str}")
                                        break
                                except Exception as e:
                                    logger.error(
                                        f"---> [get_user_data] Error parsing timestamp: {e}")
                                    continue

                    logger.info(
                        f"---> [get_user_data] Raw history list retrieved (length: {len(history_list)})")
                    formatted_history = format_conversation_history(
                        history_list)
                    logger.info(
                        f"---> [get_user_data] Formatted history length: {len(formatted_history)}")
                    logger.info(
                        f"---> [get_user_data] Returning data - Bio: {bool(bio)}, Topics: {len(topics)}, Interests: {bool(interests)}, Last Bot Timestamp: {last_bot_timestamp}")

                    return (formatted_history, bio, topics, interests, last_bot_timestamp)
                else:
                    logger.debug(
                        f"---> [get_user_data] Skipping comparison for user '{user_id}'; username ('{json_ig_username}') is missing or not a string.")

        if not user_found:
            logger.warning(
                f"---> [get_user_data] User '{ig_username}' NOT FOUND within 'conversations'['metrics'] in {analytics_file_path}")

        return "", "", [], "", 0

    except FileNotFoundError:
        logger.error(f"---> [get_user_data] {analytics_file_path} not found.")
        return "", "", [], "", 0
    except json.JSONDecodeError:
        logger.error(
            f"---> [get_user_data] Error decoding {analytics_file_path}.")
        return "", "", [], "", 0
    except Exception as e:
        logger.error(
            f"---> [get_user_data] Unexpected error: {e}", exc_info=True)
        return "", "", [], "", 0


def get_melbourne_time_str():
    """Get current Melbourne time with error handling."""
    try:
        melbourne_tz = pytz.timezone('Australia/Melbourne')
        current_time = datetime.now(melbourne_tz)
        return current_time.strftime("%Y-%m-%d %I:%M %p AEST")
    except Exception as e:
        logger.error(f"Error getting Melbourne time: {e}")
        # Fallback to UTC or local time if pytz fails
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy"}

# --- ADDED: Intent Detection Function Stub --- START ---


async def detect_and_handle_action(sender_id: str, message_text: str) -> bool:
    """
    Detects the user's intent and handles specific actions like Trainerize edits.

    Returns:
        bool: True if a specific action was detected and handled (or is being handled),
              False if it's general chat.
    """
    logger.info(
        f"[detect_and_handle_action] Analyzing message from {sender_id}: '{message_text[:100]}...'")

    # 1. If awaiting program edit details, parse and execute
    if program_edit_pending.get(sender_id, False):
        try:
            # Extract details JSON
            details_prompt = prompts.PROGRAM_EDIT_DETAILS_PROMPT_TEMPLATE.format(
                user_message=message_text)
            details_json = call_gemini_with_retry(
                GEMINI_MODEL_PRO, details_prompt)
            data = json.loads(details_json)
            workout_day = data.get('workout_day')
            exercise_name = data.get('exercise_name')
            sets = data.get('sets', 3)
            reps = data.get('reps', 12)
            ig_username = ig_usernames.get(sender_id)
            # Call TrainerizeAutomation edit method
            if trainerize_instance and ig_username:
                trainerize_instance.edit_client_workout(
                    client_name=ig_username,
                    workout_name=workout_day,
                    action="edit",
                    exercise_details={
                        "exercise_name": exercise_name,
                        "sets": str(sets),
                        "reps": str(reps)
                    }
                )
                await send_instagram_reply(
                    sender_id,
                    f"Got your details! Updating {workout_day} - {exercise_name} to {sets}x{reps}. I'll let you know when it's complete."
                )
            else:
                await send_instagram_reply(
                    sender_id,
                    "Sorry, I couldn't apply that change right now. Please try again later."
                )
        except Exception as e:
            logger.error(
                f"Error handling program edit details for {sender_id}: {e}", exc_info=True)
            await send_instagram_reply(sender_id, "Oops, something went wrong parsing those details. Could you try again?")
        finally:
            # Clear pending state
            program_edit_pending.pop(sender_id, None)
        return True

    # 2. Call Gemini for Intent Detection
    intent_prompt = prompts.INTENT_DETECTION_PROMPT_TEMPLATE.format(
        user_message=message_text
    )
    logger.debug(
        f"[detect_and_handle_action] Sending intent detection prompt for {sender_id}...")
    detected_intent = call_gemini_with_retry(
        GEMINI_MODEL_PRO, intent_prompt)  # Use primary model for intent
    logger.info(
        f"[detect_and_handle_action] Detected intent for {sender_id}: '{detected_intent}'")

    # 3. Handle Specific Intents
    if detected_intent == "Program Edit Request":
        # Flag that next user message should contain edit details
        program_edit_pending[sender_id] = True
        logger.info(
            f"Intent 'Program Edit Request' detected for {sender_id}. Initiating clarification flow.")
        # Clarify details: ask workout day, exercise, and mention fallback 3x12
        client_ig_username = ig_usernames.get(sender_id, None)
        if client_ig_username:
            await send_instagram_reply(
                sender_id,
                "Sure thing! Which workout day and exercise would you like to edit? And if you don't specify sets/reps, I'll default to 3 sets of 12."
            )
        else:
            logger.warning(
                f"Cannot proceed with Program Edit Request for sender_id {sender_id}: Instagram username unknown.")
        # Indicate the action is being handled (prevents general chat response)
        return True

    elif detected_intent == "Coaching Inquiry":
        logger.info(
            f"Intent 'Coaching Inquiry' detected for {sender_id}. Handling via general chat flow for now.")
        # Let the general chat handle this for now, as per the prompt logic
        return False  # Fall through to general chat

    elif detected_intent == "Fitness/Nutrition Question":
        logger.info(
            f"Intent 'Fitness/Nutrition Question' detected for {sender_id}. Handling via general chat flow.")
        # Let the general chat handle this
        return False  # Fall through to general chat

    # Add elif blocks for other specific intents if needed (e.g., build_program)

    # --- Handle the build_program intent placeholder if kept ---
    # elif detected_intent == "build_program": # Replace "build_program" with actual intent name if different
    #     client_name = "Extracted Client Name" # Replace with actual extraction
    #     program_name = "Extracted Program Name" # Replace with actual extraction
    #     logger.info(f"Intent 'build_program' detected for {sender_id}. Client: {client_name}")
    #     # --- Placeholder for Internal API Call ---
    #     return True # Indicate action was handled

    # --- Default to General Chat ---
    else:  # Includes General Chat/Rapport Building, Disengagement, Story/Post Reply, Complaint, Uncertain, or None
        logger.info(
            f"[detect_and_handle_action] Intent '{detected_intent}' does not trigger a specific action. Proceeding to general chat for {sender_id}.")
        return False  # No specific action detected/handled, proceed to general chat

# --- ADDED: Intent Detection Function Stub --- END ---

# --- Onboarding Google Sheets Helper Function START ---


def get_checkin_data(instagram_name: str) -> Dict[str, str]:
    """
    Retrieve client data for check-in from the Coaching Onboarding Form.

    Args:
        instagram_name: Instagram username to search for

    Returns:
        Dictionary with client data fields
    """
    logger.info(f"Retrieving check-in data for: {instagram_name}")

    try:
        # This uses the same credentials and spreadsheet as the onboarding flow
        creds = google.oauth2.service_account.Credentials.from_service_account_file(
            SHEETS_CREDENTIALS_PATH, scopes=SCOPES)
        service = googleapiclient.discovery.build(
            'sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        result = sheet.values().get(
            spreadsheetId=ONBOARDING_SPREADSHEET_ID,
            range=ONBOARDING_RANGE_NAME
        ).execute()

        values = result.get('values', [])
        if not values:
            logger.error("No data found in onboarding sheet")
            return {}

        # Get the header row to understand column positions
        headers = values[0]

        # Find the column indices for each required field
        instagram_col = next(
            (i for i, h in enumerate(headers) if "Instagram" in h), None)
        first_name_col = next(
            (i for i, h in enumerate(headers) if "First name" in h), None)
        last_name_col = next(
            (i for i, h in enumerate(headers) if "Last Name" in h), None)
        gender_col = next(
            (i for i, h in enumerate(headers) if "Gender" in h), None)
        weight_col = next(
            (i for i, h in enumerate(headers) if "Weight" in h), None)
        goals_col = next((i for i, h in enumerate(headers)
                         if "Long term fitness goals" in h), None)
        diet_col = next((i for i, h in enumerate(headers)
                        if "Dietary Requirements" in h), None)
        dob_col = next((i for i, h in enumerate(headers)
                       if "Date of Birth" in h), None)
        height_col = next(
            (i for i, h in enumerate(headers) if "Height" in h), None)
        gym_col = next((i for i, h in enumerate(
            headers) if "Gym Access" in h), None)
        freq_col = next((i for i, h in enumerate(headers)
                        if "Training Frequency" in h), None)
        exercises_col = next((i for i, h in enumerate(
            headers) if "Exercises they enjoy" in h), None)
        calories_col = next((i for i, h in enumerate(
            headers) if "Daily Calories" in h), None)
        conversation_col = next((i for i, h in enumerate(
            headers) if "Total Conversation" in h), None)
        legit_col = next((i for i, h in enumerate(
            headers) if "Legit Checkin" in h), None)

        client_data = {}
        # Search for the row with the matching Instagram username
        for row in values[1:]:  # Skip header row
            if instagram_col is not None and len(row) > instagram_col:
                row_instagram = row[instagram_col].strip(
                ).lower() if row[instagram_col] else ""
                if instagram_name.lower() in row_instagram:
                    logger.info(
                        f"Found client in onboarding sheet: {row_instagram}")

                    # Extract all required fields
                    client_data = {
                        "First Name": row[first_name_col] if first_name_col is not None and len(row) > first_name_col else "",
                        "Last Name": row[last_name_col] if last_name_col is not None and len(row) > last_name_col else "",
                        "Gender": row[gender_col] if gender_col is not None and len(row) > gender_col else "",
                        "Weight": row[weight_col] if weight_col is not None and len(row) > weight_col else "",
                        "Long Term Goals": row[goals_col] if goals_col is not None and len(row) > goals_col else "",
                        "Dietary Requirements": row[diet_col] if diet_col is not None and len(row) > diet_col else "",
                        "Date of Birth": row[dob_col] if dob_col is not None and len(row) > dob_col else "",
                        "Height": row[height_col] if height_col is not None and len(row) > height_col else "",
                        "Gym Access": row[gym_col] if gym_col is not None and len(row) > gym_col else "",
                        "Training Frequency": row[freq_col] if freq_col is not None and len(row) > freq_col else "",
                        "Instagram Name": row[instagram_col] if instagram_col is not None and len(row) > instagram_col else "",
                        "Exercises Enjoyed": row[exercises_col] if exercises_col is not None and len(row) > exercises_col else "",
                        "Daily Calories": row[calories_col] if calories_col is not None and len(row) > calories_col else "",
                        "Total Conversation": row[conversation_col] if conversation_col is not None and len(row) > conversation_col else "",
                        "Legit Checkin": row[legit_col] if legit_col is not None and len(row) > legit_col else ""
                    }
                    break

        if not client_data:
            logger.warning(
                f"Client with Instagram name {instagram_name} not found in onboarding sheet")

        return client_data

    except Exception as e:
        logger.error(f"Error retrieving checkin data: {str(e)}")
        return {}


def build_member_chat_prompt(client_data: Dict[str, str], current_conversation: str, total_conversation: str = "", legit_checkin: str = "") -> str:
    """
    Build the prompt for member general chat.
    """
    try:
        # Create a summary of client data
        client_summary = "\n".join(
            [f"{key}: {value}" for key, value in client_data.items() if value])

        # Use the prompt template from prompts.py
        prompt = prompts.MEMBER_CONVERSATION_PROMPT_TEMPLATE.format(
            client_summary=client_summary,
            total_conversation=total_conversation,
            legit_checkin=legit_checkin,
            current_conversation=current_conversation
        )
        return prompt
    except Exception as e:
        logger.error(f"Error building member chat prompt: {e}", exc_info=True)
        return f"Error building member chat prompt: {e}"


def update_analytics_data(ig_username: str, user_message: str, ai_response: str):
    """Reads analytics_data.json, updates conversation history, and writes back."""
    logger.info(
        f"---> [update_analytics_data] Attempting to update history for '{ig_username}'")
    analytics_file_path = r"C:\Users\Shannon\analytics_data.json"

    try:
        # 1. Read existing data
        try:
            with open(analytics_file_path, "r") as f:
                analytics_data = json.load(f)
                logger.info(
                    f"---> [update_analytics_data] Read existing data from {analytics_file_path}")
        except FileNotFoundError:
            logger.warning(
                f"---> [update_analytics_data] {analytics_file_path} not found. Creating new structure.")
            # Create base structure if file doesn't exist
            analytics_data = {"global_metrics": {}, "conversations": {}}
        except json.JSONDecodeError:
            logger.error(
                f"---> [update_analytics_data] Error decoding {analytics_file_path}. Cannot update.")
            return  # Exit if file is corrupt

        # 2. Find the user within 'conversations'
        conversations_data = analytics_data.get('conversations', {})
        if not isinstance(conversations_data, dict):
            logger.error(
                "---> [update_analytics_data] 'conversations' key is not a dictionary. Resetting.")
            conversations_data = {}
            analytics_data['conversations'] = conversations_data

        target_user_id = None
        target_user_data = None
        search_ig_username_lower = ig_username.strip().lower()

        for user_id, user_data in conversations_data.items():
            if isinstance(user_data, dict):
                metrics_data = user_data.get("metrics", {})
                if isinstance(metrics_data, dict):
                    json_ig_username = metrics_data.get("ig_username", None)
                    if isinstance(json_ig_username, str) and json_ig_username.strip().lower() == search_ig_username_lower:
                        target_user_id = user_id
                        target_user_data = user_data  # We need the whole user_data to modify
                        logger.info(
                            f"---> [update_analytics_data] Found user '{ig_username}' with ID '{target_user_id}'")
                        break

        # 3. Update conversation history (if user found)
        if target_user_id and target_user_data:
            # Ensure 'metrics' and 'conversation_history' structure exists
            if "metrics" not in target_user_data or not isinstance(target_user_data["metrics"], dict):
                target_user_data["metrics"] = {}
                logger.warning(
                    f"---> [update_analytics_data] Created missing 'metrics' dict for user {target_user_id}")
            metrics_dict = target_user_data["metrics"]
            # Save IG username in metrics for lookup
            metrics_dict["ig_username"] = ig_username
            if "conversation_history" not in metrics_dict or not isinstance(metrics_dict["conversation_history"], list):
                metrics_dict["conversation_history"] = []
                logger.warning(
                    f"---> [update_analytics_data] Created missing 'conversation_history' list for user {target_user_id}")

            history_list = metrics_dict["conversation_history"]

            # Get current timestamp in ISO format (UTC)
            current_timestamp_iso = datetime.now(timezone.utc).isoformat()

            # Append user message
            if user_message:
                history_list.append({
                    "timestamp": current_timestamp_iso,
                    "type": "user",
                    "text": user_message
                })
                logger.info(
                    "---> [update_analytics_data] Appended user message to history.")

            # Set first_message_timestamp if not set
            metrics = target_user_data["metrics"]
            if not metrics.get("first_message_timestamp"):
                metrics["first_message_timestamp"] = current_timestamp_iso
                logger.info(
                    "---> [update_analytics_data] Set first_message_timestamp to current time.")

            # Append AI response
            if ai_response:
                history_list.append({
                    "timestamp": current_timestamp_iso,  # Use same timestamp for related pair
                    "type": "ai",
                    "text": ai_response
                })
                logger.info(
                    "---> [update_analytics_data] Appended AI response to history.")

            # Always update last_message_timestamp to current time
            metrics["last_message_timestamp"] = current_timestamp_iso
            logger.info(
                "---> [update_analytics_data] Updated last_message_timestamp to current time.")

            # Update the data in the main structure
            conversations_data[target_user_id] = target_user_data

        else:
            logger.warning(
                f"---> [update_analytics_data] User '{ig_username}' not found in {analytics_file_path}. Cannot update history.")
            # Optionally, you could create a new user entry here if desired
            return  # Exit if user not found and not creating new entries

        # 4. Write the entire updated structure back to the file
        try:
            with open(analytics_file_path, "w") as f:
                # Use indent for readability
                json.dump(analytics_data, f, indent=2)
                logger.info(
                    f"---> [update_analytics_data] Successfully wrote updated data to {analytics_file_path}")
        except IOError as e:
            logger.error(
                f"---> [update_analytics_data] Error writing to {analytics_file_path}: {e}")

    except Exception as e:
        logger.error(
            f"---> [update_analytics_data] Unexpected error during update: {e}", exc_info=True)


# --- Helper Function for Media Analysis --- START ---
def transcribe_audio_with_google(audio_bytes: bytes) -> Optional[str]:
    """
    Transcribe audio using Google Cloud Speech-to-Text with FFmpeg conversion
    """
    if not AUDIO_PROCESSING_AVAILABLE:
        logger.warning(
            "Audio processing is not available - cannot transcribe audio")
        return "Audio message received (transcription not available)"

    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_mp4, \
                tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:

            # Write the MP4 data to temp file
            temp_mp4.write(audio_bytes)
            temp_mp4.flush()

            # Convert audio to WAV format using ffmpeg
            ffmpeg_cmd = [
                FFMPEG_PATH,
                "-i", temp_mp4.name,
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                temp_wav.name
            ]

            try:
                result = subprocess.run(
                    ffmpeg_cmd, check=True, capture_output=True, text=True)
                logger.info(f"FFmpeg conversion successful: {result.stdout}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg conversion failed: {e.stderr}")
                return None

            # Initialize Speech client
            client = speech_v1.SpeechClient()

            # Read the WAV audio file
            with open(temp_wav.name, "rb") as audio_file:
                content = audio_file.read()

            audio = speech_v1.RecognitionAudio(content=content)
            config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-AU",
                enable_automatic_punctuation=True,
                model="phone_call",
                use_enhanced=True,
                audio_channel_count=1,
                enable_word_confidence=True,
                speech_contexts=[{
                    "phrases": [
                        "hey", "hello", "morning", "afternoon", "evening",
                        "training", "workout", "exercise", "gym", "fitness", "program"
                    ],
                    "boost": 20.0
                }]
            )

            response = client.recognize(config=config, audio=audio)

            if response.results:
                transcription = response.results[0].alternatives[0].transcript
                logger.info(f"Successfully transcribed audio: {transcription}")
                return transcription
            else:
                logger.warning("No transcription results received")
                return None

    except Exception as e:
        logger.error(f"Error in audio transcription: {e}", exc_info=True)
        return None
    finally:
        try:
            os.unlink(temp_mp4.name)
            os.unlink(temp_wav.name)
        except Exception as cleanup_e:
            logger.warning(f"Error cleaning up temp files: {cleanup_e}")


def analyze_media_url(media_url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Downloads and processes media content, prioritizing video analysis for video files.
    """
    if not media_url:
        return None, None

    try:
        response = requests.get(media_url, stream=True, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        media_bytes = response.content
        logger.info(
            f"Successfully downloaded media data ({len(media_bytes)} bytes) of type {content_type}.")

        media_type = None
        prompt_text = None
        transcription = None

        # --- Image Handling ---
        if content_type.startswith('image/'):
            media_type = 'image'
            prompt_text = "Describe this image briefly, focusing on the main subject and action."
            if PIL_AVAILABLE:
                try:
                    img = Image.open(io.BytesIO(media_bytes))
                    img.verify()
                    logger.info("PIL verification successful for image.")
                except Exception as pil_e:
                    logger.error(
                        f"PIL verification failed for image data: {pil_e}", exc_info=True)
                    return None, None

        # --- Video Handling ---
        elif content_type == 'video/mp4':
            media_type = 'video'
            logger.info("Processing as video content")
            # Attempt to transcribe audio regardless of size
            try:
                transcription = transcribe_audio_with_google(media_bytes)
                if transcription:
                    logger.info(
                        f"Successfully transcribed audio from video: {transcription}")
                else:
                    logger.info("Could not transcribe audio from video.")
            except Exception as audio_e:
                logger.error(
                    f"Error during audio transcription attempt for video: {audio_e}", exc_info=True)

            # Prepare prompt for Gemini video analysis
            prompt_text = """This is a video clip. Please:
            1. Describe the main visual elements and actions.
            2. Note any text or captions visible.
            3. If audio is present, briefly describe its nature (e.g., speech, music, background noise)."""

        # --- Audio Handling ---
        elif content_type.startswith('audio/'):
            media_type = 'audio'
            logger.info("Processing as audio content")
            # Try Google Speech-to-Text first
            transcription = transcribe_audio_with_google(media_bytes)
            if transcription:
                # Return only transcription for pure audio
                return 'audio', transcription
            else:
                # Fall back to Gemini if transcription fails
                logger.warning(
                    "Speech-to-Text failed for audio, falling back to Gemini audio analysis...")
                prompt_text = "This is an audio file. Please describe any indicators of audio content you can detect."

        else:
            logger.warning(f"Unrecognized content type: {content_type}")
            return None, None

        # --- Gemini Analysis (for image, video, or failed audio transcription) ---
        if not prompt_text:
            logger.error(
                f"No prompt text generated for media type {media_type}. This shouldn't happen.")
            return media_type, "Error: Could not generate analysis prompt."

        media_part = {
            "mime_type": content_type,
            "data": media_bytes
        }

        # Combine prompt and media for Gemini
        gemini_contents = [
            {
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": media_part}
                ]
            }
        ]

        # Call Gemini with retry logic
        gemini_description = None
        try:
            # Try main model first
            model = genai.GenerativeModel(GEMINI_MODEL_PRO)
            response = model.generate_content(contents=gemini_contents)
            gemini_description = response.text.strip()
            logger.info(f"Successfully processed {media_type} with main model")
        except Exception as e:
            logger.warning(
                f"Main model failed for {media_type}: {e}. Trying flash model...")
            try:
                # Try flash model
                model = genai.GenerativeModel(GEMINI_MODEL_FLASH)
                simple_prompt = f"Briefly describe this {media_type} content."
                # Update prompt
                gemini_contents[0]['parts'][0]['text'] = simple_prompt
                response = model.generate_content(contents=gemini_contents)
                gemini_description = response.text.strip()
                logger.info(
                    f"Successfully processed {media_type} with flash model")
            except Exception as e2:
                logger.error(
                    f"All models failed to process {media_type}: {e2}")
                gemini_description = "Analysis failed."

        # --- Combine results for Video ---
        if media_type == 'video':
            final_result = f"Video Content: {gemini_description if gemini_description else 'Visual analysis failed.'}"
            if transcription:
                final_result += f" (Audio transcription: {transcription})"
            return media_type, final_result

        # --- Return results for Image or failed Audio ---
        else:
            return media_type, gemini_description

    except requests.exceptions.RequestException as req_e:
        logger.error(
            f"Failed to download media from {media_url[:100]}: {req_e}", exc_info=True)
        return None, None
    except Exception as e:
        logger.error(
            f"Unexpected error during media analysis: {e}", exc_info=True)
        return None, None

# --- Helper Function to Process Conversation for Media --- START ---


def process_conversation_for_media(conversation_text: str) -> str:
    """
    Detects media URLs in conversation text, analyzes them, and replaces URLs with descriptions.
    """
    if not conversation_text:
        return ""

    url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"
    processed_text = conversation_text
    urls_found = list(re.finditer(url_pattern, conversation_text))

    if not urls_found:
        logger.info("No media URLs found in conversation text.")
        return conversation_text

    logger.info(
        f"Found {len(urls_found)} potential media URLs in conversation.")
    for match in urls_found:
        url = match.group(1)
        logger.info(f"Processing URL found: {url[:100]}...")
        media_type, result_text = analyze_media_url(url)

        if media_type and result_text:
            if media_type == 'image':
                replacement_text = f"(Sent a photo: {result_text})"
            elif media_type == 'audio':
                # This case should now only happen for pure audio files where transcription succeeded
                replacement_text = f"(Voice message: {result_text})"
            elif media_type == 'video':
                # Result_text for video now includes both visual description and transcription if available
                replacement_text = f"(Sent a video: {result_text})"
            else:
                # Fallback for unexpected types or Gemini audio description
                replacement_text = f"({media_type}: {result_text})"

            logger.info(
                f"Replacing URL with {media_type} description: {replacement_text[:100]}...")
        else:
            replacement_text = f"(Sent {media_type if media_type else 'media'}, but analysis failed)"
            logger.warning(f"Using generic placeholder for {url[:100]}")

        processed_text = processed_text.replace(url, replacement_text, 1)

    logger.info("Finished processing conversation text for media.")
    return processed_text
# --- Helper Function to Process Conversation for Media --- END ---

# --- Instagram Webhook Verification --- START ---


@app.get("/webhook/instagram")
async def verify_instagram_webhook(request: Request):
    # Get query parameters from the request
    params = dict(request.query_params)

    # Facebook sends these parameters for verification
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Log everything for debugging
    logger.info(
        f"Instagram webhook verification requested. Mode: {mode}, Token: {token}, Challenge: {challenge}")

    # Verify token set in Facebook Developer Dashboard
    # This should match what you entered in Facebook
    verify_token = "Shanbotcyywp7nyk"

    # Verification logic
    if mode == "subscribe" and token == verify_token:
        logger.info("Instagram webhook verified successfully")
        # Return challenge directly as string (Facebook expects it as-is)
        return PlainTextResponse(content=challenge)
    else:
        logger.error(
            f"Failed webhook verification. Mode: {mode}, Token: {token}")
        raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook/instagram")
async def process_instagram_webhook(request: Request):
    """
    Process incoming webhook events from Instagram
    """
    # Get the raw request body
    body_raw = await request.body()

    # Log the raw data for debugging
    logger.info(f"INSTAGRAM WEBHOOK RAW DATA: {body_raw.decode()}")

    try:
        # Parse the JSON body
        body = await request.json()
        logger.info(f"Received Instagram webhook: {body}")

        # Extract the Instagram data
        if body.get('object') == 'instagram' and 'entry' in body:
            for entry in body['entry']:
                # Handle direct messages
                if 'messaging' in entry:
                    for messaging in entry['messaging']:
                        sender_id = messaging.get('sender', {}).get('id')
                        # Fetch and cache IG username if not cached
                        sender_username = ig_usernames.get(sender_id)
                        if not sender_username:
                            try:
                                resp = requests.get(
                                    f"https://graph.facebook.com/v18.0/{sender_id}?fields=username&access_token={IG_GRAPH_ACCESS_TOKEN}",
                                    timeout=5
                                )
                                data = resp.json()
                                uname = data.get("username")
                                if uname:
                                    ig_usernames[sender_id] = uname
                                    sender_username = uname
                                    logger.info(
                                        f"Fetched IG username for {sender_id}: {sender_username}")
                            except Exception as e:
                                logger.error(
                                    f"Error fetching IG username for {sender_id}: {e}")
                        recipient_id = messaging.get('recipient', {}).get('id')
                        timestamp = messaging.get('timestamp')

                        # Process message
                        if 'message' in messaging:
                            message = messaging['message']
                            message_id = message.get('mid')
                            message_text = message.get('text', '')

                            # ---> ADDED: Check if it's a reply to a story < ---
                            story_reply_info = message.get(
                                'reply_to', {}).get('story')
                            if story_reply_info:
                                story_id = story_reply_info.get('id')
                                # Use the message text as the comment text
                                comment_text = message_text
                                logger.info(
                                    f"Detected reply to story (ID: {story_id}): '{comment_text}'")
                                if story_id and comment_text:
                                    # Use the existing story comment handler, passing None for comment_id as it's not available here
                                    try:
                                        # Pass sender_id so the reply can be sent via DM
                                        asyncio.create_task(handle_story_reply_dm(
                                            sender_id, story_id, comment_text))
                                        logger.info(
                                            f"Scheduled handle_story_reply_dm task for story {story_id}")
                                    except Exception as task_e:
                                        logger.error(
                                            f"Error scheduling handle_story_reply_dm for story {story_id}: {task_e}", exc_info=True)
                                else:
                                    logger.warning(
                                        "Missing story_id or comment_text for story reply.")
                                continue  # Skip normal DM processing for story replies
                            # ---> END ADDED CHECK <---

                            # ---> Standard DM Processing (if not a story reply) <---
                            # Check for echo messages
                            if message.get('is_echo'):
                                logger.info(
                                    f"Ignoring echo message from {sender_id}")
                                continue  # Skip processing echo messages

                            # Log incoming DM with username if available
                            display = f"{sender_id} ({sender_username})" if sender_username else sender_id
                            logger.info(
                                f"Instagram DM from {display}: {message_text}")

                            # Check if a task already exists for this sender and cancel it FIRST
                            if sender_id in response_tasks:
                                old_task = response_tasks[sender_id]
                                if not old_task.done():  # Check if it's not already finished/cancelled
                                    logger.info(
                                        f"Cancelling previous response task for {sender_id}: {old_task}")
                                    old_task.cancel()
                                else:
                                    logger.info(
                                        f"Previous task for {sender_id} already done, no need to cancel.")
                                # Remove reference to old task immediately after cancelling attempt
                                del response_tasks[sender_id]

                            # Record arrival time for engagement delay
                            last_message_timestamps[sender_id] = time.time()

                            # Buffer the NEW incoming message
                            message_buffer[sender_id].append(message_text)
                            logger.info(
                                f"Appended message to buffer for {sender_id}. Buffer size: {len(message_buffer[sender_id])}")

                            # --- Combine buffered messages for intent detection ---
                            combined_message_for_intent = ' '.join(
                                message_buffer[sender_id])
                            logger.info(
                                f"Combined message for intent check: '{combined_message_for_intent[:100]}...'")

                            # --- Call Intent Detection ---
                            action_handled = await detect_and_handle_action(sender_id, combined_message_for_intent)

                            if action_handled:
                                logger.info(
                                    f"Action handled for {sender_id} by detect_and_handle_action. Clearing buffer and skipping general response.")
                                # Clear buffer as the action was handled based on this message sequence
                                if sender_id in message_buffer:
                                    del message_buffer[sender_id]
                                # Remove the scheduled task if one was accidentally created (shouldn't happen with this logic flow, but good practice)
                                if sender_id in response_tasks:
                                    task_to_cancel = response_tasks.pop(
                                        sender_id)
                                    if not task_to_cancel.done():
                                        task_to_cancel.cancel()
                                    logger.info(
                                        f"Cancelled potentially redundant task for {sender_id} after action handled.")
                            else:
                                # --- No action detected, proceed with scheduling general response ---
                                logger.info(
                                    f"No action detected for {sender_id}, proceeding to schedule general chat response.")
                                # --- (Existing logic for calculating delay and scheduling response follows) ---
                                # ---> ADDED: Pre-calculate initial delay based on file history < ---
                                calculated_initial_delay = FIRST_MESSAGE_DELAY  # Default to long delay
                                log_reason = "Default (Long - Initial)"
                                analytics_file_path = r"C:\Users\Shannon\analytics_data.json"
                                # Use the username fetched earlier in this webhook function
                                ig_username_for_check = ig_usernames.get(
                                    sender_id)

                                if ig_username_for_check:
                                    normalized_ig_username = ig_username_for_check.strip().lower()
                                    logger.info(
                                        f"[process_instagram_webhook] Pre-checking file history for {normalized_ig_username}")
                                    try:
                                        with open(analytics_file_path, "r") as f:
                                            analytics = json.load(f)
                                        convs = analytics.get(
                                            "conversations", {})

                                        target_user_metrics = None
                                        for user_key, user_data in convs.items():
                                            metrics = user_data.get(
                                                "metrics", {})
                                            json_username = metrics.get(
                                                "ig_username")
                                            normalized_json_username = ""
                                            if json_username:
                                                normalized_json_username = json_username.strip().lower()

                                            if normalized_json_username == normalized_ig_username:
                                                target_user_metrics = metrics
                                                break  # Found the user

                                        if target_user_metrics:
                                            last_ts_str = target_user_metrics.get(
                                                "last_message_timestamp")
                                            if last_ts_str:
                                                try:
                                                    last_dt = parser.isoparse(
                                                        last_ts_str)
                                                    last_dt_utc = last_dt.astimezone(
                                                        pytz.UTC)
                                                    last_date = last_dt_utc.date()
                                                    today_utc = datetime.now(
                                                        pytz.UTC).date()

                                                    if last_date == today_utc:
                                                        calculated_initial_delay = BATCH_DELAY
                                                        log_reason = f"Metrics timestamp is today ({last_date})"
                                                    else:
                                                        # Keep FIRST_MESSAGE_DELAY (default)
                                                        log_reason = f"Metrics timestamp on {last_date}"
                                                except Exception as date_e:
                                                    log_reason = f"Error parsing metrics date: {type(date_e).__name__}"
                                                    # Keep FIRST_MESSAGE_DELAY (default)
                                            else:
                                                log_reason = "User found, but no last_message_timestamp field"
                                                # Keep FIRST_MESSAGE_DELAY (default)
                                        else:
                                            log_reason = "User not found in analytics file"
                                            # Keep FIRST_MESSAGE_DELAY (default)

                                    except FileNotFoundError:
                                        log_reason = "Analytics file not found"
                                        # Keep FIRST_MESSAGE_DELAY (default)
                                    except Exception as e:
                                        log_reason = f"Error loading analytics: {type(e).__name__}"
                                        # Keep FIRST_MESSAGE_DELAY (default)
                                else:
                                    log_reason = "Username lookup failed earlier in webhook"
                                    # Keep FIRST_MESSAGE_DELAY (default)

                                logger.info(
                                    f"[process_instagram_webhook] Calculated initial delay: {calculated_initial_delay}s. Reason: {log_reason}")
                                # ---> END ADDED SECTION < ---

                                # Now, create the NEW task and store it
                                logger.info(
                                    f"Creating NEW response task for {sender_id} with delay {calculated_initial_delay}s")
                                new_task = asyncio.create_task(
                                    schedule_response(sender_id, calculated_initial_delay))
                                response_tasks[sender_id] = new_task
                                logger.info(
                                    f"Scheduled NEW response task for {sender_id}: {new_task}")

                # Handle story comments, mentions, and other webhook events
                elif 'changes' in entry:
                    for change in entry['changes']:
                        field = change.get('field')
                        value = change.get('value', {})

                        # Log all fields for debugging
                        logger.info(f"Processing change with field: {field}")
                        logger.info(f"Change value: {value}")

                        # Handle comments on posts or stories
                        if field == 'comments':
                            if 'media' in value and 'comments' in value:
                                media_id = value.get('media', {}).get('id')
                                media_type = value.get('media', {}).get(
                                    'media_type', 'Unknown')
                                for comment in value.get('comments', []):
                                    comment_id = comment.get('id')
                                    comment_text = comment.get('text', '')
                                    username = value.get(
                                        'from', {}).get('username')
                                    user_id = value.get('from', {}).get('id')

                                    logger.info(
                                        f"Received a {media_type} comment from {username} (ID: {user_id}): {comment_text}")
                                    logger.info(
                                        f"Comment ID: {comment_id}, Media ID: {media_id}")

                                    logger.info(
                                        f"Received STORY comment (ID: {comment_id}) on media (ID: {media_id}). Comment text: {comment_text}")

                                    # --- Call new handler function ---
                                    try:
                                        # Schedule the handling as a background task so webhook returns quickly
                                        # Make sure handle_story_comment is defined elsewhere!
                                        asyncio.create_task(handle_story_comment(
                                            media_id, comment_id, comment_text))
                                        logger.info(
                                            f"Scheduled handle_story_comment task for comment {comment_id}")
                                    except Exception as task_e:
                                        logger.error(
                                            f"Error scheduling handle_story_comment for comment {comment_id}: {task_e}", exc_info=True)
                                    # --- End Story Comment Handling ---

                                    # You could add handling for non-story comments (e.g., posts, reels) here if needed

                        # Handle mentions in stories or posts
                        elif field == 'mentions':
                            mention_id = value.get('id')
                            mention_media_id = value.get('media_id')
                            mentioned_by = value.get(
                                'from', {}).get('username')
                            mentioned_by_id = value.get('from', {}).get('id')

                            logger.info(
                                f"Received mention from {mentioned_by} (ID: {mentioned_by_id})")
                            logger.info(
                                f"Mention ID: {mention_id}, Media ID: {mention_media_id}")

                            # Add AI response to mention logic here if needed

        # Always acknowledge receipt
        return PlainTextResponse(content="EVENT_RECEIVED")
    except Exception as e:
        logger.error(
            f"Error processing Instagram webhook: {str(e)}", exc_info=True)
        # Still return 200 to acknowledge receipt and prevent retries
        return PlainTextResponse(content="ERROR_PROCESSED")


# Function to send Instagram replies
async def send_instagram_reply(recipient_id: str, message_text: str):
    """
    Send a reply message using the Instagram Graph API
    """
    try:
        # Your page/app access token from Facebook Developer Portal
        access_token = "EAAJaUdyYIDgBO2TVUXn3nZChZBUEyJlkUi5oZCbVKm5TOMZA3l33bQaMZCRkiLNsZACYnxg8B1LarhVHeb0HmPQoAZBSEHfAw3B0ZAPHp1jx5Etp7TmarfSlfb5QJmMZCfIY7lDmRaqzhxtgxxGlniEukynpJoQHBKVK6ppbkRDjGTfUzVGwNvPEajwYScllwZACYZD"  # Updated with fresh token

        # The page/app ID that is sending the message
        instagram_account_id = "17841415641641750"  # Your Instagram business account ID

        # API URL for sending messages using Graph API
        url = f"https://graph.facebook.com/v18.0/me/messages"

        # Payload for the message
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }

        # Add headers with the access token
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        # Log what we're about to send
        logger.info(f"Sending reply to {recipient_id}: {message_text[:50]}...")
        logger.info(f"Using URL: {url}")

        # Send the message
        response = requests.post(url, json=payload, headers=headers)

        # Log the result
        try:
            response_json = response.json()
            logger.info(f"Instagram API response: {response_json}")
        except:
            logger.info(
                f"Instagram API response status: {response.status_code}, text: {response.text}")

        if response.status_code != 200:
            logger.error(
                f"Failed to send message. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")

            # Try alternative endpoint if first method fails
            alt_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/messages"
            alt_payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": message_text},
                "access_token": access_token
            }

            logger.info(f"Trying alternative endpoint: {alt_url}")
            alt_response = requests.post(alt_url, json=alt_payload)

            try:
                alt_response_json = alt_response.json()
                logger.info(f"Alternative API response: {alt_response_json}")
                return alt_response_json
            except:
                logger.error(
                    f"Alternative endpoint also failed: {alt_response.status_code}, {alt_response.text}")

        return response.json() if response.status_code == 200 else {"error": "Failed to send message"}
    except Exception as e:
        logger.error(
            f"Exception when sending Instagram reply: {str(e)}", exc_info=True)
        return {"error": str(e)}


@app.get("/debug")
async def debug_endpoint(request: Request):
    """Simple debug endpoint that returns all query parameters and headers"""
    query_params = dict(request.query_params)
    headers = dict(request.headers)

    # Log everything for debugging
    logger.info(f"DEBUG ENDPOINT ACCESSED - Query params: {query_params}")

    # If this is a Facebook verification attempt, handle it specially
    if "hub.mode" in query_params and "hub.verify_token" in query_params and "hub.challenge" in query_params:
        mode = query_params.get("hub.mode")
        token = query_params.get("hub.verify_token")
        challenge = query_params.get("hub.challenge")

        logger.info(
            f"DEBUG: Facebook verification detected! Mode: {mode}, Token: {token}, Challenge: {challenge}")

        # Verify the token for proper logging (but always return challenge in debug mode)
        verify_token = "Shanbotcyywp7nyk"
        if mode == "subscribe" and token == verify_token:
            logger.info("DEBUG: Token verification successful")
        else:
            logger.warning(
                f"DEBUG: Token verification failed. Expected: {verify_token}, Got: {token}")

        # Always return the challenge as plain text without verification for debugging
        return PlainTextResponse(content=challenge)

    return {
        "status": "debug",
        "query_params": query_params,
        "headers": {k: v for k, v in headers.items()},
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint that redirects to health check"""
    logger.info("Root endpoint accessed")
    return {"status": "Shanbot API running", "message": "Use /webhook endpoints for functionality"}


@app.get("/facebook-webhook")
async def facebook_webhook(request: Request):
    """
    Ultra simple Facebook webhook verification endpoint
    """
    # Get query parameters
    params = dict(request.query_params)

    # Log all parameters
    logger.info(f"FACEBOOK SIMPLE WEBHOOK: Params = {params}")

    # Check if this is a verification request
    if "hub.mode" in params and params["hub.mode"] == "subscribe":
        if "hub.verify_token" in params and params["hub.verify_token"] == "Shanbotcyywp7nyk":
            challenge = params.get("hub.challenge", "")
            logger.info(
                f"FACEBOOK SIMPLE WEBHOOK: Verification successful. Returning challenge: {challenge}")
            return PlainTextResponse(content=challenge)
        else:
            logger.warning(
                "FACEBOOK SIMPLE WEBHOOK: Token verification failed")

    # Default response
    return PlainTextResponse(content="Hello Facebook")


@app.post("/facebook-webhook")
async def process_facebook_webhook(request: Request):
    """
    Process incoming webhook events from Facebook/Instagram
    """
    # Get the raw request body
    body_raw = await request.body()

    # Log the raw data
    logger.info(f"WEBHOOK RAW DATA: {body_raw.decode()}")

    try:
        # Parse the JSON body
        body = await request.json()
        logger.info(
            f"FACEBOOK WEBHOOK POST: Received data: {json.dumps(body, indent=2)}")

        # Extract the event type - entries[0].changes[0].field should be 'messages'
        if 'entry' in body and len(body['entry']) > 0:
            for entry in body['entry']:
                # Log the entry for debugging
                logger.info(f"Processing entry: {json.dumps(entry, indent=2)}")

                # Handle Instagram messages specifically
                if 'messaging' in entry:
                    for messaging_event in entry['messaging']:
                        sender_id = messaging_event.get('sender', {}).get('id')
                        recipient_id = messaging_event.get(
                            'recipient', {}).get('id')

                        # Check if this contains a message
                        if 'message' in messaging_event:
                            message_text = messaging_event['message'].get(
                                'text', '')
                            logger.info(
                                f"Received message from {sender_id} to {recipient_id}: {message_text}")

                            # Here you would process the message and generate a response
                            # For now, just log it

                elif 'changes' in entry:
                    for change in entry['changes']:
                        field = change.get('field')
                        if field == 'messages':
                            value = change.get('value', {})
                            if 'messages' in value:
                                for message in value['messages']:
                                    message_id = message.get('id')
                                    message_text = message.get(
                                        'text', {}).get('body', '')
                                    from_id = value.get('from', {}).get('id')
                                    logger.info(
                                        f"Received message (ID: {message_id}) from {from_id}: {message_text}")

        # Always return a 200 OK to acknowledge receipt
        return PlainTextResponse(content="EVENT_RECEIVED")

    except json.JSONDecodeError:
        logger.error(
            "Failed to decode JSON from Facebook webhook request body")
        # Even with error, return 200 to prevent Facebook from retrying
        return PlainTextResponse(content="JSON_ERROR")
    except Exception as e:
        logger.error(
            f"Error processing Facebook webhook: {str(e)}", exc_info=True)
        # Even with error, return 200 to prevent Facebook from retrying
        return PlainTextResponse(content="ERROR")

# Buffer incoming messages per sender and schedule batched responses
message_buffer: Dict[str, List[str]] = defaultdict(list)
response_tasks: Dict[str, asyncio.Task] = {}
# Track when user sent last message
last_message_timestamps: Dict[str, float] = {}
# ---> ADDED: Track when bot last finished replying < ---
last_bot_reply_timestamps: Dict[str, float] = {}
# --- ADDED: Track users awaiting program edit details ---
program_edit_pending: Dict[str, bool] = {}
# seconds to wait to batch rapid messages (allow multiple user messages to accumulate)
BATCH_DELAY = 20
# seconds to wait before responding to first message of the day
FIRST_MESSAGE_DELAY = 600

# Scheduled batch response handler


async def schedule_response(sender_id: str, initial_delay_to_use: int):
    try:
        # --- NEW DELAY LOGIC --- START ---
        # Start with the base delay (20s or 600s)
        target_total_wait = initial_delay_to_use
        user_response_time_seconds = 0  # Default

        # Get user message arrival time and bot last reply time
        user_message_arrival_ts = last_message_timestamps.get(sender_id)
        last_bot_reply_ts = last_bot_reply_timestamps.get(sender_id)

        if user_message_arrival_ts and last_bot_reply_ts:
            user_response_time_seconds = user_message_arrival_ts - last_bot_reply_ts
            # Ensure response time isn't negative (e.g., clock sync issues)
            user_response_time_seconds = max(0, user_response_time_seconds)
            target_total_wait = max(
                initial_delay_to_use, user_response_time_seconds)
            logger.info(
                f"[schedule_response] User response time: {user_response_time_seconds:.1f}s.")
        elif user_message_arrival_ts:
            logger.info(
                f"[schedule_response] User message timestamp found, but no previous bot reply timestamp. Using initial delay.")
        else:
            logger.info(
                f"[schedule_response] No user message arrival timestamp found. Using initial delay.")

        logger.info(
            f"[schedule_response] Base Delay: {initial_delay_to_use}s, User Response Time: {user_response_time_seconds:.1f}s. Target Total Wait: {target_total_wait:.1f}s")

        # Perform the calculated total wait
        await asyncio.sleep(target_total_wait)
        logger.info(
            f"[schedule_response] Woke up after {target_total_wait:.1f}s total wait for {sender_id}.")
        # --- NEW DELAY LOGIC --- END ---

        # --- Rest of the message processing ---
        messages = message_buffer.pop(sender_id, [])
        if not messages:
            logger.info(
                f"No messages left in buffer for {sender_id} after delay.")
            return  # Exit if buffer was cleared by another message

        full_message = ' '.join(messages)
        logger.info(
            f"Processing combined message for {sender_id}: '{full_message}'")

        # Get user data for prompt context (using the already looked-up username if available)
        prev_conv, bio, conversation_topics, interests = "", "N/A", [], "N/A"  # Defaults
        if ig_usernames.get(sender_id):
            try:
                # Re-use get_user_data which handles file reading and parsing
                prev_conv, bio, conversation_topics, interests = get_user_data(
                    ig_usernames.get(sender_id))
                logger.info(
                    f"Retrieved context for {ig_usernames.get(sender_id)} for prompt generation.")
            except Exception as gud_e:
                logger.error(
                    f"Error retrieving context via get_user_data for {ig_usernames.get(sender_id)}: {gud_e}")
        else:
            logger.warning(
                f"Cannot retrieve context for prompt generation, username unknown for {sender_id}.")

        # Build AI prompt
        topics_str = "\\n- " + \
            "\\n- ".join(conversation_topics) if conversation_topics else "N/A"
        current_time = get_melbourne_time_str()
        combined_history_for_prompt = (prev_conv + "\\n") if prev_conv else ""
        # Add the latest message(s)
        combined_history_for_prompt += f"Lead: {full_message}"

        prompt = prompts.GENERAL_CHAT_PROMPT_TEMPLATE.format(
            current_melbourne_time_str=current_time,
            bio=bio if bio else "N/A",
            topics_str=topics_str,
            interests=interests if interests else "N/A",
            full_conversation=combined_history_for_prompt
        )
        logger.info(
            f"Generated prompt for {sender_id} (length: {len(prompt)})")

        # Call Gemini
        response_text = call_gemini_with_retry(
            # Provide a fallback
            GEMINI_MODEL_PRO, prompt) or "Sorry, I couldn't generate a response right now."
        logger.info(
            f"Generated Gemini response for {sender_id}: '{response_text[:100]}...'")

        # Update analytics_data.json (using the already looked-up username)
        if ig_usernames.get(sender_id):
            try:
                update_analytics_data(ig_usernames.get(
                    sender_id), full_message, response_text)
                logger.info(
                    f"Updated analytics data for {ig_usernames.get(sender_id)}")
            except Exception as e:
                logger.error(
                    f"Error updating analytics for {ig_usernames.get(sender_id)} ({sender_id}): {e}")
        else:
            logger.warning(
                f"No IG username for {sender_id}, skipping analytics update.")

        # Split and send messages
        response_messages = split_response_into_messages(response_text)
        logger.info(
            f"Split response into {len(response_messages)} message chunks for {sender_id}")
        messages_sent_successfully = 0
        for idx, msg in enumerate(response_messages, 1):
            logger.info(
                f"Sending message {idx}/{len(response_messages)} to {sender_id}: '{msg[:50]}...'")
            # --- MODIFIED: Track success of send_instagram_reply --- START ---
            send_success = await send_instagram_reply(sender_id, msg)
            if send_success:
                messages_sent_successfully += 1
                logger.info(
                    f"Sent message {idx}/{len(response_messages)} to {sender_id}")
                # Dynamic delay based on message length
                await asyncio.sleep(max(len(msg)/10, 2))
            else:
                logger.error(
                    f"Failed to send message {idx}/{len(response_messages)} to {sender_id}. Stopping send sequence.")
                break  # Stop trying to send further chunks if one fails
            # --- MODIFIED: Track success of send_instagram_reply --- END ---

        # --- ADDED: Update last_bot_reply_timestamp --- START ---
        if messages_sent_successfully > 0:
            # Only update if at least one message chunk was sent
            current_time_float = time.time()
            last_bot_reply_timestamps[sender_id] = current_time_float
            logger.info(
                f"Updated last_bot_reply_timestamp for {sender_id} to {current_time_float}")
        else:
            logger.warning(
                f"No messages were sent successfully to {sender_id}, not updating last_bot_reply_timestamp.")
        # --- ADDED: Update last_bot_reply_timestamp --- END ---

    except asyncio.CancelledError:
        logger.info(f"Response task for {sender_id} was cancelled.")
    except Exception as e:
        logger.error(
            f"Error in scheduled response task for {sender_id}: {e}", exc_info=True)
        # Optionally try to send an error message to the user
        try:
            await send_instagram_reply(sender_id, "Sorry, something went wrong on my end. Please try again later.")
        except Exception as send_err:
            logger.error(
                f"Failed to send error message to {sender_id}: {send_err}")

# --- Story Comment Handling Functions --- START ---


def get_story_media_info(media_id: str) -> Optional[str]:
    """Fetches the media_url for a given story media_id."""
    logger.info(
        f"Attempting to fetch media info for story media_id: {media_id}")
    api_url = f"https://graph.facebook.com/v18.0/{media_id}?fields=media_url,media_type&access_token={IG_GRAPH_ACCESS_TOKEN}"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        data = response.json()
        media_url = data.get('media_url')
        media_type = data.get('media_type')

        if media_url:
            logger.info(
                f"Successfully fetched media_url for {media_id} (Type: {media_type}): {media_url[:100]}...")
            return media_url
        else:
            logger.warning(
                f"media_url not found in response for media_id {media_id}. Response: {data}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error fetching media info for {media_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error in get_story_media_info for {media_id}: {e}", exc_info=True)
        return None


def reply_to_instagram_comment(comment_id: str, reply_text: str) -> bool:
    """Posts a reply to a specific Instagram comment."""
    logger.info(
        f"Attempting to reply to comment_id: {comment_id} with text: \'{reply_text[:50]}...\'")
    api_url = f"https://graph.facebook.com/v18.0/{comment_id}/replies"
    payload = {
        "message": reply_text,
        "access_token": IG_GRAPH_ACCESS_TOKEN
    }

    try:
        response = requests.post(api_url, data=payload, timeout=15)
        response.raise_for_status()

        response_data = response.json()
        logger.info(
            f"Successfully replied to comment {comment_id}. Response: {response_data}")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error replying to comment {comment_id}: {e}", exc_info=True)
        # Log response body if available
        if hasattr(e, 'response') and e.response is not None:
            logger.error(
                f"Response status: {e.response.status_code}, body: {e.response.text}")
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error in reply_to_instagram_comment for {comment_id}: {e}", exc_info=True)
        return False


async def handle_story_comment(media_id: str, comment_id: str, comment_text: str):
    """Handles fetching story context, generating, and sending a reply."""
    logger.info(
        f"--- Starting handle_story_comment for comment_id: {comment_id} ---")
    try:
        story_media_url = get_story_media_info(media_id)

        if not story_media_url:
            logger.warning(
                f"handle_story_comment: Could not get media URL for media_id {media_id}. Aborting reply.")
            return

        # Analyze the story media to get a description
        # analyze_media_url returns a tuple (media_type, result_text)
        analysis_result = analyze_media_url(story_media_url)
        story_description = None
        if analysis_result and analysis_result[1]:
            story_description = analysis_result[1]
            logger.info(
                f"handle_story_comment: Story analysis result for {media_id}: {story_description}")
        else:
            logger.warning(
                f"handle_story_comment: Could not analyze story media for URL: {story_media_url}. Using comment only.")
            # Fallback: proceed without story description, or use a default
            story_description = "the story"  # Default placeholder if analysis fails

        # Construct the prompt using the template (ensure it exists in prompts.py)
        try:
            prompt = prompts.STORY_COMMENT_REPLY_PROMPT_TEMPLATE.format(
                story_description=story_description,
                comment_text=comment_text
            )
            logger.info(
                f"handle_story_comment: Generated prompt for comment {comment_id}.")
        except AttributeError:
            logger.error(
                f"handle_story_comment: STORY_COMMENT_REPLY_PROMPT_TEMPLATE not found in prompts.py! Using basic prompt.")
            # Fallback basic prompt if template is missing
            prompt = f"Someone commented on my Instagram story (which was about: {story_description}) saying: '{comment_text}'. Generate a friendly, casual response as a fitness trainer named Shannon. Keep it brief (1-2 sentences max)."
        except Exception as prompt_e:
            logger.error(
                f"handle_story_comment: Error formatting prompt: {prompt_e}", exc_info=True)
            return  # Cannot proceed without a prompt

        # Generate the reply using Gemini
        reply_text = call_gemini_with_retry(GEMINI_MODEL_PRO, prompt)

        if not reply_text:
            logger.error(
                f"handle_story_comment: Failed to generate Gemini reply for comment {comment_id}.")
            return

        logger.info(
            f"handle_story_comment: Generated reply for comment {comment_id}: {reply_text}")

        # Send the reply
        success = reply_to_instagram_comment(comment_id, reply_text)
        if success:
            logger.info(
                f"handle_story_comment: Successfully sent reply to comment {comment_id}.")
        else:
            logger.error(
                f"handle_story_comment: Failed to send reply for comment {comment_id}.")

    except Exception as e:
        logger.error(
            f"handle_story_comment: Unexpected error processing comment {comment_id}: {e}", exc_info=True)
    finally:
        logger.info(
            f"--- Finished handle_story_comment for comment_id: {comment_id} ---")

# --- Story Comment Handling Functions --- END ---

# --- ADDED: Story Reply DM Handler --- START ---


async def handle_story_reply_dm(sender_id: str, story_id: str, comment_text: str):
    """Handles story replies received via DM, gets story context, generates reply, and sends via DM."""
    logger.info(
        f"--- Starting handle_story_reply_dm for story_id: {story_id} from sender_id: {sender_id} ---")
    try:
        story_media_url = get_story_media_info(story_id)

        if not story_media_url:
            logger.warning(
                f"handle_story_reply_dm: Could not get media URL for story_id {story_id}. Sending generic reply.")
            await send_instagram_reply(sender_id, "Thanks for replying to my story!")
            return

        # Analyze the story media to get a description
        analysis_result = analyze_media_url(story_media_url)
        story_description = "my recent story"  # Default placeholder
        if analysis_result and analysis_result[1]:
            story_description = analysis_result[1]
            logger.info(
                f"handle_story_reply_dm: Story analysis result for {story_id}: {story_description}")
        else:
            logger.warning(
                f"handle_story_reply_dm: Could not analyze story media for URL: {story_media_url}. Using default description.")

        # Construct the prompt using the template
        try:
            prompt = prompts.STORY_COMMENT_REPLY_PROMPT_TEMPLATE.format(
                story_description=story_description,
                comment_text=comment_text
            )
            logger.info(
                f"handle_story_reply_dm: Generated prompt for story reply.")
        except AttributeError:
            logger.error(
                f"handle_story_reply_dm: STORY_COMMENT_REPLY_PROMPT_TEMPLATE not found! Using basic prompt.")
            prompt = f"Someone replied to my Instagram story (which was about: {story_description}) saying: '{comment_text}'. Generate a friendly, casual response as a fitness trainer named Shannon. Keep it brief (1-2 sentences max)."
        except Exception as prompt_e:
            logger.error(
                f"handle_story_reply_dm: Error formatting prompt: {prompt_e}", exc_info=True)
            await send_instagram_reply(sender_id, "Thanks for your reply!")
            return

        # Generate the reply using Gemini
        reply_text = call_gemini_with_retry(GEMINI_MODEL_PRO, prompt)

        if not reply_text:
            logger.error(
                f"handle_story_reply_dm: Failed to generate Gemini reply for story {story_id}.")
            reply_text = "Got it, thanks!"  # Fallback reply

        logger.info(
            f"handle_story_reply_dm: Generated reply for story {story_id}: {reply_text}")

        # Send the reply via DM
        await send_instagram_reply(sender_id, reply_text)
        logger.info(
            f"handle_story_reply_dm: Successfully sent DM reply to {sender_id}.")

        # Optionally: Update analytics for story reply interaction
        # try:
        #     ig_username = ig_usernames.get(sender_id, f"user_{sender_id}") # Get username or use ID
        #     update_analytics_data(ig_username, f"[Story Reply to {story_id}]: {comment_text}", reply_text)
        # except Exception as analytics_e:
        #     logger.error(f"handle_story_reply_dm: Failed to update analytics: {analytics_e}")

    except Exception as e:
        logger.error(
            f"handle_story_reply_dm: Unexpected error processing story reply {story_id}: {e}", exc_info=True)
        # Attempt to send a generic error reply via DM
        try:
            await send_instagram_reply(sender_id, "Couldn't process that reply right now, but thanks!")
        except Exception as send_err:
            logger.error(
                f"handle_story_reply_dm: Failed to send error DM: {send_err}")
    finally:
        logger.info(
            f"--- Finished handle_story_reply_dm for story_id: {story_id} ---")
# --- ADDED: Story Reply DM Handler --- END ---

# --- Trainerize API Endpoints ---


@app.post("/trainerize/build-program")
async def build_trainerize_program(request_data: BuildProgramRequest):
    """
    API endpoint to build a full training program for a client in Trainerize.
    """
    logger.info(
        f"Received request to build program for: {request_data.client_name}")

    if not trainerize_instance:
        logger.error("TrainerizeAutomation instance is not available.")
        raise HTTPException(
            status_code=503, detail="Trainerize service unavailable.")

    try:
        # Convert Pydantic model to dictionary list for the method call
        workout_defs_dict = [wd.dict()
                             for wd in request_data.workout_definitions]

        # Call the method on the global instance
        results = trainerize_instance.build_full_program_for_client(
            client_name=request_data.client_name,
            program_name=request_data.program_name,
            workout_definitions=workout_defs_dict
        )

        # Check if the overall process encountered critical failures
        # Example: check if navigation or program creation failed
        critical_failure = any(step['step'] in ['navigate_to_client', 'navigate_to_training_program',
                               'create_program'] and not step['success'] for step in results)

        if critical_failure:
            logger.error(
                f"Critical failure during program build for {request_data.client_name}. Results: {results}")
            # Return a server error status code if critical steps failed
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Failed to build program due to critical error during automation.", "details": results}
            )
        else:
            logger.info(
                f"Successfully completed program build request for {request_data.client_name}. Results: {results}")
            return JSONResponse(
                status_code=200,
                content={"message": "Program build process initiated.",
                         "details": results}
            )

    except Exception as e:
        logger.error(
            f"Error calling build_full_program_for_client for {request_data.client_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error during program build: {str(e)}")


def update_manychat_fields(subscriber_id: str, field_updates: Dict[str, str]) -> bool:
    """Update custom fields in ManyChat for a subscriber"""
    # Filter out None and empty string values
    filtered_updates = {
        k: v for k, v in field_updates.items() if v is not None and v != ""}
    if not filtered_updates:
        logger.info("No valid field updates to send to ManyChat.")
        return True  # Nothing to update, consider it success

    # Prepare the data using field_name
    field_data = [
        {"field_name": field_name, "field_value": value}
        for field_name, value in filtered_updates.items()
    ]
    data = {
        "subscriber_id": subscriber_id,
        "fields": field_data
    }

    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_KEY}",
        "Content-Type": "application/json"
    }

    logger.info(
        f"Attempting to update ManyChat fields for subscriber {subscriber_id}: {list(filtered_updates.keys())}")
    # --- ADDED DETAILED PAYLOAD LOGGING ---
    logger.info(f"ManyChat API Request Payload: {json.dumps(data, indent=2)}")
    # --- END ADDED LOGGING ---
    try:
        response = requests.post(
            "https://api.manychat.com/fb/subscriber/setCustomFields", headers=headers, json=data, timeout=10)
        # Log beginning of response
        logger.info(
            f"ManyChat API response: {response.status_code} - {response.text[:500]}")
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        logger.info(
            f"Successfully updated ManyChat fields for subscriber {subscriber_id}.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error updating ManyChat fields for subscriber {subscriber_id}: {e}", exc_info=True)
        # Log response body if available
        if hasattr(e, 'response') and e.response is not None:
            logger.error(
                f"ManyChat Error Response Body: {e.response.text[:500]}")
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error during ManyChat field update for {subscriber_id}: {e}", exc_info=True)
        return False


# --- ADDED: Dictionary to store last sent timestamp for ManyChat users ---
manychat_last_bot_sent_timestamps: Dict[str, float] = {}
# --- END ADDED ---

# --- ADDED: Message Buffer System ---

# Global dictionaries for message buffering
manychat_message_buffer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
manychat_last_message_time: Dict[str, float] = {}
BUFFER_WINDOW = 15  # seconds to wait for grouping messages

# Task management for preventing duplicate processing
user_buffer_tasks: Dict[str, asyncio.Task] = {}
user_buffer_task_scheduled: Dict[str, bool] = defaultdict(bool)

# Cleanup tracking
last_cleanup_time = time.time()
CLEANUP_INTERVAL = 300  # 5 minutes


def cleanup_stale_buffers():
    """Clean up stale buffers and tasks to prevent memory leaks."""
    global last_cleanup_time
    current_time = time.time()

    if current_time - last_cleanup_time < CLEANUP_INTERVAL:
        return

    last_cleanup_time = current_time
    cleaned_count = 0

    # Clean up done tasks
    for subscriber_id in list(user_buffer_tasks.keys()):
        task = user_buffer_tasks[subscriber_id]
        if task.done():
            user_buffer_tasks.pop(subscriber_id, None)
            user_buffer_task_scheduled[subscriber_id] = False
            cleaned_count += 1

    # Clean up old buffers (older than 10 minutes)
    ten_minutes_ago = current_time - 600
    for subscriber_id in list(manychat_message_buffer.keys()):
        if manychat_message_buffer[subscriber_id]:
            oldest_message_time = min(
                msg.get('timestamp', 0) for msg in manychat_message_buffer[subscriber_id]
            )
            if oldest_message_time < ten_minutes_ago:
                manychat_message_buffer.pop(subscriber_id, None)
                user_buffer_task_scheduled[subscriber_id] = False
                cleaned_count += 1

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} stale buffers/tasks")


def process_buffered_messages(subscriber_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Process and combine buffered messages for a subscriber.
    Returns tuple of (combined message text, latest message data) or (None, None) if buffer is empty.
    """
    messages = manychat_message_buffer.get(subscriber_id, [])
    if not messages:
        logger.info(f"No messages in buffer for {subscriber_id}")
        return None, None

    # Sort messages by timestamp
    messages.sort(key=lambda x: x.get('timestamp', 0))

    logger.info(
        f"Processing {len(messages)} buffered messages for {subscriber_id}")

    # Store the latest message data before combining
    latest_message_data = messages[-1]['original_data'] if messages else None

    # Combine messages with proper context
    combined_parts = []
    for i, msg in enumerate(messages):
        text = msg.get('text', '')
        media_type = msg.get('media_type')
        media_desc = msg.get('media_desc')

        if media_type and media_desc:
            if media_type == 'voice':
                combined_parts.append(f"[Voice Message: {media_desc}]")
            elif media_type == 'video':
                combined_parts.append(f"[Video Message: {media_desc}]")
            elif media_type == 'image':
                combined_parts.append(f"[Image: {media_desc}]")
        elif text:
            # Add separator between messages if there are multiple
            if i > 0 and combined_parts:
                combined_parts.append(" | ")
            combined_parts.append(text)

    # Clear the buffer
    manychat_message_buffer[subscriber_id] = []

    combined_text = ' '.join(combined_parts)
    logger.info(
        f"Combined {len(messages)} messages for {subscriber_id}: {combined_text[:100]}...")

    return combined_text, latest_message_data

# Add this new function


async def delayed_message_processing(subscriber_id: str):
    """Process buffered messages after the buffer window expires"""
    try:
        # Wait for the buffer window
        await asyncio.sleep(BUFFER_WINDOW)

        logger.info(
            f"Buffer window expired for {subscriber_id}. Processing messages...")

        # Check if more messages arrived recently (within last 5 seconds)
        current_time = time.time()
        last_message_time = manychat_last_message_time.get(subscriber_id, 0)

        if current_time - last_message_time < 5:
            logger.info(
                f"More messages arrived for {subscriber_id} recently, rescheduling processing")
            # Reschedule processing
            task = asyncio.create_task(
                delayed_message_processing(subscriber_id))
            user_buffer_tasks[subscriber_id] = task
            return

        # Process buffered messages and get latest data
        combined_message, latest_data = process_buffered_messages(
            subscriber_id)
        if not combined_message or not latest_data:
            logger.warning(
                f"No messages to process for {subscriber_id} after buffer window")
            return

        # Get user context from the latest message's data first to get timestamp
        ig_username = latest_data.get("ig_username") or latest_data.get(
            "name", f"user_{subscriber_id}")
        logger.info(f"Using Instagram username: {ig_username}")

        # Skip processing if the sender is cocos_connected (Shannon's own account)
        if ig_username.lower() == "cocos_connected":
            logger.info(f"Skipping processing for cocos_connected account")
            return

        # Get user data including last bot timestamp
        prev_conv, bio, conversation_topics, interests, last_bot_timestamp = get_user_data(
            ig_username)

        logger.info("=== PHASE 1: Setting Response Time ===")
        # Calculate response time bucket using timestamp from analytics data
        response_time_bucket = None

        if last_bot_timestamp > 0:
            user_response_time_seconds = time.time() - last_bot_timestamp
            logger.info(
                f"User response time calculated from analytics data: {user_response_time_seconds:.2f} seconds")
            # Map to buckets
            if user_response_time_seconds <= 120:
                response_time_bucket = "0-2minutes"
            elif user_response_time_seconds <= 300:
                response_time_bucket = "2-5 minutes"
            elif user_response_time_seconds <= 600:
                response_time_bucket = "5-10 minutes"
            elif user_response_time_seconds <= 1200:
                response_time_bucket = "10-20 minutes"
            elif user_response_time_seconds <= 1800:
                response_time_bucket = "20-30 minutes"
            elif user_response_time_seconds <= 3600:
                response_time_bucket = "30-60 minutes"
            elif user_response_time_seconds <= 7200:
                response_time_bucket = "1-2 Hours"
            elif user_response_time_seconds <= 18000:
                response_time_bucket = "2 - 5 hours"
            else:
                response_time_bucket = "Above 5 Hours"
            logger.info(
                f"Response time bucket determined: {response_time_bucket}")
        else:
            logger.info(
                "No previous bot response timestamp found in analytics data - setting first message bucket")
            response_time_bucket = "First Message"

        # Set response time field FIRST
        if response_time_bucket:
            time_field_update = {
                "response time": response_time_bucket
            }
            logger.info(
                f"Attempting to set response time field to: {response_time_bucket}")
            success = update_manychat_fields(subscriber_id, time_field_update)
            if success:
                logger.info(
                    f"Successfully set response time to {response_time_bucket} for {subscriber_id}")
            else:
                logger.error(
                    f"Failed to set response time for {subscriber_id}")

        # Wait 10 seconds before processing the rest
        logger.info("=== PHASE 2: Starting 10-second delay ===")
        await asyncio.sleep(10)
        logger.info("=== PHASE 3: Continuing with message processing ===")

        # Continue with the rest of the processing
        logger.info(f"Combined message for processing: {combined_message}")

        logger.info(
            f"Retrieved user data - Bio exists: {bool(bio)}, Topics count: {len(conversation_topics)}")

        # Build the prompt
        topics_str = "\\n- " + \
            "\\n- ".join(conversation_topics) if conversation_topics else "N/A"
        current_time_str = get_melbourne_time_str()
        combined_history_for_prompt = (prev_conv + "\\n") if prev_conv else ""
        combined_history_for_prompt += f"Lead: {combined_message}"

        # Check if user is a paying client and choose appropriate prompt
        # Get user data from SQLite to check client status
        try:
            import app.dashboard_modules.dashboard_sqlite_utils as db_utils
            conn = db_utils.get_db_connection()
            cursor = conn.cursor()

            # Try to find user by ig_username
            cursor.execute("""
                SELECT subscriber_id, first_name, last_name, client_status, journey_stage, 
                       metrics_json, last_message_timestamp
                FROM users 
                WHERE ig_username = ?
            """, (ig_username,))

            user_row = cursor.fetchone()
            conn.close()

            is_paying_client = False
            if user_row:
                # Parse journey_stage to check if paying client
                journey_stage_json = user_row[4]  # journey_stage
                if journey_stage_json:
                    try:
                        journey_stage = json.loads(journey_stage_json)
                        if isinstance(journey_stage, dict):
                            is_paying_client = journey_stage.get(
                                'is_paying_client', False)
                            trial_start_date_exists = journey_stage.get(
                                'trial_start_date') is not None
                            if trial_start_date_exists:
                                is_paying_client = True
                    except json.JSONDecodeError:
                        pass

                # Also check client_status field
                client_status = user_row[3] or ''  # client_status
                if client_status.lower() in ["active client", "trial", "paying client"]:
                    is_paying_client = True
        except Exception as e:
            logger.warning(
                f"Error checking client status for {ig_username}: {e}")
            is_paying_client = False

        # NEW: Clean up paying clients from ad flow if they're still in it
        if is_paying_client:
            try:
                from paying_client_cleanup import cleanup_paying_client_from_ad_flow
                cleanup_paying_client_from_ad_flow(ig_username)
            except ImportError:
                logger.warning(
                    "Could not import paying client cleanup function")

        # Fetch appropriate few-shot examples based on client status
        few_shot_examples = []
        try:
            if is_paying_client:
                # Use member few-shot examples for paying clients
                from app.dashboard_modules.dashboard_sqlite_utils import get_member_few_shot_examples
                few_shot_examples = get_member_few_shot_examples(limit=100)
                logger.info(
                    f"Using {len(few_shot_examples)} member few-shot examples for {ig_username}")
            else:
                # Use general few-shot examples for leads
                from app.dashboard_modules.dashboard_sqlite_utils import get_good_few_shot_examples
                few_shot_examples = get_good_few_shot_examples(limit=100)
                logger.info(
                    f"Using {len(few_shot_examples)} general few-shot examples for {ig_username}")
        except Exception as e:
            logger.warning(
                f"Error fetching few-shot examples for {ig_username}: {e}")

        # Choose appropriate prompt template
        if is_paying_client:
            # Use member chat prompt for paying clients
            client_data = {
                'ig_username': ig_username,
                'first_name': user_row[1] if user_row else '',
                'last_name': user_row[2] if user_row else '',
                'client_status': user_row[3] if user_row else 'Not a Client',
                'journey_stage': user_row[4] if user_row else 'Initial Inquiry'
            }

            prompt = prompts.MEMBER_CONVERSATION_PROMPT_TEMPLATE.format(
                current_melbourne_time_str=current_time_str,
                ig_username=ig_username,
                first_name=client_data.get('first_name', ''),
                fitness_goals="Not specified",
                dietary_requirements="Not specified",
                current_program="Active member",
                full_conversation=combined_history_for_prompt
            )
            logger.info(
                f"Using MEMBER_CONVERSATION_PROMPT_TEMPLATE for paying client: {ig_username}")
        else:
            # Use general chat prompt for leads
            prompt = prompts.GENERAL_CHAT_PROMPT_TEMPLATE.format(
                current_melbourne_time_str=current_time_str,
                bio=bio if bio else "N/A",
                topics_str=topics_str,
                interests=interests if interests else "N/A",
                full_conversation=combined_history_for_prompt
            )
            logger.info(
                f"Using GENERAL_CHAT_PROMPT_TEMPLATE for lead: {ig_username}")
        logger.info(f"Built prompt for {subscriber_id}")

        # Generate response
        response_text = call_gemini_with_retry(GEMINI_MODEL_PRO, prompt)
        if not response_text:
            logger.error(
                f"Failed to get response from Gemini for {subscriber_id}")
            return

        logger.info(
            f"Generated response for {subscriber_id}: {response_text[:100]}...")

        # Update analytics
        if ig_username:
            try:
                update_analytics_data(
                    ig_username, combined_message, response_text)
                logger.info(f"Updated analytics data for {ig_username}")
            except Exception as analytics_e:
                logger.error(f"Failed to update analytics: {analytics_e}")

        # Split and prepare response
        response_messages = split_response_into_messages(response_text)
        logger.info(f"Split response into {len(response_messages)} parts")

        # Prepare remaining field updates
        field_updates = {
            "o1 Response": response_messages[0] if response_messages else "",
            "o1 Response 2": response_messages[1] if len(response_messages) > 1 else "",
            "o1 Response 3": response_messages[2] if len(response_messages) > 2 else "",
            "CONVERSATION": combined_message
        }

        # Update remaining ManyChat fields
        success = update_manychat_fields(subscriber_id, field_updates)
        if success:
            logger.info(
                f"Successfully processed and sent response for {subscriber_id}")
        else:
            logger.error(
                f"Failed to update ManyChat fields for {subscriber_id}")

    except Exception as e:
        logger.error(
            f"Error in delayed message processing for {subscriber_id}: {e}", exc_info=True)
    finally:
        # Clean up task tracking
        if subscriber_id in user_buffer_tasks:
            del user_buffer_tasks[subscriber_id]
        user_buffer_task_scheduled[subscriber_id] = False
        logger.info(f"Cleaned up task tracking for {subscriber_id}")

# Modify the webhook handler


@app.post("/webhook/manychat")
@app.post("/manychat")
async def process_manychat_webhook(request: Request):
    """Handle incoming webhooks from ManyChat"""
    logger.info("=== ManyChat Webhook Received ===")
    current_time = time.time()

    try:
        # Log raw request data
        raw_data = await request.body()
        logger.info(f"Raw webhook data: {raw_data.decode()}")

        data = await request.json()
        logger.info(f"Parsed webhook data: {json.dumps(data, indent=2)}")

        subscriber_id = data.get("id", "")
        if not subscriber_id:
            logger.error("Missing subscriber ID in webhook data")
            raise HTTPException(
                status_code=400, detail="Missing subscriber ID")

        logger.info(f"Processing webhook for subscriber_id: {subscriber_id}")

        # Run cleanup to prevent memory leaks
        cleanup_stale_buffers()

        custom_fields = data.get("custom_fields", {})
        logger.info(
            f"Custom fields received: {json.dumps(custom_fields, indent=2)}")

        message = custom_fields.get("o1 input", "")
        logger.info(f"Original message: {message}")

        # Process any media in the message
        processed_message = process_conversation_for_media(message)
        logger.info(
            f"Processed message (after media handling): {processed_message}")

        # Check if user is currently being processed to prevent duplicates
        if user_buffer_task_scheduled.get(subscriber_id, False):
            logger.info(
                f"User {subscriber_id} is currently being processed. Adding message to buffer.")

        # Initialize buffer if needed
        if subscriber_id not in manychat_message_buffer:
            manychat_message_buffer[subscriber_id] = []
            manychat_last_message_time[subscriber_id] = current_time
            logger.info(
                f"Created new message buffer for subscriber {subscriber_id}")

        # Prepare message data for buffer
        message_data = {
            'timestamp': current_time,
            'text': processed_message,
            'original_data': data
        }

        # Add media context if present
        if "voice message:" in processed_message.lower():
            message_data['media_type'] = 'voice'
            message_data['media_desc'] = processed_message
        elif "video:" in processed_message.lower():
            message_data['media_type'] = 'video'
            message_data['media_desc'] = processed_message
        elif "photo of" in processed_message.lower():
            message_data['media_type'] = 'image'
            message_data['media_desc'] = processed_message

        # Add to buffer
        manychat_message_buffer[subscriber_id].append(message_data)
        logger.info(
            f"Added message to buffer for {subscriber_id}. Buffer size: {len(manychat_message_buffer[subscriber_id])}")

        # Cancel existing task if it exists
        if subscriber_id in user_buffer_tasks:
            try:
                user_buffer_tasks[subscriber_id].cancel()
                logger.info(
                    f"Cancelled existing processing task for {subscriber_id}")
            except Exception as e:
                logger.warning(
                    f"Error cancelling task for {subscriber_id}: {e}")

        # Start the delayed processing task
        task = asyncio.create_task(delayed_message_processing(subscriber_id))
        user_buffer_tasks[subscriber_id] = task
        user_buffer_task_scheduled[subscriber_id] = True
        logger.info(f"Created new delayed processing task for {subscriber_id}")

        return JSONResponse(status_code=200, content={"status": "processing"})

    except Exception as e:
        logger.error(f"Error in webhook handler: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# Add this near the top after the FastAPI app initialization


@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify the server is running"""
    return {"status": "ok", "message": "Server is running"}

if __name__ == "__main__":
    uvicorn.run("app.webhook_manychat:app",  # Corrected module path
                host="0.0.0.0",
                port=8001,
                reload=True,
                timeout_keep_alive=300,  # 5 minutes keep-alive timeout
                timeout_graceful_shutdown=300,  # 5 minutes graceful shutdown
                limit_concurrency=100,  # Limit concurrent connections
                backlog=2048  # Increase backlog size
                )
