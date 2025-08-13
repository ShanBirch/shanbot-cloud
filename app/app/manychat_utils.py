import requests
import json
import logging
from typing import Dict, Any  # Added Any for field_value flexibility
import os
from datetime import datetime

# Configure logging - assuming a logger might be set up globally in the app
# If not, you might want to configure a specific logger here.
logger = logging.getLogger(__name__)  # Use __name__ for module-specific logger

# Your ManyChat API key - consider moving to environment variables or a central config
MANYCHAT_API_KEY = os.getenv(
    "MANYCHAT_API_KEY", "996573:5b6dc180662de1be343655db562ee918")


def update_manychat_fields(subscriber_id: str, field_updates: Dict[str, Any]) -> bool:
    '''Update custom fields in ManyChat for a subscriber.

    Args:
        subscriber_id: The ID of the ManyChat subscriber.
        field_updates: A dictionary where keys are field names and values are the values to set.
                       Values can be strings, numbers, or booleans.
                       Example: {"o1 Response": "Hello!", "user_score": 100}

    Returns:
        True if the update was successful, False otherwise.
    '''
    if not MANYCHAT_API_KEY or MANYCHAT_API_KEY == "YOUR_MANYCHAT_API_KEY_HERE":  # Added placeholder check
        logger.error(
            "MANYCHAT_API_KEY is not configured. Cannot update fields.")
        return False

    # Filter out None values. ManyChat might handle empty strings, but None can cause issues.
    # Allow boolean False and numeric 0 to pass through.
    filtered_updates = {
        k: v for k, v in field_updates.items() if v is not None
    }
    if not filtered_updates:
        logger.info(
            "No valid field updates to send to ManyChat (all values were None).")
        return True  # Nothing to update, consider it success

    # Prepare the data using field_name
    # ManyChat API expects field_value to be string, number, or boolean.
    # We should ensure values are of these types, or let ManyChat API handle conversion/error.
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
    logger.debug(f"ManyChat API Request Payload: {json.dumps(data, indent=2)}")

    try:
        response = requests.post(
            "https://api.manychat.com/fb/subscriber/setCustomFields",
            headers=headers,
            json=data,
            timeout=15  # Increased timeout slightly
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        if response_data.get("status") == "success":
            logger.info(
                f"Successfully updated ManyChat fields for subscriber {subscriber_id}. Response: {response_data}")
            return True
        else:
            logger.error(
                f"ManyChat API reported failure for subscriber {subscriber_id}. Status: {response_data.get('status')}, Message: {response_data.get('message')}, Details: {response_data.get('details')}")
            return False

    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error updating ManyChat fields for subscriber {subscriber_id}: {http_err} - Response: {http_err.response.text[:500] if http_err.response else 'No response text'}", exc_info=True)
        return False
    except requests.exceptions.RequestException as req_err:
        logger.error(
            f"Request error updating ManyChat fields for subscriber {subscriber_id}: {req_err}", exc_info=True)
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error during ManyChat field update for {subscriber_id}: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    # Example Usage (for testing this module directly)
    logging.basicConfig(
        level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Testing manychat_utils.py...")

    # Replace with a real subscriber_id and field names/values for testing
    test_subscriber_id = "1597203429"  # Example, use a real one from your ManyChat

    # Test 1: Simple text update
    # test_fields_1 = {"o1 Response": f"Test message from manychat_utils.py at {datetime.now().isoformat()}"}
    # For testing from command line, avoid datetime directly in the string that might be misparsed by the tool itself.
    current_time_str = datetime.now().isoformat()
    test_fields_1 = {
        "o1 Response": f"Test message from manychat_utils.py at {current_time_str}"}
    if update_manychat_fields(test_subscriber_id, test_fields_1):
        logger.info(
            f"Test 1 SUCCESS: Updated fields {list(test_fields_1.keys())}")
    else:
        logger.error(f"Test 1 FAILED for fields {list(test_fields_1.keys())}")

    # Test 2: Update multiple fields including a number
    test_fields_2 = {
        "o1 Response": "Another test!",
        # Ensure 'test_numerical_field' exists in your ManyChat
        "test_numerical_field": 12345,
        "test_boolean_field": True    # Ensure 'test_boolean_field' exists
    }
    # Note: ManyChat might require you to create these custom fields first.
    # if update_manychat_fields(test_subscriber_id, test_fields_2):
    #     logger.info(f"Test 2 SUCCESS: Updated fields {list(test_fields_2.keys())}")
    # else:
    #     logger.error(f"Test 2 FAILED for fields {list(test_fields_2.keys())}")

    # Test 3: Update with a None value (should be filtered out)
    test_fields_3 = {"o1 Response": "This should send",
                     "field_with_none": None}
    # if update_manychat_fields(test_subscriber_id, test_fields_3):
    #     logger.info(f"Test 3 SUCCESS: Updated with None value (should have been filtered).")
    # else:
    #     logger.error(f"Test 3 FAILED when sending None value.")

    logger.info("ManyChat utils testing finished.")
