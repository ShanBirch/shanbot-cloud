import json
from typing import Dict, List, Optional, Tuple, Any, Set
from fastapi import FastAPI, APIRouter, Request, HTTPException
import logging
from datetime import datetime, timedelta, timezone
import re
from pydantic import BaseModel
import os
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("conversation_analytics")

# Update the analytics file path to use the correct location
ANALYTICS_FILE = os.getenv("ANALYTICS_FILE", "analytics_data.json")

# Define conversation gap threshold
CONVERSATION_GAP_THRESHOLD = timedelta(hours=24)

# Define responder categories and thresholds
RESPONDER_CATEGORIES = {
    (0, 0): "No Responder",
    (1, 10): "Low Responder",
    (11, 50): "Medium Responder",
    (51, float('inf')): "High Responder",
}


def _get_responder_category(user_message_count: int) -> str:
    """Determine the responder category based on the number of user messages."""
    if user_message_count <= 0:
        return "No Responder"
    elif user_message_count <= 10:
        return "Low Responder"
    elif user_message_count <= 50:
        return "Medium Responder"
    else:
        return "High Responder"


class ConversationAnalytics:
    def __init__(self):
        # Set the absolute path to the analytics file
        self.analytics_file = ANALYTICS_FILE
        self.conversation_metrics = {}
        self.global_metrics = {
            "total_conversations": 0,
            "total_messages_sent": 0,
            "total_responses": 0,
            "average_response_time": 0,
            "conversation_success_rate": 0,
            "bot_message_stats": {
                "total_messages_sent": 0,
                "total_messages_responded": 0,
                "daily_messages_sent": {},
                "daily_messages_responded": {}
            }
        }
        self.load_analytics()

    def _initialize_global_metrics(self) -> Dict[str, Any]:
        """Returns a dictionary with the default structure for global metrics."""
        return {
            "total_conversations": 0,
            "total_messages": 0,
            "total_user_messages": 0,
            "total_ai_messages": 0,
            "coaching_inquiries": 0,
            "signups": 0,
            "ai_detections": 0,
            "question_stats": {
                "ai_questions_asked": 0,
                "user_responses_to_questions": 0,
                "response_rate": 0.0
            }
        }

    def _initialize_conversation_metrics(self) -> Dict[str, Any]:
        """Returns a dictionary with the default structure for conversation metrics."""
        return {
            "total_messages": 0,
            "user_messages": 0,
            "ai_messages": 0,
            "ai_questions": 0,
            "ai_statements": 0,
            "user_responses_to_ai_question": 0,
            "ai_question_turns_without_user_response": 0,
            "last_message_was_ai_question": False,
            "question_response_rate": 0.0,
            "conversation_start_time": datetime.now().isoformat(),
            "conversation_end_time": None,
            "conversation_duration_seconds": 0,
            "achieved_message_milestones": set(),
            "fitness_topic_initiator": None,
            "offer_mentioned_in_conv": False,
            "link_sent_in_conv": False,
            "coaching_inquiry_count": 0,
            "signup_recorded": False,
            "vegan_topic_mentioned": False,
            "weight_loss_mentioned": False,
            "muscle_gain_mentioned": False,
            "responder_category": "No Responder",
            "conversation_history": [],
            "post_analysis": None,
            "meal_plan_offered": False,
            "meal_plan_accepted": False,
            "meal_plan_type": None,
            "meal_plan_goal": None,
            "meal_plan_customizations": [],
            "meal_plan_feedback": None,
            "ig_username": None
        }

    def analyze_message(self, subscriber_id: str, message_text: str, message_type: str, timestamp: str, ig_username: Optional[str] = None) -> None:
        """Analyze a single message for various metrics, optionally storing the username."""
        now = datetime.now()

        print(f"\n=== Analytics Debug ===")
        print(f"Processing message for subscriber: {subscriber_id}")
        print(f"IG Username: {ig_username}")
        print(f"Message type: {message_type}")
        print(f"Analytics file path: {ANALYTICS_FILE}")

        # Generate a unique conversation ID if subscriber_id not found
        conversation_id = subscriber_id or f"user_{int(time.time())}"

        # Initialize conversation if it doesn't exist
        if conversation_id not in self.conversation_metrics:
            print(f"Creating new conversation entry for {conversation_id}")
            self.conversation_metrics[conversation_id] = self._initialize_conversation_metrics(
            )
            # Store username on initialization if provided
            if ig_username:
                print(f"Setting initial username to: {ig_username}")
                self.conversation_metrics[conversation_id]["ig_username"] = ig_username
            self.global_metrics["total_conversations"] += 1
            logger.info(
                f"Initialized new conversation for subscriber {conversation_id} (User: {ig_username or 'N/A'})")
        elif ig_username and not self.conversation_metrics[conversation_id].get("ig_username"):
            # Update username if we didn't have it before
            print(
                f"Updating username for existing subscriber to: {ig_username}")
            self.conversation_metrics[conversation_id]["ig_username"] = ig_username
            logger.info(
                f"Updated username for existing subscriber {conversation_id} to {ig_username}")

        # Get conversation specific metrics
        conv_metrics = self.conversation_metrics[conversation_id]
        current_timestamp_dt = datetime.fromisoformat(
            timestamp).replace(tzinfo=timezone.utc)

        # Append message to conversation history
        message_data = {
            "timestamp": current_timestamp_dt.isoformat(),
            "type": message_type,
            "text": message_text
        }
        conv_metrics.setdefault("conversation_history",
                                []).append(message_data)
        print(f"Added message to conversation history")

        try:
            print("Attempting to export analytics...")
            self.export_analytics(ANALYTICS_FILE)
            print("Successfully exported analytics")
        except Exception as e:
            print(f"Error exporting analytics: {e}")
            import traceback
            traceback.print_exc()

        print("=== End Analytics Debug ===\n")

        # Update timestamps and duration
        if not conv_metrics.get("first_message_timestamp"):
            conv_metrics["first_message_timestamp"] = current_timestamp_dt.isoformat()
        conv_metrics["last_message_timestamp"] = current_timestamp_dt.isoformat()

        # Calculate duration string
        try:
            first_dt = datetime.fromisoformat(
                conv_metrics["first_message_timestamp"]).replace(tzinfo=timezone.utc)
            last_dt = current_timestamp_dt
            duration = last_dt - first_dt
            days = duration.days
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60

            if days > 0:
                duration_str = f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = f"{minutes}m"

            conv_metrics["conversation_duration_str"] = duration_str
        except (ValueError, TypeError, KeyError):
            conv_metrics["conversation_duration_str"] = "N/A"

        # --- Conversation Count Logic --- START ---
        last_seen_str = conv_metrics.get("last_seen_timestamp")
        conversation_count = conv_metrics.get("conversation_count", 0)

        if last_seen_str:
            try:
                last_seen_dt = datetime.fromisoformat(
                    last_seen_str).replace(tzinfo=timezone.utc)
                time_diff = current_timestamp_dt - last_seen_dt
                if time_diff >= CONVERSATION_GAP_THRESHOLD:
                    conversation_count += 1
            except (ValueError, TypeError):
                logger.warning(
                    f"SubID {conversation_id}: Could not parse last_seen_timestamp '{last_seen_str}'. Resetting conversation count logic.")
                conversation_count = 1
        else:
            conversation_count = 1

        conv_metrics["conversation_count"] = conversation_count
        conv_metrics["last_seen_timestamp"] = current_timestamp_dt.isoformat()

        # Update username if provided
        if ig_username:
            conv_metrics["ig_username"] = ig_username

        # Update message counts
        self.global_metrics["total_messages"] += 1
        conv_metrics["total_messages"] += 1

        # Track who sent the message
        if message_type == "ai":
            self.global_metrics["total_ai_messages"] += 1
            conv_metrics["ai_messages"] += 1
        else:
            self.global_metrics["total_user_messages"] += 1
            conv_metrics["user_messages"] += 1

        # Basic message analysis
        contains_question = "?" in message_text

        # --- Advanced Logic ---

        # 1. Track Question Response Rate
        if message_type != "ai" and conv_metrics.get("last_message_was_ai_question", False):
            try:
                conv_metrics["user_responses_to_ai_question"] = conv_metrics.get(
                    "user_responses_to_ai_question", 0) + 1
                self.global_metrics["question_stats"]["user_responses_to_questions"] += 1
                conv_metrics["last_message_was_ai_question"] = False
            except Exception as e:
                logger.error(
                    f"Error incrementing user_responses_to_ai_question: {e}", exc_info=True)
                # Initialize if missing
                conv_metrics["user_responses_to_ai_question"] = 1
                conv_metrics["last_message_was_ai_question"] = False

        elif message_type == "ai" and contains_question:
            conv_metrics["ai_questions"] += 1
            self.global_metrics["question_stats"]["ai_questions_asked"] += 1
            conv_metrics["last_message_was_ai_question"] = True

        elif message_type == "ai" and not contains_question:
            conv_metrics["ai_statements"] += 1
            conv_metrics["last_message_was_ai_question"] = False

        elif message_type != "ai":
            conv_metrics["last_message_was_ai_question"] = False

        # 2. Track Message Milestones
        milestones_to_check = {5, 10, 20, 50, 100}
        current_milestones = conv_metrics.get(
            "achieved_message_milestones", set())
        for ms in milestones_to_check:
            if conv_metrics.get("total_messages", 0) >= ms and ms not in current_milestones:
                current_milestones.add(ms)
                conv_metrics["achieved_message_milestones"] = current_milestones
                logger.info(
                    f"Subscriber {conversation_id} reached {ms} message milestone.")

        # 3. Track Fitness Topic Initiation & Specific Topics
        fitness_keywords = ["fitness", "workout", "exercise", "gym", "training",
                            "diet", "nutrition", "macros", "calories", "protein", "carbs", "fat"]
        vegan_keywords = ["vegan", "vegetarian", "plant-based", "veggo"]
        weight_loss_keywords = ["lose weight",
                                "weight loss", "fat loss", "shred", "cut"]
        muscle_gain_keywords = [
            "gain muscle", "build muscle", "bulk", "muscle growth", "strength"]

        lower_message = message_text.lower()
        mentioned_fitness = any(
            keyword in lower_message for keyword in fitness_keywords)
        conv_metrics["vegan_topic_mentioned"] = conv_metrics.get(
            "vegan_topic_mentioned", False) or any(keyword in lower_message for keyword in vegan_keywords)
        conv_metrics["weight_loss_mentioned"] = conv_metrics.get("weight_loss_mentioned", False) or any(
            keyword in lower_message for keyword in weight_loss_keywords)
        conv_metrics["muscle_gain_mentioned"] = conv_metrics.get("muscle_gain_mentioned", False) or any(
            keyword in lower_message for keyword in muscle_gain_keywords)

        if mentioned_fitness and conv_metrics.get("fitness_topic_initiator") is None:
            conv_metrics["fitness_topic_initiator"] = "ai" if message_type == "ai" else "user"
            logger.info(
                f"Fitness topic initiated by {'AI' if message_type == 'ai' else 'User'} for subscriber {conversation_id}")

        # 4. Track Coaching Inquiries & Signups (with refined patterns)
        coaching_inquiry_patterns = [
            # Explicit questions about cost/price
            r'(?i)\b(how much|what is|what\'s)\b.*\b(coach|cost|price)\b',
            # Direct statement of interest
            r'(?i)interested in.*(coach|program|training)',
            # Requesting info
            r'(?i)(tell me|details|info).*(about|on).*(coach|program|training)',
            r'(?i)sign me up',  # Direct call to action
            r'(?i)want to join'  # Direct statement of desire
        ]
        link_patterns = [r"cocospersonaltraining\.com/online", r"2WEEKS"]
        signup_patterns = [
            r"(?i)signed up", r"(?i)just joined", r"(?i)completed.*signup"]

        # Only count as inquiry if it's a user message
        if message_type != "ai" and any(re.search(pattern, message_text) for pattern in coaching_inquiry_patterns):
            conv_metrics["coaching_inquiry_count"] = conv_metrics.get(
                "coaching_inquiry_count", 0) + 1
            self.global_metrics["coaching_inquiries"] += 1
            logger.info(
                f"Coaching inquiry detected for subscriber {conversation_id}")

        if any(re.search(pattern, message_text) for pattern in link_patterns):
            conv_metrics["offer_mentioned_in_conv"] = True
            if "cocospersonaltraining.com/online" in message_text:
                conv_metrics["link_sent_in_conv"] = True
                logger.info(
                    f"Signup link detected for subscriber {conversation_id}")

        if any(re.search(pattern, message_text) for pattern in signup_patterns) and message_type != "ai":
            if not conv_metrics.get("signup_recorded", False):
                conv_metrics["signup_recorded"] = True
                self.global_metrics["signups"] += 1
                logger.info(
                    f"Signup confirmed for subscriber {conversation_id}")

        # 5. Track AI Detections
        ai_detection_patterns = [
            r'(?i)are.*you.*bot', r'(?i)is.*this.*ai', r'(?i)automated.*response']
        if any(re.search(pattern, message_text) for pattern in ai_detection_patterns) and message_type != "ai":
            self.global_metrics["ai_detections"] += 1
            conv_metrics["ai_detections"] = conv_metrics.get(
                "ai_detections", 0) + 1
            logger.info(
                f"AI detection detected for subscriber {conversation_id}")

    def _analyze_message_content(self, message: str, is_ai_response: bool) -> Dict:
        """Analyze message content for various patterns."""

        metrics = {
            "contains_question": bool(re.search(r'\?', message)),
            "word_count": len(message.split()),
            "coaching_inquiry": False,
            "ai_detection": False,
            "sentiment": self._analyze_sentiment(message)
        }

        # Check for coaching inquiries
        coaching_patterns = [
            r'(?i)how much.*coach',
            r'(?i)sign.*up',
            r'(?i)join.*program',
            r'(?i)cost.*training',
            r'(?i)price.*coach',
            r'(?i)interested.*coaching'
        ]
        metrics["coaching_inquiry"] = any(
            re.search(pattern, message) for pattern in coaching_patterns)

        # Check for AI detection
        ai_detection_patterns = [
            r'(?i)are.*you.*bot',
            r'(?i)is.*this.*ai',
            r'(?i)automated.*response',
            r'(?i)talking.*to.*computer',
            r'(?i)chatbot',
            r'(?i)not.*real.*person',
            r'(?i)sound.*like.*ai'
        ]
        metrics["ai_detection"] = any(
            re.search(pattern, message) for pattern in ai_detection_patterns)

        return metrics

    def _analyze_sentiment(self, message: str) -> str:
        """Basic sentiment analysis."""
        positive_words = {'great', 'good', 'awesome', 'love', 'happy',
                          'thanks', 'excited', 'perfect', 'yes', 'cool', 'nice'}
        negative_words = {'bad', 'hate', 'awful', 'terrible',
                          'angry', 'upset', 'disappointed', 'no', 'nope', 'cant'}

        words = set(message.lower().split())
        pos_count = len(words.intersection(positive_words))
        neg_count = len(words.intersection(negative_words))

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    def get_conversation_metrics(self, subscriber_id: str) -> Optional[Dict[str, Any]]:
        """Get calculated metrics for a specific conversation."""
        metrics = self.conversation_metrics.get(subscriber_id)
        if metrics:
            # Calculate duration if conversation has ended
            if metrics.get("conversation_end_time"):
                try:
                    start = datetime.fromisoformat(
                        metrics.get("conversation_start_time", datetime.now().isoformat()))
                    end = datetime.fromisoformat(
                        metrics["conversation_end_time"])
                    metrics["conversation_duration_seconds"] = (
                        end - start).total_seconds()
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Could not parse timestamps for duration calculation for {subscriber_id}: {e}")
                    metrics["conversation_duration_seconds"] = 0
            else:
                # Calculate ongoing duration if needed
                try:
                    start = datetime.fromisoformat(
                        metrics.get("conversation_start_time", datetime.now().isoformat()))
                    metrics["conversation_duration_seconds"] = (
                        datetime.now() - start).total_seconds()
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Could not parse start timestamp for ongoing duration for {subscriber_id}: {e}")
                    metrics["conversation_duration_seconds"] = 0

            # Calculate final response rate
            total_ai_questions = metrics.get("ai_questions", 0)
            user_responses = metrics.get("user_responses_to_ai_question", 0)
            if total_ai_questions > 0:
                metrics["question_response_rate"] = user_responses / \
                    total_ai_questions
            else:
                metrics["question_response_rate"] = 0.0

            # Calculate responder category
            metrics["responder_category"] = _get_responder_category(
                metrics.get("user_messages", 0))

            # Convert set to list for JSON compatibility before returning copy
            metrics_copy = metrics.copy()
            metrics_copy["achieved_message_milestones"] = sorted(
                list(metrics_copy.get("achieved_message_milestones", set())))
            return metrics_copy
        return None

    def get_global_calculated_metrics(self) -> Dict[str, Any]:
        """Get global metrics including calculated rates."""
        # Make a copy to avoid modifying the original
        global_metrics_copy = self.global_metrics.copy()
        global_metrics_copy["question_stats"] = self.global_metrics["question_stats"].copy(
        )

        # Calculate overall question response rate
        total_questions = global_metrics_copy["question_stats"]["ai_questions_asked"]
        total_responses = global_metrics_copy["question_stats"]["user_responses_to_questions"]
        if total_questions > 0:
            global_metrics_copy["question_stats"]["response_rate"] = total_responses / total_questions
        else:
            global_metrics_copy["question_stats"]["response_rate"] = 0.0

        return global_metrics_copy

    def get_engagement_analysis(self, subscriber_id: str) -> Dict:
        """Analyze engagement patterns for a conversation."""
        if subscriber_id not in self.conversations:
            return {}

        conv = self.conversations[subscriber_id]
        metrics = conv["metrics"]

        # Calculate response rates
        ai_messages = sum(1 for m in conv["messages"] if m["is_ai"])
        user_messages = sum(1 for m in conv["messages"] if not m["is_ai"])

        # Calculate question response rate
        questions_asked = metrics["ai_questions"]
        responses_after_questions = metrics["user_responses_to_questions"]

        question_response_rate = responses_after_questions / \
            questions_asked if questions_asked > 0 else 0

        return {
            "total_messages": metrics["total_messages"],
            "ai_messages": ai_messages,
            "user_messages": user_messages,
            "questions_asked": questions_asked,
            "user_responses_to_questions": responses_after_questions,
            "user_responses_no_question": metrics["user_responses_no_question"],
            "question_response_rate": question_response_rate,
            "avg_response_time": metrics["avg_response_time"],
            "coaching_inquiries": metrics["coaching_inquiries"],
            "ai_detections": metrics["ai_detections"]
        }

    def export_analytics(self, file_path="analytics_data.json"):
        """Exports the current analytics data to a JSON file using a safe write method that preserves existing data."""
        logger.info(f"Attempting to export analytics to: {file_path}")
        abs_file_path = os.path.abspath(file_path)
        temp_file_path = abs_file_path + ".tmp"

        try:
            # IMPORTANT: Always reload the file first to get any changes made by other processes
            latest_file_data = None
            if os.path.exists(abs_file_path):
                try:
                    with open(abs_file_path, 'r') as current_file:
                        latest_file_data = json.load(current_file)
                    logger.info(
                        f"Successfully loaded existing analytics file for merge.")
                except Exception as e:
                    logger.error(
                        f"Error reading current analytics file for merge: {e}")
                    # Continue with our data if we can't read the file

            # Prepare our current in-memory data
            data_to_export = {
                "global_metrics": self.global_metrics,
                "conversations": {
                    sub_id: {
                        # Build the 'metrics' dict: iterate conv items, convert sets, exclude metadata
                        "metrics": {
                            k: list(v) if isinstance(v, set) else v
                            for k, v in conv.items()
                            if k != 'metadata'  # Ensure metadata isn't duplicated inside metrics
                        },
                        # Get metadata if it exists in the conversation dict, otherwise empty dict
                        "metadata": conv.get('metadata', {})
                    }
                    # Iterate through the main conversation_metrics dictionary
                    for sub_id, conv in self.conversation_metrics.items()
                }
            }

            # If we have latest file data, merge our current data with it
            if latest_file_data:
                # Merge global metrics (simple addition for numeric values)
                for key, value in latest_file_data.get("global_metrics", {}).items():
                    if key not in data_to_export["global_metrics"]:
                        data_to_export["global_metrics"][key] = value
                    elif isinstance(value, dict) and isinstance(data_to_export["global_metrics"][key], dict):
                        # Handle nested dictionaries
                        for nested_key, nested_value in value.items():
                            if nested_key not in data_to_export["global_metrics"][key]:
                                data_to_export["global_metrics"][key][nested_key] = nested_value
                            # For bot_message_stats, make special handling
                            elif key == "bot_message_stats":
                                if nested_key == "daily_messages_sent" or nested_key == "daily_messages_responded":
                                    # Merge the daily stats dictionaries
                                    data_to_export["global_metrics"][key][nested_key].update(
                                        nested_value)
                                else:
                                    # For numeric values like total counts, take the max
                                    data_to_export["global_metrics"][key][nested_key] = max(
                                        data_to_export["global_metrics"][key][nested_key], nested_value)
                    elif isinstance(value, (int, float)) and isinstance(data_to_export["global_metrics"][key], (int, float)):
                        # For counters, take the higher value to avoid losing counts
                        data_to_export["global_metrics"][key] = max(
                            data_to_export["global_metrics"][key], value)

                # Merge conversations (preserve any that we don't have in memory)
                for sub_id, conv_data in latest_file_data.get("conversations", {}).items():
                    if sub_id not in data_to_export["conversations"]:
                        # This conversation exists in file but not in memory, keep it
                        data_to_export["conversations"][sub_id] = conv_data
                    else:
                        # Merge conversation metrics where needed
                        if "conversation_history" in conv_data.get("metrics", {}):
                            file_history = conv_data["metrics"]["conversation_history"]
                            memory_history = data_to_export["conversations"][sub_id]["metrics"].get(
                                "conversation_history", [])

                            # Only merge if histories differ
                            if len(file_history) != len(memory_history):
                                # Create a simple hash of messages to avoid duplicates
                                memory_msgs = {f"{msg.get('timestamp', '')}:{msg.get('text', '')[:20]}"
                                               for msg in memory_history}

                                # Add any messages from file that aren't in memory
                                for msg in file_history:
                                    msg_key = f"{msg.get('timestamp', '')}:{msg.get('text', '')[:20]}"
                                    if msg_key not in memory_msgs:
                                        memory_history.append(msg)

                                # Update the merged history
                                data_to_export["conversations"][sub_id]["metrics"]["conversation_history"] = memory_history

                logger.info(
                    f"Merged data from existing file with current memory state.")

            # Write the merged data to file
            os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
            with open(temp_file_path, 'w') as f:
                json.dump(data_to_export, f, indent=2)
                f.flush()  # Ensure Python buffers are flushed
                os.fsync(f.fileno())  # Ensure OS buffers are flushed

            os.replace(temp_file_path, abs_file_path)
            logger.info(f"Analytics exported successfully to {abs_file_path}.")
        except IOError as e:
            logger.error(f"Error writing analytics file: {e}")
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError as remove_err:
                    logger.error(
                        f"Error removing temporary file {temp_file_path}: {remove_err}")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during analytics export: {e}")
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError as remove_err:
                    logger.error(
                        f"Error removing temporary file {temp_file_path}: {remove_err}")

    def load_analytics(self) -> None:
        """Loads analytics data from the JSON file if it exists."""
        load_path = os.path.abspath(ANALYTICS_FILE)
        logger.info(f"Attempting to load analytics from: {load_path}")

        if not os.path.exists(load_path):
            logger.warning(
                f"Analytics file {load_path} not found. Starting fresh.")
            self.global_metrics = self._initialize_global_metrics()
            self.conversation_metrics = {}
            return

        try:
            with open(load_path, 'r') as f:
                loaded_data = json.load(f)

            # Load global metrics
            default_global = self._initialize_global_metrics()
            loaded_global = loaded_data.get("global_metrics", {})
            self.global_metrics = {**default_global, **loaded_global}

            # Load conversation metrics from the nested structure
            # This is dict {sub_id: {"metrics":..., "metadata":...}}
            loaded_conv_data = loaded_data.get("conversations", {})
            self.conversation_metrics = {}
            logger.info(
                f"Processing {len(loaded_conv_data)} conversations from file...")

            # conv_data is {"metrics":..., "metadata":...}
            for sub_id, conv_data in loaded_conv_data.items():
                default_conv = self._initialize_conversation_metrics()
                # Get metrics dict safely
                metrics_dict = conv_data.get("metrics", {})
                metadata_dict = conv_data.get("metadata", {})

                # Ensure conversation_count and last_seen_timestamp are loaded, defaulting if missing
                if "conversation_count" not in metrics_dict:
                    metrics_dict["conversation_count"] = 0
                if "last_seen_timestamp" not in metrics_dict:
                    metrics_dict["last_seen_timestamp"] = None

                # Ensure conversation_history is loaded as a list
                if "conversation_history" not in metrics_dict:
                    metrics_dict["conversation_history"] = []

                # Convert loaded milestones list (from metrics_dict) back to set
                milestones_list = metrics_dict.get(
                    "achieved_message_milestones", [])
                # Ensure metrics_dict itself is updated if milestones key exists
                if "achieved_message_milestones" in metrics_dict:
                    metrics_dict["achieved_message_milestones"] = set(
                        milestones_list)

                # Merge: start with default, overwrite with loaded metrics, add metadata key
                self.conversation_metrics[sub_id] = {
                    **default_conv,
                    **metrics_dict,  # Spread the actual metrics
                    "metadata": metadata_dict  # Add the metadata separately
                }

                # Ensure conversation_history is a list after merge
                if not isinstance(self.conversation_metrics[sub_id].get("conversation_history"), list):
                    logger.warning(
                        f"Conversation history for {sub_id} was not a list, resetting to empty list.")
                    self.conversation_metrics[sub_id]["conversation_history"] = [
                    ]

                # Recalculate category on load
                self.conversation_metrics[sub_id]["responder_category"] = _get_responder_category(
                    self.conversation_metrics[sub_id].get("user_messages", 0)
                )

            logger.info(f"Analytics loaded successfully from {load_path}.")
            # logger.info(f"Loaded global metrics (raw): {self.global_metrics}") # Optional: reduce log verbosity
            logger.info(
                f"Loaded {len(self.conversation_metrics)} conversations into memory.")

        except FileNotFoundError:
            logger.warning(
                f"Analytics file {load_path} not found during load attempt (FileNotFoundError).")
            self.global_metrics = self._initialize_global_metrics()
            self.conversation_metrics = {}
        except json.JSONDecodeError as e:
            logger.error(
                f"Error decoding JSON from analytics file {load_path}: {e}. Starting fresh.", exc_info=True)
            self.global_metrics = self._initialize_global_metrics()
            self.conversation_metrics = {}
        except IOError as e:
            logger.error(
                f"IOError reading analytics file {load_path}: {e}. Starting fresh.", exc_info=True)
            self.global_metrics = self._initialize_global_metrics()
            self.conversation_metrics = {}
        except Exception as e:
            logger.error(
                f"Unexpected error loading analytics from {load_path}: {e}. Starting fresh.", exc_info=True)
            self.global_metrics = self._initialize_global_metrics()
            self.conversation_metrics = {}


# Create router for analytics endpoints

# --- Instantiate Analytics Singleton HERE ---
analytics = ConversationAnalytics()
logger.info("ConversationAnalytics instance created.")

router = APIRouter()
# --- END Instantiate Analytics Singleton ---


@router.get("/analytics/global")
async def get_global_metrics_endpoint():
    """Get global conversation metrics, including calculated rates."""
    return analytics.get_global_calculated_metrics()


@router.get("/analytics/conversation/{subscriber_id}")
async def get_conversation_metrics_endpoint(subscriber_id: str):
    """Get calculated metrics for a specific conversation."""
    metrics = analytics.get_conversation_metrics(subscriber_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return metrics


@router.get("/analytics/engagement/{subscriber_id}")
async def get_engagement_analysis(subscriber_id: str):
    """Get detailed engagement analysis for a conversation."""
    analysis = analytics.get_engagement_analysis(subscriber_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return analysis


@router.post("/analytics/export")
async def export_analytics_endpoint():
    """Export all analytics data to a JSON file."""
    try:
        analytics.export_analytics()
        return {"message": f"Analytics exported to {ANALYTICS_FILE}"}
    except Exception as e:
        logger.error(
            f"Error during analytics export endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Decorator to add analytics tracking to webhook endpoints


def track_conversation_analytics(endpoint_func):
    async def wrapper(request: Request, *args, **kwargs):
        # Process the original request
        response = await endpoint_func(request, *args, **kwargs)

        try:
            # Extract data from request for analytics
            data = await request.json()
            subscriber_id = data.get("id", "")
            custom_fields = data.get("custom_fields", {})
            ig_username = None

            # Try to extract Instagram username if available
            try:
                ig_username = custom_fields.get("INSTAGRAM_USERNAME") or custom_fields.get(
                    "Instagram Username") or None
            except Exception:
                pass

            # Get conversation from fields
            conversation_value = None
            try:
                conversation_value = custom_fields.get("CONVERSATION", "")
            except Exception:
                logger.warning("Could not extract CONVERSATION field")

            # Analyze the last user message if present
            if conversation_value:
                try:
                    messages = conversation_value.split('\n')
                    if len(messages) > 0:
                        last_message = messages[-1]
                        # Check if message is from user (not AI)
                        if not last_message.startswith("Shannon:"):
                            analytics.analyze_message(
                                subscriber_id, last_message, "user", datetime.now().isoformat(), ig_username)
                except Exception as e:
                    logger.error(
                        f"Error analyzing user message: {str(e)}", exc_info=True)

            # If response contains AI message, analyze it
            try:
                if isinstance(response, dict) and "content" in response:
                    content = response["content"]
                    if isinstance(content, dict) and "messages" in content:
                        ai_message = content["messages"][0] if content["messages"] else ""
                        analytics.analyze_message(
                            subscriber_id, ai_message, "ai", datetime.now().isoformat(), ig_username)
            except Exception as e:
                logger.error(
                    f"Error analyzing AI message: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error tracking analytics: {str(e)}", exc_info=True)
            # Continue with response even if analytics tracking fails

        return response

    return wrapper


# Instructions for integration:
"""
To integrate this analytics module with manychat_webhook_fullprompt.py:

1. Add these imports to the top of manychat_webhook_fullprompt.py:
   from app.conversation_analytics_integration import analytics, router as analytics_router, track_conversation_analytics

2. Include the analytics router in your FastAPI app:
   app.include_router(analytics_router)

3. Decorate your webhook endpoints with the analytics tracker:
   @app.post("/webhook/manychat")
   @track_conversation_analytics
   async def manychat_webhook(request: Request):
       # existing code

   @app.post("/webhook/onboarding")
   @track_conversation_analytics
   async def onboarding_webhook(request: Request):
       # existing code

   @app.post("/webhook/checkin")
   @track_conversation_analytics
   async def checkin_webhook(request: Request):
       # existing code

   @app.post("/webhook/member_general_chat")
   @track_conversation_analytics
   async def member_general_chat_webhook(request: Request):
       # existing code

4. Manually track AI responses if not captured by decorator:
   # After generating an AI response:
   analytics.analyze_message(subscriber_id, ai_response_text, "ai", datetime.now().isoformat())

5. Access analytics via the new endpoints:
   - GET /analytics/global
   - GET /analytics/conversation/{subscriber_id}
   - GET /analytics/engagement/{subscriber_id}
   - POST /analytics/export
"""
