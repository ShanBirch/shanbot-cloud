import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Set up logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_safe_value(data: Dict[str, Any], key: str, default: str = "MISSING") -> Any:
    """Safely get a value from a dictionary, returning a default if not found."""
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


def process_analytics_data(input_file: str, output_dir: str):
    """Process analytics data and create individual user files."""

    logger.info(f"Starting to process analytics data from: {input_file}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Created/verified output directory: {output_dir}")

    try:
        logger.info("Reading analytics data file...")
        with open(input_file, 'r', encoding='utf-8') as f:
            analytics_data = json.load(f)
        logger.info(f"Successfully loaded analytics data")
    except FileNotFoundError:
        logger.error(f"Analytics file not found at: {input_file}")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from analytics file: {e}")
        return
    except Exception as e:
        logger.error(f"Unexpected error reading analytics file: {e}")
        return

    # Track statistics
    stats = {
        "total_entries": 0,
        "processed_users": 0,
        "entries_with_missing_data": 0,
        "missing_field_types": {}
    }

    # Process each entry
    user_data = {}

    # Get global metrics
    global_metrics = analytics_data.get("global_metrics", {})
    logger.info(
        f"Found global metrics with {global_metrics.get('total_conversations', 0)} conversations")

    # Get conversations
    conversations = analytics_data.get("conversations", {})
    if not conversations:
        logger.warning("No conversations found in analytics data")
        return

    logger.info(f"Processing {len(conversations)} conversations...")

    for conv_id, conversation in conversations.items():
        stats["total_entries"] += 1

        # Get subscriber_id from the conversation ID or data
        subscriber_id = conversation.get("subscriber_id", conv_id)
        if not subscriber_id:
            subscriber_id = f"unknown_user_{stats['total_entries']}"

        # Initialize user data if not exists
        if subscriber_id not in user_data:
            user_data[subscriber_id] = {
                "subscriber_id": subscriber_id,
                "conversations": [],
                "metrics": {
                    "total_messages": 0,
                    "ai_questions": 0,
                    "user_responses": 0,
                    "coaching_inquiries": 0,
                    "ai_detections": 0,
                    "missing_fields": []
                }
            }

        # Process messages in conversation
        messages = conversation.get("messages", [])
        if isinstance(messages, dict):
            # Convert dict to list if necessary
            messages = list(messages.values())

        for message in messages:
            if not isinstance(message, dict):
                continue

            msg_data = {
                "timestamp": get_safe_value(message, "timestamp", datetime.now().isoformat()),
                "message": get_safe_value(message, "text", "NO_MESSAGE"),
                "is_ai": get_safe_value(message, "is_ai", "UNKNOWN"),
                "sentiment": get_safe_value(message, "sentiment", "UNKNOWN")
            }

            # Track missing fields
            missing_fields = [k for k, v in msg_data.items(
            ) if v in ["MISSING", "NO_MESSAGE", "UNKNOWN"]]
            if missing_fields:
                user_data[subscriber_id]["metrics"]["missing_fields"].extend(
                    missing_fields)
                stats["entries_with_missing_data"] += 1
                # Track types of missing fields
                for field in missing_fields:
                    stats["missing_field_types"][field] = stats["missing_field_types"].get(
                        field, 0) + 1

            # Update metrics
            user_data[subscriber_id]["metrics"]["total_messages"] += 1
            if msg_data["is_ai"] == True:
                if "?" in msg_data["message"]:
                    user_data[subscriber_id]["metrics"]["ai_questions"] += 1
            elif msg_data["is_ai"] == False:
                user_data[subscriber_id]["metrics"]["user_responses"] += 1

            # Add message to conversation data
            user_data[subscriber_id]["conversations"].append(msg_data)

    # Write individual user files
    logger.info(f"Writing {len(user_data)} user files...")
    for subscriber_id, data in user_data.items():
        output_file = os.path.join(output_dir, f"user_{subscriber_id}.json")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Created user file: {output_file}")
        except Exception as e:
            logger.error(f"Error writing user file {output_file}: {e}")

    stats["processed_users"] = len(user_data)

    # Log detailed statistics
    logger.info(f"""
Analytics Processing Complete:
- Total entries processed: {stats['total_entries']}
- Users processed: {stats['processed_users']}
- Entries with missing data: {stats['entries_with_missing_data']}
- Missing field types:
  {json.dumps(stats['missing_field_types'], indent=2)}
- Output directory: {output_dir}
""")


if __name__ == "__main__":
    # Use the exact path provided
    input_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.json"
    output_dir = os.path.join(os.path.dirname(input_file), "by_user")

    logger.info(f"Starting script with:")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Output directory: {output_dir}")

    process_analytics_data(input_file, output_dir)
