from typing import Dict, Any, List, Optional, Tuple, Union
import json
import requests
import logging
import hashlib
import hmac
import os
import google.generativeai as genai
import google.oauth2.service_account
import googleapiclient.discovery
import re
from datetime import datetime, timedelta, timezone
import pytz
from app import prompts
import time
from collections import defaultdict
import dateutil.parser as parser
import httpx
from pydantic import BaseModel, Field
from google.cloud import speech_v1
import io
import tempfile
import random
import asyncio
from pathlib import Path
import subprocess
from PIL import Image
from todo_utils import add_todo_item

# Add guarded import for PostOnboardingHandler
try:
    from post_onboarding_handler import PostOnboardingHandler
except ImportError as e:
    PostOnboardingHandler = None
    logger = logging.getLogger("manychat_webhook")
    logger.warning(
        f"Could not import PostOnboardingHandler: {e}. Onboarding features disabled.")
import sqlite3
import shutil
import glob

# Import from the new manychat_utils module
from app.manychat_utils import update_manychat_fields
from app.analytics import update_analytics_data

def format_few_shot_examples(few_shot_examples: List[Dict[str, str]]) -> str:
    """Format few-shot examples for prompt injection"""
    if not few_shot_examples:
        return ""
    
    formatted = "\n\nHere are examples of how Shannon responds to members:\n"
    for example in few_shot_examples[-5:]:  # Use last 5 examples
        user_msg = example.get('user_message', '')
        shannon_response = example.get('shannon_response', '')
        if user_msg and shannon_response:
            formatted += f"\nMember: {user_msg}\nShannon: {shannon_response}\n"
    
    return formatted

# PostOnboardingHandler already imported with guard above

# Add stub for active users analysis if missing
if 'trigger_instagram_analysis_for_active_users' not in globals():
    async def trigger_instagram_analysis_for_active_users():
        return True


def verify_manychat_signature(payload: bytes, headers: dict) -> bool:
    """
    Verify ManyChat webhook signature.
    For now, returns True as signature verification is disabled in production.
    TODO: Implement proper signature verification when needed.
    """
    manychat_signature = headers.get(
        'X-ManyChat-Signature') or headers.get('x-manychat-signature')

    if not manychat_signature:
        logger.info(
            "No X-ManyChat-Signature header found. Proceeding without signature verification.")
        return True

    # For now, skip signature verification as it's commented out in production
    logger.info(
        "X-ManyChat-Signature verification would happen here (currently disabled).")
    return True


async def trigger_instagram_analysis_for_user() -> None:
    """
    Trigger Instagram analysis for active users.
    This is called during startup to initialize bio analysis.
    """
    try:
        import subprocess
        import os

        analyzer_script_path = os.path.join(
            os.path.dirname(__file__), "anaylize_followers.py")

        if os.path.exists(analyzer_script_path):
            logger.info("Triggering Instagram bio analysis for active users")
            # This could be enhanced to trigger analysis for specific users
            # For now, just log that it would happen
            logger.info("Instagram analysis would be triggered here")
        else:
            logger.warning(
                f"Analyzer script not found at {analyzer_script_path}")

    except Exception as e:
        logger.error(f"Error triggering Instagram analysis: {e}")

# Configure logging
logger = logging.getLogger("manychat_webhook")

# --- Add PIL for image type check --- START ---
PIL_AVAILABLE = False
try:
    # PIL is already imported as Image, so this try is more about confirming it's usable
    # and setting the flag, rather than re-importing.
    # We can do a simple check, e.g., by trying to access a PIL constant or a basic function.
    # Access a constant to confirm PIL (as Image) is somewhat functional
    _ = Image.MODES
    PIL_AVAILABLE = True
    logger.info(
        "PIL library (imported as Image) found and seems usable. Image verification enabled.")
except AttributeError:  # If Image module doesn't have MODES or similar expected attribute
    logger.warning(
        "PIL (imported as Image) does not seem fully functional. Image verification might be unreliable.")
except Exception as e:  # Catch any other exception during this check
    logger.warning(
        f"Could not confirm PIL (imported as Image) usability due to an error: {e}. Image verification may be unreliable.")
# --- Add PIL for image type check --- END ---

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

# Global configuration
MANYCHAT_API_KEY = os.getenv(
    "MANYCHAT_API_KEY", "996573:5b6dc180662de1be343655db562ee918")
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "AIzaSyAH6467EocGBwuMi-oDLawrNyCKjPHHmN8")
GEMINI_MODEL_PRO = "gemini-1.5-flash"
GEMINI_MODEL_FLASH = "gemini-1.5-flash"
GEMINI_MODEL_FLASH_STANDARD = "gemini-1.5-flash"

# File paths
CHECKIN_REVIEWS_DIR = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\output\\checkin_reviews"
SHEETS_CREDENTIALS_PATH = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\sheets_credentials.json"

# Database configuration - prefer PostgreSQL on Render, fallback to SQLite locally
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    logger.info("Using PostgreSQL database")
else:
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        sqlite_db_path = os.path.join(
            BASE_DIR, "app", "analytics_data_good.sqlite")
    except Exception:
        sqlite_db_path = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\app\\analytics_data_good.sqlite"
    logger.info(f"Using SQLite DB Path: {sqlite_db_path}")


def get_conn_cursor():
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        return conn, conn.cursor(cursor_factory=RealDictCursor)
    else:
        import sqlite3
        conn = sqlite3.connect(sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, conn.cursor()


def ensure_tables_pg(c, conn):
    if not USE_POSTGRES:
        return
    # Base tables
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id SERIAL PRIMARY KEY,
          ig_username TEXT UNIQUE,
          subscriber_id TEXT UNIQUE,
          first_name TEXT,
          last_name TEXT,
          client_status TEXT DEFAULT 'Not a Client',
          journey_stage TEXT DEFAULT 'Initial Inquiry',
          is_onboarding BOOLEAN DEFAULT FALSE,
          is_in_checkin_flow_mon BOOLEAN DEFAULT FALSE,
          is_in_checkin_flow_wed BOOLEAN DEFAULT FALSE,
          is_in_ad_flow BOOLEAN DEFAULT FALSE,
          ad_script_state TEXT,
          ad_scenario INTEGER,
          lead_source TEXT,
          fb_ad BOOLEAN DEFAULT FALSE,
          last_interaction_timestamp TEXT,
          profile_bio_text TEXT,
          interests_json TEXT DEFAULT '[]',
          conversation_topics_json TEXT DEFAULT '[]',
          client_analysis_json TEXT DEFAULT '{}',
          goals_text TEXT,
          current_fitness_level_text TEXT,
          injuries_limitations_text TEXT,
          preferred_workout_types_text TEXT,
          lifestyle_factors_text TEXT,
          engagement_preferences_text TEXT,
          meal_plan_summary TEXT,
          weekly_workout_summary TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
          id SERIAL PRIMARY KEY,
          ig_username TEXT,
          subscriber_id TEXT,
          message_type TEXT,
          message_text TEXT,
          sender TEXT,
          message TEXT,
          timestamp TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_reviews (
          id SERIAL PRIMARY KEY,
          user_ig_username TEXT,
          user_subscriber_id TEXT,
          subscriber_id TEXT,
          incoming_message_text TEXT,
          incoming_message_timestamp TEXT,
          generated_prompt_text TEXT,
          proposed_response_text TEXT,
          user_message TEXT,
          ai_response_text TEXT,
          final_response_text TEXT,
          prompt_type TEXT,
          status TEXT DEFAULT 'pending',
          created_timestamp TEXT,
          reviewed_timestamp TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Reconcile columns across versions (safe no-ops if present)
    alter_stmts = [
        # users
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS journey_stage TEXT DEFAULT 'Initial Inquiry'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_onboarding BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_in_checkin_flow_mon BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_in_checkin_flow_wed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ad_script_state TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ad_scenario INTEGER",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS lead_source TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS fb_ad BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_interaction_timestamp TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_bio_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS interests_json TEXT DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS conversation_topics_json TEXT DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS client_analysis_json TEXT DEFAULT '{}'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS goals_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_fitness_level_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS injuries_limitations_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_workout_types_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS lifestyle_factors_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS engagement_preferences_text TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS meal_plan_summary TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_workout_summary TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        # messages
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender TEXT",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS message TEXT",
        # pending_reviews
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS final_response_text TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS prompt_type TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS reviewed_timestamp TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS user_subscriber_id TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS incoming_message_text TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS incoming_message_timestamp TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS generated_prompt_text TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS proposed_response_text TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS user_message TEXT",
        "ALTER TABLE pending_reviews ADD COLUMN IF NOT EXISTS ai_response_text TEXT"
    ]
    for stmt in alter_stmts:
        try:
            c.execute(stmt)
        except Exception:
            pass
    conn.commit()


# Global state tracking
form_check_pending: Dict[str, bool] = {}
food_analysis_pending: Dict[str, bool] = {}
program_info = {}
manychat_last_bot_sent_timestamps: Dict[str, float] = {}
manychat_message_buffer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
manychat_last_message_time: Dict[str, float] = {}
program_edit_pending: Dict[str, str] = {}
message_buffer = {}

# Response options
FORM_CHECK_REQUEST_RESPONSES = [
    "Would love to, Send it through!",
    "Yeah keen! Flick it over.",
    "Sweet, send it my way.",
    "Yep, happy to take a look. Send it over.",
    "Awesome, send the video through when you're ready.",
    "Sure thing, let's see it.",
    "Keen to check it out, send it through!",
    "Easy, flick the video over.",
    "Yep, send it over and I'll have a look.",
    "Go for it, send the vid!"
]

# Constants
BUFFER_WINDOW = 15  # seconds to wait for grouping messages
RETRY_DELAY = 16  # Seconds to wait before retry
MAX_RETRIES = 3  # Maximum number of retry attempts

# Google Sheets Configuration
SPREADSHEET_ID = "1nDVn6jhkYBubVTQqbYU3PKo_WooeuTsQzsaNNcQdJlo"
ONBOARDING_SPREADSHEET_ID = "1038Ep0lYGEtpipNAIzH7RB67-KOAfXA-TcUTKBKqIfo"
RANGE_NAME = "Sheet1!A:E"
ONBOARDING_RANGE_NAME = "Sheet1!A:AAF"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Initialize Gemini
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to configure Gemini API: {e}", exc_info=True)

# Add this helper function near the top or with other helpers
ONBOARDING_COMPLETION_TRIGGERS = [
    "ill go over everything and set you up now",
    "thanks for joining up",
    "let me get into this",
    "i'll go over everything and set you up now",
    "i'll go over everything and set you up now",
    # Add more as needed
]


def is_onboarding_complete(ai_response: str) -> bool:
    response_lower = ai_response.lower()
    return any(trigger in response_lower for trigger in ONBOARDING_COMPLETION_TRIGGERS)

# Utility Functions


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


def load_json_data(file_path: str) -> Optional[Dict]:
    """Safely load JSON data from a file."""
    if not file_path or not os.path.exists(file_path):
        logger.error(
            f"[load_json_data] File not found or path is invalid: {file_path}")
        return None
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            logger.info(
                f"[load_json_data] Successfully loaded JSON data from: {file_path}")
            return data
    except json.JSONDecodeError as e:
        logger.error(
            f"[load_json_data] Failed to decode JSON from {file_path}: {e}")
        return None
    except FileNotFoundError:
        logger.error(f"[load_json_data] File not found error for: {file_path}")
        return None
    except Exception as e:
        logger.error(
            f"[load_json_data] Unexpected error loading JSON from {file_path}: {e}", exc_info=True)
        return None


def transcribe_audio_with_google(audio_bytes: bytes) -> Optional[str]:
    """Transcribe audio using Google Cloud Speech-to-Text with FFmpeg conversion and chunking for long audio."""
    if not AUDIO_PROCESSING_AVAILABLE:
        logger.warning(
            "Audio processing is not available - cannot transcribe audio")
        return "Audio message received (transcription not available)"

    temp_mp4_path = None
    temp_wav_path = None
    temp_chunk_dir = None

    try:
        # Create temp mp4 file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_mp4:
            temp_mp4.write(audio_bytes)
            temp_mp4_path = temp_mp4.name

        # Get duration using ffprobe
        ffprobe_cmd = [
            FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", temp_mp4_path
        ]
        try:
            duration_str = subprocess.check_output(
                ffprobe_cmd).decode('utf-8').strip()
            duration = float(duration_str)
            logger.info(f"Audio duration: {duration:.2f} seconds.")
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(
                f"Failed to get audio duration for {temp_mp4_path}: {e}")
            return None  # Cannot proceed without duration

        # Create temp wav file path
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name

        # Convert mp4 to wav
        ffmpeg_cmd = [
            FFMPEG_PATH, "-i", temp_mp4_path,
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-y", temp_wav_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        logger.info(f"Successfully converted to WAV: {temp_wav_path}")

        client = speech_v1.SpeechClient()
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

        if duration < 59:
            logger.info("Audio is short. Using standard recognition.")
            with open(temp_wav_path, "rb") as audio_file:
                content = audio_file.read()
            audio = speech_v1.RecognitionAudio(content=content)
            response = client.recognize(config=config, audio=audio)

            if response.results:
                transcription = response.results[0].alternatives[0].transcript
                logger.info(
                    f"Successfully transcribed short audio: {transcription}")
                return transcription
            else:
                logger.warning("No transcription results for short audio.")
                return None
        else:
            logger.info("Audio is long. Using chunking for recognition.")
            chunk_duration = 50  # seconds
            temp_chunk_dir = tempfile.mkdtemp()
            chunk_filename_pattern = os.path.join(
                temp_chunk_dir, "chunk_%03d.wav")

            # Use ffmpeg to split the wav file into chunks
            ffmpeg_chunk_cmd = [
                FFMPEG_PATH,
                "-i", temp_wav_path,
                "-f", "segment",
                "-segment_time", str(chunk_duration),
                chunk_filename_pattern
            ]

            result = subprocess.run(
                ffmpeg_chunk_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg chunking failed: {result.stderr}")
                return None
            logger.info(f"Successfully chunked audio into {temp_chunk_dir}")

            transcriptions = []
            chunk_files = sorted(
                glob.glob(os.path.join(temp_chunk_dir, "chunk_*.wav")))

            if not chunk_files:
                logger.error("FFmpeg created no chunk files.")
                return None

            for i, chunk_path in enumerate(chunk_files):
                with open(chunk_path, "rb") as audio_file:
                    content = audio_file.read()

                audio = speech_v1.RecognitionAudio(content=content)
                try:
                    response = client.recognize(config=config, audio=audio)
                    if response.results:
                        transcript = response.results[0].alternatives[0].transcript
                        transcriptions.append(transcript)
                        logger.info(
                            f"Transcribed chunk {i+1}/{len(chunk_files)}: {transcript[:50]}...")
                except Exception as chunk_e:
                    logger.error(
                        f"Error transcribing chunk {i+1} of {len(chunk_files)}: {chunk_e}")

            full_transcription = " ".join(transcriptions).strip()
            if full_transcription:
                logger.info(
                    f"Successfully transcribed long audio: {full_transcription[:100]}...")
                return full_transcription
            else:
                logger.warning(
                    "Transcription of long audio resulted in an empty string.")
                return None

    except Exception as e:
        logger.error(
            f"Error in audio transcription pipeline: {e}", exc_info=True)
        return None
    finally:
        # Cleanup
        if temp_mp4_path and os.path.exists(temp_mp4_path):
            os.unlink(temp_mp4_path)
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
        if temp_chunk_dir and os.path.exists(temp_chunk_dir):
            shutil.rmtree(temp_chunk_dir)


def analyze_media_url(media_url: str) -> tuple[Optional[str], Optional[str]]:
    """Downloads and processes media content, prioritizing video analysis for video files."""
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

        elif content_type == 'video/mp4':
            media_type = 'video'
            logger.info("Processing as video content")
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

            exercise_detection_prompt = """This is a video clip. Please analyze it and determine if it shows someone performing an exercise or workout. If it does:
            1. Identify the specific exercise being performed
            2. Note the number of repetitions visible (if applicable)
            3. Describe the overall form and technique shown

            If it's not an exercise video, just say "Not an exercise video" and describe the general content instead."""

            try:
                exercise_detection_model = genai.GenerativeModel(
                    GEMINI_MODEL_PRO)
                exercise_detection_contents = [
                    {
                        "parts": [
                            {"text": exercise_detection_prompt},
                            {"inline_data": {
                                "mime_type": content_type, "data": media_bytes}}
                        ]
                    }
                ]

                exercise_detection_response = exercise_detection_model.generate_content(
                    exercise_detection_contents)
                exercise_analysis = exercise_detection_response.text.strip()

                if "Not an exercise video" not in exercise_analysis:
                    prompt_text = """This is an exercise video. Please provide a detailed analysis including:
                    1. Exercise Identification: What exercise is being performed?
                    2. Form Analysis: Describe the technique and form shown in detail
                    3. Key Points: List the main technical aspects being demonstrated correctly or incorrectly
                    4. Safety Concerns: Note any potential safety issues or form corrections needed
                    5. Recommendations: Provide specific suggestions for improvement if needed

                    Format the response in clear sections for readability."""
                else:
                    prompt_text = """This is a video clip. Please:
                    1. Describe the main visual elements and actions
                    2. Note any text or captions visible
                    3. If audio is present, briefly describe its nature (e.g., speech, music, background noise)"""

            except Exception as e:
                logger.error(
                    f"Error during exercise detection with main model: {e}")
                try:
                    logger.info(
                        "Attempting exercise analysis with flash model...")
                    model = genai.GenerativeModel(GEMINI_MODEL_FLASH)
                    exercise_focused_prompt = """As a professional strength coach, analyze this exercise video clip in detail. Focus on:

1. Exercise Details:
- What exercise is being performed?
- Any specific variation or style?
- How many reps are shown?

2. Technical Analysis:
- Starting position and setup
- Movement execution quality
- Range of motion and depth
- Body positioning and alignment

3. Key Observations:
- What's being done well
- Areas needing improvement
- Safety considerations
- Quick form tips

If this isn't an exercise video, simply describe what you see."""

                    flash_contents = [
                        {
                            "parts": [
                                {"text": exercise_focused_prompt},
                                {"inline_data": {
                                    "mime_type": content_type, "data": media_bytes}}
                            ]
                        }
                    ]
                    flash_response = model.generate_content(flash_contents)
                    flash_analysis = flash_response.text.strip()

                    if any(exercise_term in flash_analysis.lower() for exercise_term in ['exercise', 'form', 'technique', 'deadlift', 'squat', 'bench', 'workout', 'rep', 'position', 'movement']):
                        prompt_text = """Provide a detailed exercise technique analysis including:
                        1. Exercise name and setup details
                        2. Movement execution quality
                        3. Specific form points observed
                        4. Safety considerations
                        5. Improvement suggestions"""
                    else:
                        prompt_text = """This is a video clip. Please:
                        1. Describe the main visual elements and actions
                        2. Note any text or captions visible
                        3. If audio is present, briefly describe its nature"""

                except Exception as flash_e:
                    logger.error(f"Flash model also failed: {flash_e}")
                    prompt_text = "Please describe what you see in this video, focusing on any exercise or movement technique if present."

        elif content_type.startswith('audio/'):
            media_type = 'audio'
            logger.info("Processing as audio content")
            transcription = transcribe_audio_with_google(media_bytes)
            if transcription:
                return 'audio', transcription
            else:
                logger.warning(
                    "Speech-to-Text failed for audio, falling back to Gemini audio analysis...")
                prompt_text = "This is an audio file. Please describe any indicators of audio content you can detect."

        else:
            logger.warning(f"Unrecognized content type: {content_type}")
            return None, None

        if not prompt_text:
            logger.error(
                f"No prompt text generated for media type {media_type}. This shouldn't happen.")
            return media_type, "Error: Could not generate analysis prompt."

        media_part = {
            "mime_type": content_type,
            "data": media_bytes
        }

        gemini_contents = [
            {
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": media_part}
                ]
            }
        ]

        gemini_description = None
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_PRO)
            response = model.generate_content(contents=gemini_contents)
            gemini_description = response.text.strip()
            logger.info(f"Successfully processed {media_type} with main model")
        except Exception as e:
            logger.warning(
                f"Main model failed for {media_type}: {e}. Trying flash model...")
            try:
                model = genai.GenerativeModel(GEMINI_MODEL_FLASH)
                simple_prompt = f"Briefly describe this {media_type} content."
                gemini_contents[0]['parts'][0]['text'] = simple_prompt
                response = model.generate_content(contents=gemini_contents)
                gemini_description = response.text.strip()
                logger.info(
                    f"Successfully processed {media_type} with flash model")
            except Exception as e2:
                logger.error(
                    f"All models failed to process {media_type}: {e2}")
                gemini_description = "Analysis failed."

        if media_type == 'video':
            final_result = f"Video Content: {gemini_description if gemini_description else 'Visual analysis failed.'}"
            if transcription:
                final_result += f" (Audio transcription: {transcription})"
            return media_type, final_result
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


def process_conversation_for_media(conversation_text: str) -> str:
    """Detects media URLs in conversation text, analyzes them, and replaces URLs with descriptions."""
    if not conversation_text:
        return ""

    url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"

    # Use re.search for efficiency since we only need to know if at least one URL exists
    if not re.search(url_pattern, conversation_text):
        logger.info(
            "No media URLs found in conversation text, returning original text.")
        return conversation_text

    logger.info("Potential media URLs found, starting replacement process.")

    processed_text = conversation_text
    # Now use re.finditer since we are performing replacements
    urls_found = list(re.finditer(url_pattern, conversation_text))

    for match in urls_found:
        url = match.group(1)
        logger.info(f"Processing URL found: {url[:100]}...")
        media_type, result_text = analyze_media_url(url)

        if media_type and result_text:
            if media_type == 'image':
                replacement_text = f"(Sent a photo: {result_text})"
            elif media_type == 'audio':
                replacement_text = f"(Voice message: {result_text})"
            elif media_type == 'video':
                replacement_text = f"(Sent a video: {result_text})"
            else:
                replacement_text = f"({media_type}: {result_text})"
            logger.info(
                f"Replacing URL with {media_type} description: {replacement_text[:100]}...")
        else:
            replacement_text = f"(Sent {media_type if media_type else 'media'}, but analysis failed)"
            logger.warning(f"Using generic placeholder for {url[:100]}")

        processed_text = processed_text.replace(url, replacement_text, 1)

    logger.info("Finished processing conversation text for media.")
    return processed_text


async def get_ai_response(prompt: str) -> Optional[str]:
    """Get response from Gemini with proper fallback handling"""
    async def try_model(model_name: str, retry_count: int = 0) -> Optional[str]:
        try:
            response = await call_gemini_with_retry(model_name, prompt)
            if response:
                logger.info(f"Got successful response from model {model_name}")
                return response
            logger.warning(f"No response from model {model_name}")
        except Exception as e:
            logger.error(f"Error with model {model_name}: {e}")
        return None

    # Try primary model
    logger.info("Trying primary model (PRO)")
    response = await try_model(GEMINI_MODEL_PRO)
    if response:
        return response

    # If primary fails, wait and try flash thinking model
    logger.warning(
        "Primary model failed. Waiting before trying flash-thinking model...")
    await asyncio.sleep(RETRY_DELAY)  # Wait before trying fallback
    logger.info("Trying flash-thinking model")
    response = await try_model(GEMINI_MODEL_FLASH)
    if response:
        return response

    # If flash thinking fails, wait and try standard flash model
    logger.warning(
        "Flash thinking model failed. Waiting before trying standard flash model...")
    await asyncio.sleep(RETRY_DELAY)  # Wait before trying second fallback
    logger.info("Trying standard flash model")
    response = await try_model(GEMINI_MODEL_FLASH_STANDARD)
    if response:
        return response

    # If all models fail, return None
    logger.error("All models failed to generate response")
    return None


async def call_gemini_with_retry(model_name: str, prompt: str, retry_count: int = 0) -> Optional[str]:
    """Call Gemini API with retry logic and multiple fallback models."""
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) and retry_count < MAX_RETRIES:
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Rate limit hit for {model_name}. Falling back to flash-thinking model after delay.")
                await asyncio.sleep(RETRY_DELAY)
                return await call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            else:
                wait_time = RETRY_DELAY * (retry_count + 1)
                logger.warning(
                    f"Rate limit hit. Waiting {wait_time} seconds before retry {retry_count + 1} on {model_name}")
                await asyncio.sleep(wait_time)
                return await call_gemini_with_retry(model_name, prompt, retry_count + 1)
        elif retry_count < MAX_RETRIES:
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Main model failed: {e}. Trying first fallback model after delay.")
                await asyncio.sleep(RETRY_DELAY)
                return await call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            elif model_name == GEMINI_MODEL_FLASH:
                logger.warning(
                    f"First fallback model failed: {e}. Trying second fallback model after delay.")
                await asyncio.sleep(RETRY_DELAY)
                return await call_gemini_with_retry(GEMINI_MODEL_FLASH_STANDARD, prompt, retry_count + 1)
        logger.error(f"All Gemini attempts failed: {e}")
        return None


def ensure_database_tables():
    """Ensure all required tables exist - create them if they don't"""
    if not USE_POSTGRES:
        return  # Skip for SQLite (tables should exist locally)

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                ig_username TEXT UNIQUE,
                subscriber_id TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                client_status TEXT DEFAULT 'Not a Client',
                journey_stage TEXT DEFAULT 'Initial Inquiry',
                is_onboarding BOOLEAN DEFAULT FALSE,
                is_in_checkin_flow_mon BOOLEAN DEFAULT FALSE,
                is_in_checkin_flow_wed BOOLEAN DEFAULT FALSE,
                is_in_ad_flow BOOLEAN DEFAULT FALSE,
                ad_script_state TEXT,
                ad_scenario INTEGER,
                lead_source TEXT,
                fb_ad BOOLEAN DEFAULT FALSE,
                last_interaction_timestamp TEXT,
                profile_bio_text TEXT,
                interests_json TEXT DEFAULT '[]',
                conversation_topics_json TEXT DEFAULT '[]',
                client_analysis_json TEXT DEFAULT '{}',
                goals_text TEXT,
                current_fitness_level_text TEXT,
                injuries_limitations_text TEXT,
                preferred_workout_types_text TEXT,
                lifestyle_factors_text TEXT,
                engagement_preferences_text TEXT,
                meal_plan_summary TEXT,
                weekly_workout_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                ig_username TEXT,
                subscriber_id TEXT,
                message_type TEXT,
                message_text TEXT,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create pending_reviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_reviews (
                id SERIAL PRIMARY KEY,
                user_ig_username TEXT,
                user_subscriber_id TEXT,
                subscriber_id TEXT,
                incoming_message_text TEXT,
                incoming_message_timestamp TEXT,
                generated_prompt_text TEXT,
                proposed_response_text TEXT,
                user_message TEXT,
                ai_response_text TEXT,
                final_response_text TEXT,
                prompt_type TEXT,
                status TEXT DEFAULT 'pending',
                created_timestamp TEXT,
                reviewed_timestamp TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create analytics_data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_data (
                id SERIAL PRIMARY KEY,
                subscriber_id TEXT,
                ig_username TEXT,
                message_text TEXT,
                message_direction TEXT,
                timestamp TEXT,
                first_name TEXT,
                last_name TEXT,
                client_status TEXT,
                journey_stage TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        logger.info("✅ Database tables ensured")
        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error ensuring database tables: {e}")


def get_database_connection():
    """Get database connection - PostgreSQL on Render, SQLite locally"""
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn, conn.cursor(cursor_factory=RealDictCursor)
    else:
        import sqlite3
        conn = sqlite3.connect(sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, conn.cursor()


def get_user_data(ig_username: str, subscriber_id: Optional[str] = None) -> tuple[list, dict, Optional[str]]:
    """Retrieve user data; create if missing. Uses Postgres on Render, SQLite locally."""
    conn = None
    try:
        conn, c = get_conn_cursor()

        # Ensure tables on Render (Postgres)
        ensure_tables_pg(c, conn)

        # Look up existing user
        if USE_POSTGRES:
            if subscriber_id:
                c.execute(
                    "SELECT * FROM users WHERE subscriber_id = %s", (subscriber_id,))
            else:
                c.execute(
                    "SELECT * FROM users WHERE ig_username = %s", (ig_username,))
            row = c.fetchone()
        else:
            if subscriber_id:
                c.execute(
                    "SELECT * FROM users WHERE subscriber_id = ?", (subscriber_id,))
            else:
                c.execute("SELECT * FROM users WHERE ig_username = ?",
                          (ig_username,))
            row = c.fetchone()

        # Create if missing (requires subscriber_id)
        if not row:
            if not subscriber_id:
                logger.error(
                    f"Cannot create user '{ig_username}' without subscriber_id")
                return [], {}, None
            if USE_POSTGRES:
                c.execute(
                    "INSERT INTO users (ig_username, subscriber_id, client_status) VALUES (%s, %s, %s)",
                    (ig_username, subscriber_id, "Not a Client"),
                )
                conn.commit()
                c.execute(
                    "SELECT * FROM users WHERE subscriber_id = %s", (subscriber_id,))
                row = c.fetchone()
            else:
                c.execute(
                    "INSERT INTO users (ig_username, subscriber_id, client_status) VALUES (?, ?, ?)",
                    (ig_username, subscriber_id, "Not a Client"),
                )
                conn.commit()
                c.execute(
                    "SELECT * FROM users WHERE subscriber_id = ?", (subscriber_id,))
                row = c.fetchone()

        # Normalize row → dict
        if USE_POSTGRES:
            user_data = dict(row) if row else {}
        else:
            user_columns = [col[0] for col in c.description]
            user_data = dict(zip(user_columns, row)) if row else {}

        # Get conversation history from messages table (handle multiple storage formats)
        history_query_key = user_data.get('subscriber_id')
        if not history_query_key:
            logger.warning(
                f"Could not find subscriber_id for history query. Falling back to ig_username for user {ig_username}")
            history_query_key = ig_username  # Fallback, not ideal

        # Query by subscriber_id first (support BOTH new and old column names)
        # New schema columns: message_type, message_text
        # Old schema columns: type, text
        if USE_POSTGRES:
            # Postgres uses %s placeholders
            try:
                c.execute(
                    "SELECT timestamp, message_type, message_text FROM messages WHERE subscriber_id = %s ORDER BY timestamp DESC LIMIT 200",
                    (history_query_key,),
                )
                history_rows_subscriber_new = c.fetchall()
            except Exception:
                history_rows_subscriber_new = []

            try:
                c.execute(
                    "SELECT timestamp, sender, message FROM messages WHERE subscriber_id = %s ORDER BY timestamp DESC LIMIT 200",
                    (history_query_key,),
                )
                history_rows_subscriber_old = c.fetchall()
            except Exception:
                history_rows_subscriber_old = []
        else:
            try:
                c.execute(
                    "SELECT timestamp, message_type, message_text FROM messages WHERE subscriber_id = ? ORDER BY timestamp DESC LIMIT 200",
                    (history_query_key,),
                )
                history_rows_subscriber_new = c.fetchall()
            except Exception:
                history_rows_subscriber_new = []

            c.execute(
                "SELECT timestamp, sender, message FROM messages WHERE subscriber_id = ? ORDER BY timestamp DESC LIMIT 200",
                (history_query_key,),
            )
            history_rows_subscriber_old = c.fetchall()

        # Query by ig_username (support BOTH new and old formats)
        if USE_POSTGRES:
            try:
                c.execute(
                    "SELECT timestamp, message_type, message_text FROM messages WHERE ig_username = %s ORDER BY timestamp DESC LIMIT 200",
                    (ig_username,),
                )
                history_rows_username_new = c.fetchall()
            except Exception:
                history_rows_username_new = []

            try:
                c.execute(
                    "SELECT timestamp, sender, message FROM messages WHERE ig_username = %s ORDER BY timestamp DESC LIMIT 200",
                    (ig_username,),
                )
                history_rows_username_old = c.fetchall()
            except Exception:
                history_rows_username_old = []
        else:
            try:
                c.execute(
                    "SELECT timestamp, message_type, message_text FROM messages WHERE ig_username = ? ORDER BY timestamp DESC LIMIT 200",
                    (ig_username,),
                )
                history_rows_username_new = c.fetchall()
            except Exception:
                history_rows_username_new = []

            c.execute(
                "SELECT timestamp, sender, message FROM messages WHERE ig_username = ? ORDER BY timestamp DESC LIMIT 200",
                (ig_username,),
            )
            history_rows_username_old = c.fetchall()

        # Combine both result sets and handle both storage formats
        history = []

        # Process subscriber_id results (new format)
        for ts, msg_type, text in history_rows_subscriber_new:
            if text is not None and text.strip():
                history.append({
                    "timestamp": ts,
                    "type": msg_type if msg_type is not None else "unknown",
                    "text": text
                })

        # Process subscriber_id results (old format)
        for ts, msg_type, text in history_rows_subscriber_old:
            if text is not None and text.strip():
                history.append({
                    "timestamp": ts,
                    "type": msg_type if msg_type is not None else "unknown",
                    "text": text
                })

        # Process ig_username results (new format)
        for ts, msg_type, text in history_rows_username_new:
            if text is not None and text.strip():
                history.append({
                    "timestamp": ts,
                    "type": msg_type if msg_type is not None else "unknown",
                    "text": text
                })

        # Process ig_username results (old format)
        for ts, sender, message in history_rows_username_old:
            if message is not None and message.strip():
                history.append({
                    "timestamp": ts,
                    "type": sender if sender is not None else "unknown",
                    "text": message
                })

        # Only augment with pending_reviews that were actually sent (status = 'sent')
        try:
            if USE_POSTGRES:
                c.execute(
                    """
                    SELECT ig_username FROM users WHERE subscriber_id = %s LIMIT 1
                    """,
                    (subscriber_id,),
                )
                row_user = c.fetchone()
                ig_for_pending = (row_user.get('ig_username')
                                  if row_user else None) or ig_username

                c.execute(
                    """
                    SELECT final_response_text, reviewed_timestamp, created_timestamp
                    FROM pending_reviews
                    WHERE user_ig_username = %s AND status = 'sent' AND final_response_text IS NOT NULL
                    ORDER BY created_timestamp DESC
                    LIMIT 50
                    """,
                    (ig_for_pending,),
                )
            else:
                c.execute(
                    """
                    SELECT ig_username FROM users WHERE subscriber_id = ? LIMIT 1
                    """,
                    (subscriber_id,),
                )
                row_user = c.fetchone()
                # SQLite row is a tuple when row_factory not dict; support both
                ig_for_pending = None
                try:
                    ig_for_pending = row_user[0] if row_user else None
                except Exception:
                    try:
                        ig_for_pending = row_user['ig_username'] if row_user else None
                    except Exception:
                        ig_for_pending = None
                ig_for_pending = ig_for_pending or ig_username

                c.execute(
                    """
                    SELECT final_response_text, reviewed_timestamp, created_timestamp
                    FROM pending_reviews
                    WHERE user_ig_username = ? AND status = 'sent' AND final_response_text IS NOT NULL
                    ORDER BY created_timestamp DESC
                    LIMIT 50
                    """,
                    (ig_for_pending,),
                )
            rows_sent = c.fetchall() or []
            for final_ai, reviewed_ts, created_ts in rows_sent:
                final_txt = str(final_ai).strip()
                if final_txt:
                    history.append({
                        "timestamp": (reviewed_ts or created_ts),
                        "type": "ai",
                        "text": final_txt,
                    })
        except Exception:
            pass

        # Normalize message type labels across schemas
        def _canonical_type(t: Optional[str]) -> str:
            t_lower = str(t or "").strip().lower()
            if t_lower in ("user", "incoming", "lead", "client"):
                return "user"
            if t_lower in ("ai", "assistant", "bot", "outgoing", "system"):
                return "ai"
            return t_lower or "unknown"

        for i in range(len(history)):
            history[i]["type"] = _canonical_type(history[i].get("type"))

        # Remove duplicates based on (timestamp, type, text) combination (more robust)
        seen = set()
        unique_history = []
        for msg in history:
            # Use first 80 chars and message type to detect duplicates
            key = (msg.get("timestamp"), msg.get(
                "type"), (msg.get("text") or "")[:80])
            if key not in seen:
                seen.add(key)
                unique_history.append(msg)

        # Sort by timestamp to get chronological order
        try:
            history = sorted(unique_history, key=lambda x: x["timestamp"])
        except Exception as e:
            logger.warning(
                f"Error sorting conversation history for {ig_username}: {e}")
            history = unique_history

        # Second-pass dedupe: collapse consecutive identical messages from the same sender
        # within a short window to avoid duplicates caused by multi-path logging/scheduling
        def _parse_dt(ts: Optional[str]) -> Optional[datetime]:
            if not ts:
                return None
            try:
                # Support both Zulu time and naive ISO strings
                return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                return None

        final_history: list[dict] = []
        last_by_type: dict[str, tuple[str, Optional[datetime]]] = {}
        last_by_text: dict[str, Optional[datetime]] = {}
        window = timedelta(minutes=5)

        for msg in history:
            msg_type = str(msg.get("type") or "unknown")
            msg_text = (msg.get("text") or "").strip()
            msg_dt = _parse_dt(msg.get("timestamp"))

            prev = last_by_type.get(msg_type)
            is_dup = False
            if prev:
                prev_text, prev_dt = prev
                if msg_text and prev_text == msg_text:
                    # If timestamps are close or unavailable, consider duplicate
                    if not prev_dt or not msg_dt or abs((msg_dt - prev_dt)) <= window:
                        is_dup = True

            # Cross-type duplicate check (same exact text any sender) within window
            if not is_dup and msg_text:
                prev_text_dt = last_by_text.get(msg_text)
                if prev_text_dt and msg_dt and abs((msg_dt - prev_text_dt)) <= window:
                    is_dup = True

            if not is_dup:
                final_history.append(msg)
                last_by_type[msg_type] = (msg_text, msg_dt)
                if msg_text:
                    last_by_text[msg_text] = msg_dt

        history = final_history

        # --- Populate metrics dictionary ---
        # Start with all data from the user row
        metrics = user_data.copy()

        # Ensure boolean fields are correctly typed
        metrics['is_onboarding'] = bool(metrics.get('is_onboarding', False))
        metrics['is_in_checkin_flow_mon'] = bool(
            metrics.get('is_in_checkin_flow_mon', False))
        metrics['is_in_checkin_flow_wed'] = bool(
            metrics.get('is_in_checkin_flow_wed', False))
        metrics['is_in_ad_flow'] = bool(metrics.get('is_in_ad_flow', False))

        # Parse JSON fields safely
        try:
            metrics['client_analysis'] = json.loads(
                metrics.get('client_analysis_json', '{}') or '{}')
        except (json.JSONDecodeError, TypeError):
            metrics['client_analysis'] = {}
            logger.error(
                f"Error parsing client_analysis_json for {ig_username}")

        # Extract interests and topics from the parsed client_analysis
        metrics['interests_json'] = json.dumps(
            metrics['client_analysis'].get('interests', []))
        metrics['conversation_topics_json'] = json.dumps(
            metrics['client_analysis'].get('conversation_topics', []))

        # Add workout data
        try:
            from workout_utils import get_current_week_workouts, format_workout_summary_for_prompt
            weekly_workouts = get_current_week_workouts(ig_username)
            if weekly_workouts and weekly_workouts.get('total_sessions', 0) > 0:
                metrics['weekly_workout_summary'] = format_workout_summary_for_prompt(
                    weekly_workouts)
            else:
                metrics['weekly_workout_summary'] = "No workout data available for this week."
        except Exception as e:
            logger.error(f"Error loading workout data for {ig_username}: {e}")
            metrics['weekly_workout_summary'] = "Error loading workout data."

        # Add conversation history to metrics for compatibility with action handlers
        metrics['conversation_history'] = history

        logger.info(f"Successfully retrieved data for user '{ig_username}'")
        return history, metrics, ig_username

    except Exception as e:
        logger.error(
            f"[get_user_data] SQLite error for {ig_username}: {e}", exc_info=True)
        return [], {}, None
    finally:
        if conn:
            conn.close()


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


def find_latest_checkin_file(full_name: str) -> Optional[str]:
    """Find the latest check-in JSON file for a given full name."""
    try:
        # Use full_name to construct pattern
        if not full_name or not isinstance(full_name, str):
            logger.error(
                "[find_latest_checkin_file] Invalid full_name provided.")
            return None

        # --- Use pathlib for robustness --- #
        # --- Add os.path.exists check for debugging --- #
        logger.info(
            f"[find_latest_checkin_file] Checking existence with os.path.exists for: {CHECKIN_REVIEWS_DIR}")
        if not os.path.exists(CHECKIN_REVIEWS_DIR):
            logger.error(
                f"[find_latest_checkin_file] os.path.exists failed for directory: {CHECKIN_REVIEWS_DIR}")
            # Return None here as if the basic check fails, pathlib likely will too
            return None
        else:
            logger.info(
                f"[find_latest_checkin_file] os.path.exists confirmed directory exists: {CHECKIN_REVIEWS_DIR}")
        # --- End os.path.exists check --- #

        checkin_dir_path = Path(CHECKIN_REVIEWS_DIR)
        if not checkin_dir_path.is_dir():
            logger.error(
                f"[find_latest_checkin_file] Check-in directory not found: {CHECKIN_REVIEWS_DIR}")
            return None

        # Try standard name order
        safe_name = full_name.replace(' ', '_').lower()
        filename_pattern = f"{safe_name}_*_fitness_wrapped_data.json"
        # --- Ensure logging uses full_name --- #
        logger.info(
            f"[find_latest_checkin_file] Searching pattern for '{full_name}': {checkin_dir_path / filename_pattern}")
        files = list(checkin_dir_path.glob(filename_pattern))

        # --- Debug: Log initial glob result --- #
        logger.info(
            f"[find_latest_checkin_file] Initial glob result for standard pattern '{filename_pattern}': {files}")
        # --- End Debug ---

        # Try swapped name order if no files found with standard order
        if not files:
            name_parts = full_name.split()
            if len(name_parts) >= 2:
                # Simple swap
                swapped_name = f"{name_parts[-1]} {name_parts[0]}"
                safe_name_swapped = swapped_name.replace(' ', '_').lower()
                filename_pattern_swapped = f"{safe_name_swapped}_*_fitness_wrapped_data.json"
                # --- Ensure logging uses full_name --- #
                logger.info(
                    f"[find_latest_checkin_file] Trying swapped pattern for '{full_name}': {checkin_dir_path / filename_pattern_swapped}")
                files = list(checkin_dir_path.glob(filename_pattern_swapped))

        if not files:
            # --- Ensure logging uses full_name --- #
            logger.warning(
                f"[find_latest_checkin_file] No check-in files found for '{full_name}' matching patterns.")
            return None

        # Extract dates and sort
        dated_files = []
        for f_path in files:
            try:
                # Extract date string assuming format username_YYYYMMDD_...
                filename = os.path.basename(f_path)
                # filename_base = filename.split('_fitness_wrapped_data.json')[0]
                # filename_parts = filename_base.split('_')
                # Assuming date is YYYY-MM-DD format right before _fitness...
                date_str_match = re.search(r'_(\d{4}-\d{2}-\d{2})_', filename)
                if date_str_match:
                    date_str = date_str_match.group(1)
                    # Attempt to parse the date (YYYY-MM-DD format)
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    # --- Store Path object --- #
                    dated_files.append((file_date, f_path))
                else:
                    logger.warning(
                        f"[find_latest_checkin_file] Could not parse YYYY-MM-DD date from filename: {filename}")
            except (ValueError, IndexError, AttributeError) as e:
                logger.warning(
                    f"[find_latest_checkin_file] Error parsing date from file {f_path}: {e}")

        if not dated_files:
            # --- Ensure logging uses full_name --- #
            logger.error(
                f"[find_latest_checkin_file] No files with parseable dates found for '{full_name}'")
            return None

        # Sort by date, newest first
        dated_files.sort(key=lambda x: x[0], reverse=True)
        latest_file_path = dated_files[0][1]
        # --- Ensure logging uses full_name --- #
        # --- Convert Path back to string for return --- #
        latest_file_str = str(latest_file_path)
        logger.info(
            f"[find_latest_checkin_file] Found latest check-in file for '{full_name}': {latest_file_str}")
        return latest_file_str

    except Exception as e:
        # --- Ensure logging uses full_name --- #
        logger.error(
            f"[find_latest_checkin_file] Error finding latest check-in file for '{full_name}': {e}", exc_info=True)
        return None


def build_member_chat_prompt(
    client_data: Dict[str, Any],
    current_message: str,
    conversation_history: str = "",
    current_stage: str = "Topic 1",
    trial_status: str = "Initial Contact",
    full_name: Optional[str] = None,
    full_conversation_string: str = "",
    few_shot_examples: Optional[List[Dict[str, str]]] = None
) -> tuple[str, str]:
    """
    Builds a comprehensive prompt for Gemini based on client data, conversation history,
    current interaction, and potentially few-shot examples.
    """
    logger.info(
        f"Building prompt for: {full_name if full_name else 'Unknown User'}")

    # --- Start: Few-Shot Example Injection ---
    few_shot_prompt_segment = ""
    if few_shot_examples:
        example_texts = []
        for i, example in enumerate(few_shot_examples):
            user_msg = example.get("user_message", "No user message provided.")
            shan_resp = example.get(
                "shanbot_response", "No Shanbot response provided.")
            rationale = example.get("rationale", "").strip()
            example_text = f"--- Example {i+1} ---\n"
            example_text += f"Client Message: {user_msg}\n"
            example_text += f"Shanbot's Excellent Response: {shan_resp}\n"
            if rationale:
                example_text += f"Reasoning for Excellence: {rationale}\n"
            example_text += f"--- End Example {i+1} ---\n"
            example_texts.append(example_text)
        if example_texts:
            few_shot_prompt_segment = ("Here are some examples of excellent responses and the reasoning behind them. "
                                       "Emulate this style and thinking:\n\n" +
                                       "\n".join(example_texts) +
                                       "\nNow, considering these examples, our conversation history, and your role, "
                                       "please respond to the current message and situation described below.\n"
                                       "-------------------------------------\n\n")
    # --- End: Few-Shot Example Injection ---

    # --- NEW: Prepare detailed bio_context from client_data['client_analysis'] and root metrics ---
    detailed_bio_context_str = "PROFILE INSIGHTS:\\n"
    raw_client_analysis = client_data.get('client_analysis', {})
    insights_found = False

    # Renamed to avoid conflict if other get_unique_items exists
    def get_unique_items_for_bio(*sources: Any) -> List[str]:
        all_items_intermediate: List[Any] = []
        for source in sources:
            if isinstance(source, list):
                all_items_intermediate.extend(source)
            elif isinstance(source, str) and source.strip():
                all_items_intermediate.append(source)

        processed_items: List[str] = []
        for item in all_items_intermediate:
            if isinstance(item, str) and item.strip() and item.lower() not in ["unknown", "not specified", "n/a", "[]", "{}"]:
                processed_items.append(item.strip())
        return sorted(list(set(processed_items)))

    # --- Fetch data, checking both client_analysis and root metrics as fallback ---
    # Interests
    interests_from_analysis = raw_client_analysis.get('interests', [])
    interests_from_root = client_data.get(
        'interests', [])  # Check root metrics
    detected_interests = get_unique_items_for_bio(
        interests_from_analysis, interests_from_root)
    if detected_interests:
        detailed_bio_context_str += f"- Interests: {', '.join(detected_interests)}\\n"
        insights_found = True

    # Recent Activities
    recent_activities_from_analysis = raw_client_analysis.get(
        'recent_activities', [])
    recent_activities_from_root = client_data.get(
        'recent_activities', [])  # Check root metrics
    recent_activities = get_unique_items_for_bio(
        recent_activities_from_analysis, recent_activities_from_root)
    if recent_activities:
        detailed_bio_context_str += f"- Recent Activities: {', '.join(recent_activities)}\\n"
        insights_found = True

    # Personality Traits (Assume primarily in profile_bio within analysis, but include fallback check)
    nested_profile_bio = raw_client_analysis.get('profile_bio', {})
    if not isinstance(nested_profile_bio, dict):
        nested_profile_bio = {}
    personality_traits_from_analysis = nested_profile_bio.get(
        'PERSONALITY TRAITS', [])
    personality_traits_from_root = client_data.get(
        'personality_traits', [])  # Check root metrics if exists
    personality_traits = get_unique_items_for_bio(
        personality_traits_from_analysis, personality_traits_from_root)
    if personality_traits:
        detailed_bio_context_str += f"- Personality Traits: {', '.join(personality_traits)}\\n"
        insights_found = True

    # Lifestyle Indicators (Check both analysis and root metrics)
    lifestyle_indicators_from_analysis = raw_client_analysis.get(
        'lifestyle_indicators', [])
    lifestyle_indicators_from_root = client_data.get(
        'lifestyle_indicators', [])  # Check root metrics
    lifestyle_notes_from_profile = nested_profile_bio.get('LIFESTYLE', "")

    combined_lifestyle_info = []
    if isinstance(lifestyle_indicators_from_analysis, list):
        combined_lifestyle_info.extend(lifestyle_indicators_from_analysis)
    if isinstance(lifestyle_indicators_from_root, list):
        combined_lifestyle_info.extend(lifestyle_indicators_from_root)
    if isinstance(lifestyle_notes_from_profile, str) and lifestyle_notes_from_profile.strip():
        combined_lifestyle_info.append(lifestyle_notes_from_profile)

    unique_lifestyle_entries = get_unique_items_for_bio(
        combined_lifestyle_info)

    if unique_lifestyle_entries:
        detailed_bio_context_str += f"- Lifestyle Indicators: {', '.join(unique_lifestyle_entries)}\\n"
        insights_found = True

    # Conversation Topics (Check both analysis and root metrics)
    conversation_topics_from_analysis = raw_client_analysis.get(
        'conversation_topics', [])
    conversation_topics_from_root = client_data.get(
        'conversation_topics', [])  # Check root metrics
    conversation_topics = get_unique_items_for_bio(
        conversation_topics_from_analysis, conversation_topics_from_root)
    if conversation_topics:
        detailed_bio_context_str += f"- Conversation Topics: {', '.join(conversation_topics)}\\n"
        insights_found = True

    if not insights_found:
        detailed_bio_context_str += "No specific profile insights found.\\n"

    # Log the constructed bio_context for debugging, e.g., for a specific user
    if client_data.get('ig_username') == 'shereesbodybuildingjourney_':
        logger.info(
            f"[DEBUG BIO CONTEXT for shereesbodybuildingjourney_] detailed_bio_context_str:\\n{detailed_bio_context_str}")

    # Add debug log for haydenlyons___ to see what's happening
    if client_data.get('ig_username') == 'haydenlyons___':
        logger.info(
            f"[DEBUG BIO CONTEXT for haydenlyons___] detailed_bio_context_str:\\n{detailed_bio_context_str}")
        logger.info(
            f"[DEBUG BIO CONTEXT for haydenlyons___] raw_client_analysis keys: {list(raw_client_analysis.keys()) if isinstance(raw_client_analysis, dict) else 'Not a dict'}")
        logger.info(
            f"[DEBUG BIO CONTEXT for haydenlyons___] client_data keys: {list(client_data.keys())}")

    # --- End: Prepare detailed bio_context ---

    prompt_type = "general_chat"
    is_mon_checkin = client_data.get('is_in_checkin_flow_mon', False)
    is_wed_checkin = client_data.get('is_in_checkin_flow_wed', False)
    is_in_ad_flow = client_data.get('is_in_ad_flow', False)

    if is_mon_checkin:
        base_prompt_template = prompts.MONDAY_MORNING_TEXT_PROMPT_TEMPLATE
        prompt_type = "monday_morning_text"
        logger.info(
            f"Using MONDAY_MORNING_TEXT_PROMPT_TEMPLATE for {full_name}")
    elif is_wed_checkin:
        base_prompt_template = prompts.CHECKINS_PROMPT_TEMPLATE
        prompt_type = "checkins"
        logger.info(f"Using CHECKINS_PROMPT_TEMPLATE for {full_name}")
    elif is_in_ad_flow:
        base_prompt_template = prompts.COMBINED_AD_RESPONSE_PROMPT_TEMPLATE
        prompt_type = "facebook_ad_response"
        logger.info(
            f"Using COMBINED_AD_RESPONSE_PROMPT_TEMPLATE for ad flow: {full_name}")
    else:
        client_status = str(client_data.get('client_status', 'Lead')).lower()
        journey_stage = client_data.get('journey_stage', {})
        if not isinstance(journey_stage, dict):
            journey_stage = {}
        is_paying_client = journey_stage.get('is_paying_client', False)
        trial_start_date_exists = journey_stage.get(
            'trial_start_date') is not None
        if is_paying_client or trial_start_date_exists or client_status in ["active client", "trial", "paying client"]:
            
            # NEW: TRY PERSONALIZED PROMPTING FIRST
            try:
                from scripts.integrate_personalized_prompting import MemberPersonalityManager
                
                ig_username = client_data.get('ig_username', '')
                if ig_username:
                    logger.info(f"🎯 Attempting personalized prompt for {ig_username}")
                    
                    manager = MemberPersonalityManager()
                    
                    # Build context for personalized prompting
                    context = {
                        'current_melbourne_time_str': get_melbourne_time_str(),
                        'first_name': full_name or ig_username,
                        'fitness_goals': client_data.get('fitness_goals', ''),
                        'dietary_requirements': client_data.get('dietary_requirements', ''),
                        'current_program': client_data.get('current_program', ''),
                        'few_shot_examples': format_few_shot_examples(few_shot_examples) if few_shot_examples else ''
                    }
                    
                    # Try personalized prompting
                    personalized_prompt, success = manager.generate_personalized_member_prompt(
                        ig_username, current_message, full_conversation_string, context
                    )
                    
                    if success:
                        logger.info(f"✅ Using personalized prompt for {ig_username}")
                        return personalized_prompt, "personalized_member_chat"
                    else:
                        logger.info(f"⚠️ Personalized prompting unavailable for {ig_username}, using fallback")
            
            except Exception as e:
                logger.warning(f"⚠️ Personalized prompting failed for {ig_username}: {e}")
            
            # FALLBACK: Use existing member prompt (your current code continues unchanged)
            base_prompt_template = prompts.MEMBER_CONVERSATION_PROMPT_TEMPLATE
            prompt_type = "member_chat"
            logger.info(
                f"Using MEMBER_CONVERSATION_PROMPT_TEMPLATE for member: {full_name}")
        else:
            # Check for A/B testing strategy for fresh vegan contacts
            ig_username = client_data.get('ig_username', '')
            try:
                from conversation_strategy import get_conversation_strategy_for_user, log_strategy_usage, log_strategy_to_database
                strategy_info = get_conversation_strategy_for_user(ig_username)

                # Log A/B test assignment to database for analytics
                is_fresh_vegan = strategy_info['strategy'] in [
                    'fresh_vegan_direct', 'fresh_vegan_rapport']
                if is_fresh_vegan:
                    log_strategy_to_database(
                        ig_username, strategy_info['approach_type'], is_fresh_vegan=True)

                if strategy_info['strategy'] == 'fresh_vegan_direct':
                    # Use direct vegan approach template
                    base_prompt_template = prompts.DIRECT_VEGAN_APPROACH_PROMPT_TEMPLATE
                    prompt_type = "general_chat"
                    logger.info(
                        f"Using DIRECT_VEGAN_APPROACH_PROMPT_TEMPLATE for fresh vegan contact: {full_name} (A/B Test Group B)")

                    # Log strategy usage for analytics
                    log_strategy_usage(
                        ig_username, strategy_info, current_message[:100])

                elif strategy_info['strategy'] == 'fresh_vegan_rapport':
                    # Use standard approach for rapport-first group
                    base_prompt_template = prompts.COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE
                    prompt_type = "general_chat"
                    logger.info(
                        f"Using COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE for fresh vegan contact: {full_name} (A/B Test Group A)")

                    # Log strategy usage for analytics
                    log_strategy_usage(
                        ig_username, strategy_info, current_message[:100])

                else:
                    # Default to standard prompt for established relationships or general chat
                    base_prompt_template = prompts.COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE
                    prompt_type = "general_chat"
                    logger.info(
                        f"Using COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE for {full_name} (Strategy: {strategy_info['strategy']})")

            except Exception as e:
                # Fallback to standard template if strategy detection fails
                logger.warning(
                    f"Error determining conversation strategy for {ig_username}: {e}")
                base_prompt_template = prompts.COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE
                prompt_type = "general_chat"
                logger.info(
                    f"Using COMBINED_CHAT_AND_ONBOARDING_PROMPT_TEMPLATE for {full_name} (fallback)")

    profile_bio_text = str(client_data.get(
        'profile_bio_text', 'Not available'))

    interests_from_client_data = client_data.get('interests_json', '[]')
    try:
        interests_list = json.loads(interests_from_client_data)
        if isinstance(interests_list, dict) and 'interests' in interests_list:
            interests_list = interests_list['interests']
        if isinstance(interests_list, list):
            interests_formatted = ", ".join(
                filter(None, interests_list)) if interests_list else "Not available"
        else:
            interests_formatted = "Interests data not in expected list format"
    except json.JSONDecodeError:
        interests_formatted = "Interests not available (JSON error)"

    topics_from_client_data = client_data.get('conversation_topics_json', '[]')
    try:
        topics_list = json.loads(topics_from_client_data)
        if isinstance(topics_list, list):
            filtered_topics = [topic for topic in topics_list if isinstance(
                topic, str) and not topic.startswith('**')]
            conversation_topics_formatted = ", ".join(
                filtered_topics) if filtered_topics else "No specific topics listed"
        else:
            conversation_topics_formatted = "Topics data not in expected list format"
    except json.JSONDecodeError:
        conversation_topics_formatted = "Topics not available (JSON error)"

    goals_text = str(client_data.get('goals_text', 'Not specified'))
    current_fitness_level_text = str(client_data.get(
        'current_fitness_level_text', 'Not specified'))
    injuries_limitations_text = str(client_data.get(
        'injuries_limitations_text', 'None specified'))
    preferred_workout_types_text = str(client_data.get(
        'preferred_workout_types_text', 'Not specified'))
    lifestyle_factors_text = str(client_data.get(
        'lifestyle_factors_text', 'Not specified'))
    engagement_preferences_text = str(client_data.get(
        'engagement_preferences_text', 'Not specified'))
    first_name_from_data = str(client_data.get('first_name', ''))
    last_name_from_data = str(client_data.get('last_name', ''))
    effective_full_name = full_name if full_name else f"{first_name_from_data} {last_name_from_data}".strip(
    )
    if not effective_full_name:
        effective_full_name = client_data.get('ig_username', 'the user')

    final_conversation_context = full_conversation_string
    if not final_conversation_context:
        # Normalize and dedupe history before building fallback conversation context
        try:
            from app.general_utils import clean_and_dedupe_history
        except Exception:
            from general_utils import clean_and_dedupe_history  # fallback

        cleaned_history = clean_and_dedupe_history(
            client_data.get('conversation_history', []), max_items=40)
        formatted_history = format_conversation_history(cleaned_history)
        if formatted_history:
            final_conversation_context = f"{formatted_history}\nUser: {current_message}"
        else:
            final_conversation_context = f"User: {current_message}"

    weekly_workout_summary = client_data.get(
        'weekly_workout_summary', "No recent workout data available")
    if 'Workout data module not found' in weekly_workout_summary or 'Error loading workout data' in weekly_workout_summary:
        ig_username_for_workout = client_data.get('ig_username')
        if ig_username_for_workout:
            try:
                current_workouts = get_current_week_workouts(
                    ig_username_for_workout)
                weekly_workout_summary = format_workout_summary_for_prompt(
                    current_workouts)
            except Exception as e_workout:
                logger.warning(
                    f"Secondary attempt to load workout data for {ig_username_for_workout} failed: {e_workout}")

    prompt_data = {
        "ig_username": client_data.get('ig_username', 'Unknown User'),
        # This is the short IG bio (from users.bio)
        "bio": client_data.get('profile_bio_text', 'Not available'),
        # These might be redundant if we use bio_context, but keep for now if templates use them directly
        # Ensure interests are populated from best source
        "interests": get_unique_items_for_bio(client_data.get('interests', []), raw_client_analysis.get('interests', [])),
        # Ensure topics from best source
        "topics_str": ", ".join(get_unique_items_for_bio(client_data.get('conversation_topics', []), raw_client_analysis.get('conversation_topics', []))),

        # Add the new detailed bio context
        "bio_context": detailed_bio_context_str.strip(),

        "weekly_workout_summary": weekly_workout_summary,
        "current_stage": current_stage,
        "trial_status": trial_status,
        "full_conversation": final_conversation_context,
        "current_melbourne_time_str": get_melbourne_time_str(),
        "effective_full_name": effective_full_name,
        "goals_text": goals_text,
        "current_fitness_level_text": current_fitness_level_text,
        "injuries_limitations_text": injuries_limitations_text,
        "preferred_workout_types_text": preferred_workout_types_text,
        "lifestyle_factors_text": lifestyle_factors_text,
        "engagement_preferences_text": engagement_preferences_text,
        "meal_plan_summary": client_data.get('meal_plan_summary', 'Not available'),
        "expected_onboarding_input": client_data.get("expected_onboarding_input", "general information"),

        # Ad-specific parameters for COMBINED_AD_RESPONSE_PROMPT_TEMPLATE
        # Use the exact placeholder names used by the template
        "script_state": client_data.get('ad_script_state', 'step1'),
        "ad_scenario": client_data.get('ad_scenario', 1)
    }

    final_prompt_str = (few_shot_prompt_segment +
                        base_prompt_template.format_map(defaultdict(str, prompt_data)))

    # NOTE: The latest user message is already included in `full_conversation`.
    # Removing the additional "Last User Message" block prevents the same content
    # from appearing twice in the prompt, which was confusing the model and led
    # to comments like "Looks like those messages came through again hey".

    # Log the first 500 chars of the prompt to check structure if needed
    # logger.debug(f"Final prompt for {effective_full_name} (first 500 chars):\n{final_prompt_str[:500]}")

    return final_prompt_str, prompt_type


async def send_manychat_message(subscriber_id: str, message: str) -> bool:
    """Send a message to a ManyChat subscriber."""
    try:
        field_updates = {
            "o1 Response": message
        }

        # Track calendar link sends
        if "calendly.com/shannonrhysbirch/15min" in message:
            try:
                # Import calendly integration
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                from calendly_integration import CalendlyIntegration

                # Get Instagram username from subscriber_id
                ig_username = await get_username_from_manychat(subscriber_id)
                if ig_username:
                    calendly = CalendlyIntegration()
                    calendly.track_calendar_link_sent(
                        ig_username, subscriber_id)
                    logger.info(
                        f"Tracked calendar link sent to @{ig_username}")
            except Exception as e:
                logger.warning(f"Failed to track calendar link send: {e}")

        # If user asks about price after Calendly has been sent, do not restart discovery; nudge call
        try:
            last_user_message = None
            try:
                from app.db_backend import add_message_to_history
                # In this context we don't have the latest user text; logic stays in state machine
                pass
            except Exception:
                pass
        except Exception:
            pass

        return update_manychat_fields(subscriber_id, field_updates)
    except Exception as e:
        logger.error(f"Error sending message to ManyChat: {e}")
        return False


# --- Helper Function to Add "To Do" Item --- START ---


# --- Helper Function to Add "To Do" Item --- END ---


# Added subscriber_id
async def detect_and_handle_action(ig_username: str, message_text: str, subscriber_id: Optional[str], data: Dict = None) -> bool:
    """Uses Gemini to detect user intent and handles multiple actions like Trainerize edits or food analysis within one message."""
    logger.info(
        f"[detect_and_handle_action] Analyzing message from {ig_username} (SubID: {subscriber_id}) for multiple actions: {message_text[:100]}"
    )

    if not data:
        logger.error("No data dictionary provided to detect_and_handle_action")
        # If data is missing, we likely don't have subscriber_id either, handle gracefully
        # Fallback to trying lookup by ig_username only, although less reliable
        subscriber_id = None  # Explicitly set to None if data dict is missing

    # --- ONBOARDING CHECK --- START ---
    logger.info(
        f"[detect_and_handle_action] Starting onboarding check for {ig_username} (SubID: {subscriber_id})")

    try:
        # Get user data to check onboarding status, passing subscriber_id
        # Ensure get_user_data returns 3 values: history, metrics, user_id_key
        conversation_history, metrics_dict, user_id_key = get_user_data(
            ig_username, subscriber_id)  # Pass subscriber_id

        if user_id_key:  # Check if user was found
            logger.info(
                f"[detect_and_handle_action] Retrieved metrics for onboarding check: {json.dumps(metrics_dict.get('calorie_tracking', {}), indent=2)}")

            # Check if user is in onboarding (for logging only now)
            is_onboarding = metrics_dict.get('is_onboarding', False)
            logger.info(
                f"[detect_and_handle_action] Onboarding status for {ig_username}: {is_onboarding}")

            logger.info(
                f"[detect_and_handle_action] User {ig_username} is NOT marked as currently onboarding (or check passed). Proceeding to specific intent detection.")
        else:
            # This case means get_user_data failed to find the user
            logger.warning(
                f"[detect_and_handle_action] User not found during onboarding check (ig='{ig_username}', sub='{subscriber_id}'). Cannot check onboarding status.")
            # Continue processing as if not onboarding, as we can't confirm otherwise

    except Exception as e:
        # Catch potential unpacking errors if get_user_data structure changes unexpectedly
        logger.error(
            f"[detect_and_handle_action] Error during onboarding check (potentially unpacking): {str(e)}", exc_info=True)
        # Proceed cautiously, assuming not onboarding if check fails
        pass  # Allow execution to continue to intent detection

    logger.info(
        f"[detect_and_handle_action] Completed onboarding check for {ig_username}")
    # --- ONBOARDING CHECK --- END ---

    intent_prompt = f"""Analyze this message to identify ALL requested actions:
# ... rest of intent_prompt ...
"""
    # ... rest of detect_and_handle_action ...


async def set_manychat_custom_field(subscriber_id: str, field_name: str, field_value: Any, field_id: Optional[int] = None) -> bool:
    """Sets a custom field for a ManyChat subscriber, using field_id if provided."""
    if not MANYCHAT_API_KEY or MANYCHAT_API_KEY == "YOUR_MANYCHAT_API_KEY_HERE":
        logger.error(
            "[ManyChat] MANYCHAT_API_KEY is not configured. Cannot set custom field.")
        return False
    if not subscriber_id:
        logger.error(
            f"[ManyChat] Missing subscriber_id ('{subscriber_id}') for set_manychat_custom_field.")
        return False
    if not field_name and not field_id:
        logger.error(
            f"[ManyChat] Missing both field_name and field_id for set_manychat_custom_field. One must be provided.")
        return False

    api_url = "https://api.manychat.com/fb/subscriber/setCustomField"
    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "subscriber_id": str(subscriber_id),
        "field_value": field_value
    }

    if field_id:
        payload["field_id"] = field_id
        logger.info(
            f"[ManyChat] Attempting to set custom field by ID '{field_id}': {field_value} (type: {type(field_value)}) for subscriber_id: {subscriber_id} via API.")
    elif field_name:  # Fallback to field_name if field_id is not provided
        payload["field_name"] = field_name
        logger.info(
            f"[ManyChat] Attempting to set custom field by NAME '{field_name}': {field_value} (type: {type(field_value)}) for subscriber_id: {subscriber_id} via API.")

    logger.debug(f"[ManyChat] Payload: {json.dumps(payload)}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == "success":
                logger.info(
                    f"[ManyChat] Successfully set custom field (ID: {field_id if field_id else 'N/A'}, Name: {field_name if field_name else 'N/A'}) to '{field_value}' for subscriber_id: {subscriber_id}.")
                return True
            else:
                logger.error(
                    f"[ManyChat] API succeeded but returned error status for custom field (ID: {field_id if field_id else 'N/A'}, Name: {field_name if field_name else 'N/A'}) for subscriber_id {subscriber_id}. Response: {response_data}")
                return False
        else:
            logger.error(
                f"[ManyChat] Failed to set custom field (ID: {field_id if field_id else 'N/A'}, Name: {field_name if field_name else 'N/A'}) for subscriber_id {subscriber_id}. Status: {response.status_code}, Response: {response.text[:300]}")
            return False
    except httpx.TimeoutException:
        logger.error(
            f"[ManyChat] Timeout while trying to set custom field (ID: {field_id if field_id else 'N/A'}, Name: {field_name if field_name else 'N/A'}) for {subscriber_id}.")
        return False
    except Exception as e:
        logger.error(
            f"[ManyChat] Exception while trying to set custom field (ID: {field_id if field_id else 'N/A'}, Name: {field_name if field_name else 'N/A'}) for {subscriber_id}: {e}", exc_info=True)
        return False


async def get_username_from_manychat(subscriber_id: str) -> Optional[str]:
    """
    Fetches user info from ManyChat API to get their Instagram username.
    """
    if not subscriber_id:
        logger.warning(
            "[get_username_from_manychat] Subscriber ID is missing.")
        return None

    url = "https://api.manychat.com/fb/subscriber/getInfo"
    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {"subscriber_id": subscriber_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=10)

        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            user_data = data.get("data", {})
            # This is often the IG handle
            ig_username = user_data.get("user_name")
            # Check if it's not a placeholder
            if ig_username and not (ig_username.startswith('user_') and ig_username[5:].isdigit()):
                logger.info(
                    f"Got username '{ig_username}' from ManyChat API for subscriber {subscriber_id}.")
                return ig_username

            # Fallback to 'name' if 'user_name' is a placeholder or missing
            name = user_data.get("name")
            if name and not (name.startswith('user_') and name[5:].isdigit()):
                logger.info(
                    f"Falling back to name '{name}' from ManyChat API for subscriber {subscriber_id}.")
                return name

            logger.warning(
                f"Username from ManyChat API for {subscriber_id} is a placeholder or missing: user_name='{ig_username}', name='{name}'")
            return None
        else:
            logger.error(
                f"ManyChat API returned error for {subscriber_id}: {data.get('message')}")
            return None

    except httpx.RequestError as e:
        logger.error(
            f"Error calling ManyChat getInfo API for {subscriber_id}: {e}")
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error getting username from ManyChat for {subscriber_id}: {e}", exc_info=True)
        return None
