import sqlite3
import json
from datetime import datetime


def cleanup_lia_conversation():
    """Clean up Lia_romy's conversation by removing unwanted AI messages"""

    # Unwanted messages to remove (partial matching)
    unwanted_messages = [
        "Hey! Awesome, let's get you started. So I can point you in the right direction, what's the number one goal you're looking to achieve with the program?",
        "I definitely think so 100% plus support and guidance from me. I know youll totally step your fitness up!",
        "Omg, it exists! That's awesome you found us! I completely understand the excitement – and maybe a little apprehension too. A lot of vegans struggle with hitting their weight loss goals because they accidentally fall into high-sugar, low-protein traps. What's the biggest fear you have about joining a challenge like this?",
        "Oh no, I'm sorry you feel that way! I totally get that a challenge can seem daunting. Lots of people feel that initial apprehension. We focus on making the process super achievable and fun, not restrictive or overwhelming. So to help me tailor the approach, what's the biggest thing holding you back from starting something like this?",
        "I hear you. That's a common misconception about plant-based eating – it's not just about total weight loss, but also body composition. Many vegans inadvertently end up with higher body fat percentages due to unbalanced macros. To help me personalize a plan for you, could you tell me a bit more about what \"pbf distributed all over the body\" means to you in terms of how you'd like to look and feel?",
        "I understand. That's a really common concern – many people focus on overall weight loss and forget about body composition. Visceral fat is stubborn, yes, but it responds well to a combined approach of targeted training and precise macro-balancing, which is exactly what we focus on. To give you the most effective plan, what are your typical daily food choices right now?"
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

        # Find and remove unwanted messages
        messages_to_remove = []
        for i, message in enumerate(conversation_history):
            if message.get('type') == 'ai':
                text = message.get('text', '')
                for unwanted in unwanted_messages:
                    if unwanted in text:
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

        # Also clean up the messages table if needed
        # First, let's see what's in the messages table for this user
        cursor.execute(
            "SELECT * FROM messages WHERE ig_username = 'blissedlia' ORDER BY timestamp")
        db_messages = cursor.fetchall()

        print(
            f"\nMessages table has {len(db_messages)} messages for blissedlia")

        # Remove unwanted messages from the messages table too
        messages_to_delete = []
        for msg in db_messages:
            # Check if text column exists and is not None
            if len(msg) > 4 and msg[4] is not None:
                msg_text = msg[4]  # text column
                for unwanted in unwanted_messages:
                    if unwanted in msg_text:
                        messages_to_delete.append(msg[0])  # id column
                        print(
                            f"Found unwanted message in DB: {msg_text[:100]}...")
                        break

        if messages_to_delete:
            placeholders = ','.join(['?' for _ in messages_to_delete])
            cursor.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})", messages_to_delete)
            print(
                f"Deleted {len(messages_to_delete)} unwanted messages from messages table")

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
    cleanup_lia_conversation()
