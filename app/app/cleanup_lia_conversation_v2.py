import sqlite3
import json
import re


def cleanup_lia_conversation_v2():
    """Clean up Lia_romy's conversation by removing unwanted AI messages with better pattern matching"""

    # Unwanted message patterns (more flexible matching)
    unwanted_patterns = [
        r"Hey! Awesome, let's get you started.*what's the number one goal",
        r"I definitely think so 100% plus support and guidance from me.*step your fitness up",
        r"Omg, it exists!.*awesome you found us.*excitement.*apprehension.*high-sugar, low-protein traps.*biggest fear.*challenge like this",
        r"Oh no, I'm sorry you feel that way.*challenge can seem daunting.*apprehension.*achievable and fun.*restrictive or overwhelming.*biggest thing holding you back",
        r"I hear you.*common misconception.*plant-based eating.*total weight loss.*body composition.*body fat percentages.*unbalanced macros.*pbf distributed all over the body",
        r"I understand.*really common concern.*overall weight loss.*body composition.*visceral fat.*targeted training.*macro-balancing.*typical daily food choices"
    ]

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

        print(f"Original conversation length: {len(conversation_history)}")

        # Find and remove unwanted messages with regex patterns
        messages_to_remove = []
        for i, message in enumerate(conversation_history):
            if message.get('type') == 'ai':
                text = message.get('text', '')
                for pattern in unwanted_patterns:
                    if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                        messages_to_remove.append(i)
                        print(
                            f"Found unwanted message at index {i}: {text[:100]}...")
                        break

        # Remove messages in reverse order to maintain indices
        for index in reversed(messages_to_remove):
            removed_message = conversation_history.pop(index)
            print(
                f"Removed message: {removed_message.get('text', '')[:100]}...")

        print(f"Removed {len(messages_to_remove)} unwanted messages")
        print(f"New conversation length: {len(conversation_history)}")

        # Update message counts
        ai_messages = sum(
            1 for msg in conversation_history if msg.get('type') == 'ai')
        user_messages = sum(
            1 for msg in conversation_history if msg.get('type') == 'user')

        # Update the last message timestamp to the actual last message
        if conversation_history:
            last_message = conversation_history[-1]
            last_timestamp = last_message.get('timestamp')
        else:
            last_timestamp = None

        # Update metrics
        metrics['conversation_history'] = conversation_history
        metrics['user_messages'] = user_messages
        metrics['ai_messages'] = ai_messages
        metrics['total_messages'] = len(conversation_history)
        if last_timestamp:
            metrics['last_message_timestamp'] = last_timestamp

        # Update the database
        updated_metrics_json = json.dumps(metrics)

        # Update users table
        cursor.execute("""
            UPDATE users 
            SET metrics_json = ?, last_interaction_timestamp = ?
            WHERE ig_username = 'blissedlia'
        """, (updated_metrics_json, last_timestamp))

        conn.commit()
        print("\nDatabase updated successfully!")

        # Verify the conversation ends correctly
        if conversation_history:
            last_message = conversation_history[-1]
            print(
                f"\nLast message in conversation: {last_message.get('text', '')[:100]}...")
            print(f"Last message type: {last_message.get('type')}")
            print(f"Last message timestamp: {last_message.get('timestamp')}")

        conn.close()

    except Exception as e:
        print(f"Error cleaning up conversation: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals() and conn:
            conn.close()


if __name__ == "__main__":
    cleanup_lia_conversation_v2()
