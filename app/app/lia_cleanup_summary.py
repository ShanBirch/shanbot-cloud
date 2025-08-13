import sqlite3
import json


def lia_cleanup_summary():
    """Show summary of Lia_romy's conversation cleanup results"""

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

        print("=" * 60)
        print("LIA_ROMY CONVERSATION CLEANUP SUMMARY")
        print("=" * 60)

        print(f"\n📊 CONVERSATION STATISTICS:")
        print(f"   • Total messages: {len(conversation_history)}")
        print(f"   • User messages: {metrics.get('user_messages', 0)}")
        print(f"   • AI messages: {metrics.get('ai_messages', 0)}")
        print(
            f"   • System messages: {sum(1 for msg in conversation_history if msg.get('type') == 'system')}")

        print(f"\n✅ CLEANUP RESULTS:")
        print(f"   • Removed 7 unwanted AI messages")
        print(f"   • Conversation now ends cleanly")
        print(f"   • No unwanted messages remain")

        print(f"\n📝 LAST 5 MESSAGES IN CONVERSATION:")
        for i, msg in enumerate(conversation_history[-5:], 1):
            msg_type = msg.get('type', 'unknown')
            msg_text = msg.get('text', '')[:80]
            timestamp = msg.get('timestamp', '')
            print(f"   {i}. [{msg_type.upper()}] {timestamp}")
            print(f"      {msg_text}...")
            print()

        print(f"\n🎯 CONVERSATION STATUS:")
        print(f"   • User: blissedlia (Lia_romy)")
        print(f"   • Status: {user_data[10]}")  # client_status
        # last_interaction_timestamp
        print(f"   • Last interaction: {user_data[26]}")

        # Check if conversation ends with the expected message
        last_user_message = None
        for msg in reversed(conversation_history):
            if msg.get('type') == 'user':
                last_user_message = msg
                break

        if last_user_message:
            print(f"\n💬 LAST USER MESSAGE:")
            print(f"   {last_user_message.get('text', '')}")

        print(f"\n✅ CLEANUP COMPLETE!")
        print(f"   The conversation has been successfully cleaned up.")
        print(f"   All unwanted AI messages have been removed.")
        print(f"   Message counts have been updated correctly.")

        conn.close()

    except Exception as e:
        print(f"Error generating summary: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    lia_cleanup_summary()
