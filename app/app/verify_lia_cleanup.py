import sqlite3
import json


def verify_lia_cleanup():
    """Verify the cleanup of Lia_romy's conversation"""

    try:
        conn = sqlite3.connect('app/analytics_data_good.sqlite')
        cursor = conn.cursor()

        # Get current user data
        cursor.execute("SELECT * FROM users WHERE ig_username = 'blissedlia'")
        user_data = cursor.fetchone()

        if not user_data:
            print("User blissedlia not found in database")
            return

        # Parse the metrics_json to get conversation history
        metrics_json = user_data[2]  # metrics_json column
        if not metrics_json:
            print("No metrics_json found for user")
            return

        metrics = json.loads(metrics_json)
        conversation_history = metrics.get('conversation_history', [])

        print(f"Current conversation length: {len(conversation_history)}")
        print(f"User messages: {metrics.get('user_messages', 0)}")
        print(f"AI messages: {metrics.get('ai_messages', 0)}")
        print(f"Total messages: {metrics.get('total_messages', 0)}")

        print("\nLast 10 messages in conversation:")
        for i, msg in enumerate(conversation_history[-10:], 1):
            msg_type = msg.get('type', 'unknown')
            msg_text = msg.get('text', '')[:100]
            timestamp = msg.get('timestamp', '')
            print(f"{i}. [{msg_type}] {timestamp}: {msg_text}...")

        # Check for the expected last message
        print(
            "\nLooking for the expected last message: 'I'll have to make my own seed mix'")
        found_seed_mix = False
        for msg in conversation_history:
            if "seed mix" in msg.get('text', '').lower():
                print(f"Found seed mix message: {msg.get('text', '')}")
                found_seed_mix = True
                break

        if not found_seed_mix:
            print("Seed mix message not found in conversation")

        # Check for any remaining unwanted messages
        unwanted_patterns = [
            "Hey! Awesome, let's get you started",
            "I definitely think so 100% plus support",
            "Omg, it exists! That's awesome you found us",
            "Oh no, I'm sorry you feel that way",
            "I hear you. That's a common misconception",
            "I understand. That's a really common concern"
        ]

        print("\nChecking for any remaining unwanted messages:")
        found_unwanted = False
        for i, msg in enumerate(conversation_history):
            if msg.get('type') == 'ai':
                text = msg.get('text', '')
                for pattern in unwanted_patterns:
                    if pattern in text:
                        print(
                            f"Found unwanted message at index {i}: {text[:100]}...")
                        found_unwanted = True

        if not found_unwanted:
            print("No unwanted messages found - cleanup successful!")

        conn.close()

    except Exception as e:
        print(f"Error verifying cleanup: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    verify_lia_cleanup()
