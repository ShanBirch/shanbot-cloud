import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Simple analytics class that doesn't require dependencies


class SimpleAnalytics:
    def __init__(self):
        self.conversations = {}
        self.global_metrics = {
            "total_conversations": 0,
            "total_messages": 0,
            "coaching_inquiries": 0,
            "signups": 0,
            "ai_detections": 0,
            "question_stats": {
                "ai_questions_asked": 0,
                "user_responses_to_questions": 0,
                "response_rate": 0.0
            }
        }

    def analyze_message(self, subscriber_id, message, is_ai_response=False):
        # Initialize conversation if needed
        if subscriber_id not in self.conversations:
            self.conversations[subscriber_id] = {
                "messages": [],
                "metrics": {
                    "total_messages": 0,
                    "ai_questions": 0,
                    "user_responses": 0,
                    "user_responses_to_questions": 0,
                    "coaching_inquiries": 0,
                    "ai_detections": 0,
                    "last_message_time": None
                }
            }
            self.global_metrics["total_conversations"] += 1

        # Update message counts
        self.global_metrics["total_messages"] += 1
        self.conversations[subscriber_id]["metrics"]["total_messages"] += 1

        # Record message
        self.conversations[subscriber_id]["messages"].append({
            "text": message,
            "timestamp": datetime.now().isoformat(),
            "is_ai": is_ai_response
        })

        # Analyze message content
        contains_question = "?" in message
        coaching_inquiry = any(pattern in message.lower() for pattern in
                               ["coach", "sign up", "join program", "cost", "training", "price"])
        ai_detection = any(pattern in message.lower() for pattern in
                           ["bot", "ai", "artificial", "automated", "computer"])

        # Update metrics
        if contains_question and is_ai_response:
            self.conversations[subscriber_id]["metrics"]["ai_questions"] += 1
            self.global_metrics["question_stats"]["ai_questions_asked"] += 1

        if not is_ai_response:
            self.conversations[subscriber_id]["metrics"]["user_responses"] += 1

            # Check if responding to question
            messages = self.conversations[subscriber_id]["messages"]
            if len(messages) >= 2 and messages[-2]["is_ai"]:
                if "?" in messages[-2]["text"]:
                    self.conversations[subscriber_id]["metrics"]["user_responses_to_questions"] += 1
                    self.global_metrics["question_stats"]["user_responses_to_questions"] += 1

        # Update question response rate
        if self.global_metrics["question_stats"]["ai_questions_asked"] > 0:
            self.global_metrics["question_stats"]["response_rate"] = (
                self.global_metrics["question_stats"]["user_responses_to_questions"] /
                self.global_metrics["question_stats"]["ai_questions_asked"]
            )

        # Track coaching inquiries
        if coaching_inquiry and not is_ai_response:
            self.conversations[subscriber_id]["metrics"]["coaching_inquiries"] += 1
            self.global_metrics["coaching_inquiries"] += 1

        # Track AI detection
        if ai_detection and not is_ai_response:
            self.conversations[subscriber_id]["metrics"]["ai_detections"] += 1
            self.global_metrics["ai_detections"] += 1

    def get_global_metrics(self):
        return self.global_metrics

    def get_conversation_metrics(self, subscriber_id):
        if subscriber_id not in self.conversations:
            return {}
        return self.conversations[subscriber_id]["metrics"]

    def export_analytics(self, file_path):
        with open(file_path, 'w') as f:
            json.dump({
                "global_metrics": self.global_metrics,
                "conversations": self.conversations
            }, f, indent=2)


def main():
    print("Starting analytics demo...")
    analytics = SimpleAnalytics()

    # Sample conversations
    conversations = [
        {
            "id": "user1",
            "messages": [
                "Hi there",
                "I'm interested in your fitness coaching",
                "How much does it cost?",
                "That's a bit expensive for me right now",
                "Maybe next month"
            ]
        },
        {
            "id": "user2",
            "messages": [
                "Hello",
                "Are you a real person or a bot?",
                "I'm not sure if I believe you",
                "Whatever"
            ]
        },
        {
            "id": "user3",
            "messages": [
                "Hey Shannon",
                "I've been working out for years",
                "I want to take it to the next level",
                "How do I sign up for coaching?",
                "Great, I'll do it"
            ]
        }
    ]

    # Process conversations
    for conv in conversations:
        user_id = conv["id"]

        for i, msg in enumerate(conv["messages"]):
            # Add user message
            analytics.analyze_message(user_id, msg, is_ai_response=False)

            # Generate and add AI response
            ai_response = "Thanks for your message!"

            if "bot" in msg.lower() or "ai" in msg.lower():
                ai_response = "I'm Shannon, a real fitness coach, not a bot!"
            elif "cost" in msg.lower() or "how much" in msg.lower():
                ai_response = "The coaching program costs $299 per month. Is that within your budget?"
            elif "sign up" in msg.lower():
                ai_response = "Great! I'll send you the signup link. Are you ready to start?"
            elif i < len(conv["messages"]) - 1:  # Not the last message
                ai_response = "That's great! Tell me more about your goals?"

            analytics.analyze_message(
                user_id, ai_response, is_ai_response=True)

    # Show global metrics
    print("\n=== GLOBAL METRICS ===")
    print(json.dumps(analytics.get_global_metrics(), indent=2))

    # Show conversation metrics
    for user_id in ["user1", "user2", "user3"]:
        print(f"\n=== METRICS FOR {user_id} ===")
        print(json.dumps(analytics.get_conversation_metrics(user_id), indent=2))

    # Export data
    output_file = "analytics_demo_results.json"
    analytics.export_analytics(output_file)
    print(f"\nAnalytics data exported to {output_file}")

    # Summary of key findings
    print("\n=== KEY ANALYTICS INSIGHTS ===")
    print(
        f"Total conversations: {analytics.global_metrics['total_conversations']}")
    print(f"Total messages: {analytics.global_metrics['total_messages']}")
    print(
        f"Coaching inquiries: {analytics.global_metrics['coaching_inquiries']}")
    print(f"AI detections: {analytics.global_metrics['ai_detections']}")

    question_stats = analytics.global_metrics["question_stats"]
    print(f"AI questions asked: {question_stats['ai_questions_asked']}")
    print(
        f"User responses to questions: {question_stats['user_responses_to_questions']}")
    print(
        f"Question response rate: {question_stats['response_rate'] * 100:.1f}%")


if __name__ == "__main__":
    main()
