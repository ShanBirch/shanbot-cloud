#!/usr/bin/env python3
"""
Test script for user stage switching functionality
"""

import json
from dashboard_sqlite_utils import load_conversations_from_sqlite, save_metrics_to_sqlite
from user_profiles import update_user_stage
import sys
import os
# Add dashboard_modules to Python path
dashboard_modules_path = os.path.join(
    os.path.dirname(__file__), 'dashboard_modules')
sys.path.insert(0, dashboard_modules_path)


def test_stage_switching():
    """Test the stage switching functionality"""
    print("Testing stage switching functionality...")

    # Load test data from SQLite
    conversations = load_conversations_from_sqlite()

    if not conversations:
        print("No conversations found in SQLite database.")
        return

    # Get first user for testing
    test_username = list(conversations.keys())[0]
    test_user_data = conversations[test_username]
    test_ig_username = test_user_data['metrics'].get(
        'ig_username', test_username)

    print(f"\nTesting with user: {test_ig_username}")
    print(
        f"Current stage: {test_user_data['metrics'].get('journey_stage', {}).get('current_stage', 'Unknown')}")

    # Test switching to Lead
    print("\n1. Testing switch to Lead...")
    success = update_user_stage(test_ig_username, "Lead", test_user_data)
    if success:
        print("✅ Successfully switched to Lead")
    else:
        print("❌ Failed to switch to Lead")

    # Test switching to Trial
    print("\n2. Testing switch to 4 Week Trial...")
    success = update_user_stage(
        test_ig_username, "4 Week Trial", test_user_data)
    if success:
        print("✅ Successfully switched to 4 Week Trial")
    else:
        print("❌ Failed to switch to 4 Week Trial")

    # Test switching to Paying Client
    print("\n3. Testing switch to Paying Client...")
    success = update_user_stage(
        test_ig_username, "Paying Client", test_user_data)
    if success:
        print("✅ Successfully switched to Paying Client")
    else:
        print("❌ Failed to switch to Paying Client")

    # Verify final state
    updated_conversations = load_conversations_from_sqlite()
    updated_user_data = updated_conversations.get(test_username, {})
    final_stage = updated_user_data.get('metrics', {}).get(
        'journey_stage', {}).get('current_stage', 'Unknown')
    is_paying = updated_user_data.get('metrics', {}).get(
        'journey_stage', {}).get('is_paying_client', False)

    print(f"\nFinal verification:")
    print(f"Final stage: {final_stage}")
    print(f"Is paying client: {is_paying}")

    print("\n✅ Stage switching test completed!")


if __name__ == "__main__":
    test_stage_switching()
