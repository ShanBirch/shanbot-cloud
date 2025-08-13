import json
import copy
from datetime import datetime
import os
import shutil


def create_empty_profile_analysis():
    return {
        "posts_analyzed": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "interests": [],
        "lifestyle_indicators": [],
        "recent_activities": [],
        "post_summaries": [],
        "conversation_topics": [],
        "generated_comment": "",
        "profile_bio": {
            "PERSON NAME": "Unknown",
            "INTERESTS": [],
            "LIFESTYLE": "",
            "CONVERSATION STARTERS": [],
            "PERSONALITY TRAITS": []
        }
    }


def normalize_entry(key, value):
    """Normalize a single entry in the analytics data."""
    if not isinstance(value, dict):
        print(f"Warning: Entry {key} is not a dictionary")
        return None, False

    try:
        normalized = copy.deepcopy(value)

        # Ensure metrics exists
        if 'metrics' not in normalized:
            normalized['metrics'] = {}

        metrics = normalized['metrics']

        # Get Instagram username
        ig_username = metrics.get('ig_username')
        if not ig_username:
            ig_username = key
            print(f"Using key as username for {key}")

        # Set username in metrics
        metrics['ig_username'] = ig_username

        # Add client_analysis if missing
        if 'client_analysis' not in metrics:
            metrics['client_analysis'] = create_empty_profile_analysis()

        # Add profile_conversation_topics if missing
        if 'profile_conversation_topics' not in metrics:
            metrics['profile_conversation_topics'] = []

        return ig_username, normalized

    except Exception as e:
        print(f"Error normalizing entry {key}: {str(e)}")
        return None, False


def main():
    # Use exact file path
    analytics_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.json"
    backup_file = analytics_file + ".backup"

    print(f"Starting analytics normalization process...")
    print(f"Analytics file: {analytics_file}")

    try:
        # Create backup first
        print(f"Creating backup at: {backup_file}")
        shutil.copy2(analytics_file, backup_file)
        print("Backup created successfully")

        # Read the current analytics data
        print("Reading analytics file...")
        with open(analytics_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Analytics data must be a dictionary")

        # Extract global metrics and conversations
        global_metrics = data.get('global_metrics', {})
        conversations = data.get('conversations', {})

        # Find all user entries in conversations
        user_data = {}
        for key, value in conversations.items():
            if isinstance(value, dict) and 'metrics' in value:
                user_data[key] = value

        print(
            f"Successfully loaded JSON data with {len(user_data)} user entries")

        normalized_data = {
            'global_metrics': global_metrics,
            'conversations': {}
        }
        processed_count = 0
        error_count = 0
        skipped_count = 0

        print("\nProcessing entries...")
        for key, value in user_data.items():
            try:
                username, normalized = normalize_entry(key, value)
                if username and normalized:
                    normalized_data['conversations'][username] = normalized
                    processed_count += 1
                    if processed_count % 100 == 0:
                        print(f"Processed {processed_count} entries...")
                else:
                    skipped_count += 1
            except Exception as e:
                print(f"Error processing entry {key}: {str(e)}")
                error_count += 1

        print(f"\nSummary:")
        print(f"- Total user entries found: {len(user_data)}")
        print(f"- Successfully processed: {processed_count}")
        print(f"- Skipped: {skipped_count}")
        print(f"- Errors: {error_count}")

        if processed_count == 0:
            raise ValueError("No entries were successfully processed!")

        print("\nSaving normalized data...")
        with open(analytics_file, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, indent=4, ensure_ascii=False)

        print("Analytics data has been normalized successfully!")
        print(f"Backup file is available at: {backup_file}")

    except FileNotFoundError:
        print(f"Error: Could not find analytics file at {analytics_file}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in analytics file: {str(e)}")
    except Exception as e:
        print(f"Error: An unexpected error occurred: {str(e)}")

    print("\nDone!")


if __name__ == "__main__":
    main()
