import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from fastapi import FastAPI, APIRouter, Request, HTTPException
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics")


class ConversationAnalytics:
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

        logger.info(
            f"Analyzed message from {subscriber_id}: {message[:50]}...")

    def get_global_metrics(self):
        return self.global_metrics

    def get_conversation_metrics(self, subscriber_id):
        if subscriber_id not in self.conversations:
            return {}
        return self.conversations[subscriber_id]["metrics"]

    def get_engagement_analysis(self, subscriber_id):
        if subscriber_id not in self.conversations:
            return {}

        conv = self.conversations[subscriber_id]
        metrics = conv["metrics"]

        ai_messages = sum(1 for m in conv["messages"] if m["is_ai"])
        user_messages = sum(1 for m in conv["messages"] if not m["is_ai"])

        questions_asked = metrics["ai_questions"]
        responses_after_questions = metrics["user_responses_to_questions"]

        question_response_rate = responses_after_questions / \
            questions_asked if questions_asked > 0 else 0

        return {
            "total_messages": metrics["total_messages"],
            "ai_messages": ai_messages,
            "user_messages": user_messages,
            "questions_asked": questions_asked,
            "question_response_rate": question_response_rate,
            "coaching_inquiries": metrics["coaching_inquiries"],
            "ai_detections": metrics["ai_detections"]
        }

    def export_analytics(self, file_path):
        with open(file_path, 'w') as f:
            json.dump({
                "global_metrics": self.global_metrics,
                "conversations": self.conversations
            }, f, indent=2)


# Create analytics instance
analytics = ConversationAnalytics()

# Create router for endpoints
router = APIRouter()


@router.get("/analytics/global")
async def get_global_metrics():
    """Get global conversation metrics."""
    return analytics.get_global_metrics()


@router.get("/analytics/conversation/{subscriber_id}")
async def get_conversation_metrics(subscriber_id: str):
    """Get metrics for a specific conversation."""
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
async def export_analytics(file_path: str):
    """Export all analytics data to a JSON file."""
    try:
        analytics.export_analytics(file_path)
        return {"message": f"Analytics exported to {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Decorator for webhooks


def track_conversation_analytics(endpoint_func):
    async def wrapper(request: Request, *args, **kwargs):
        try:
            # Copy the request body for analytics before it's consumed
            body = await request.body()
            # Re-creating a new request with the same body
            new_request = Request(request.scope, request._receive)

            # Process the original request
            response = await endpoint_func(new_request, *args, **kwargs)

            # Parse the request body as JSON for analytics
            try:
                body_str = body.decode()
                data = json.loads(body_str)

                # Extract subscriber ID and message
                subscriber_id = data.get("id", "")
                if not subscriber_id and "subscriber" in data:
                    subscriber_info = data.get("subscriber", {})
                    subscriber_id = subscriber_info.get("id", "")

                custom_fields = data.get("custom_fields", {})
                conversation_value = custom_fields.get("CONVERSATION", "")

                # Analyze the last user message if present
                if conversation_value:
                    messages = conversation_value.split('\n')
                    if len(messages) > 0:
                        last_message = messages[-1]
                        # Check if message is from user (not AI)
                        if not last_message.startswith("Shannon:"):
                            analytics.analyze_message(
                                subscriber_id, last_message, is_ai_response=False)

                # If response contains AI message, analyze it
                if isinstance(response, dict) and "content" in response:
                    content = response["content"]
                    if isinstance(content, dict) and "messages" in content:
                        ai_messages = content.get("messages", [])
                        if ai_messages and len(ai_messages) > 0:
                            ai_message = ai_messages[0]
                            analytics.analyze_message(
                                subscriber_id, ai_message, is_ai_response=True)

            except Exception as e:
                logger.error(
                    f"Error processing analytics: {str(e)}", exc_info=True)

            return response

        except Exception as e:
            logger.error(
                f"Error in track_conversation_analytics decorator: {str(e)}", exc_info=True)
            # Forward the original request to the endpoint
            return await endpoint_func(request, *args, **kwargs)

    return wrapper


# Example usage:
"""
from analytics_integration import analytics, router as analytics_router, track_conversation_analytics

# Add this to your FastAPI app
app.include_router(analytics_router)

# Decorate your webhook endpoints
@app.post("/webhook/manychat")
@track_conversation_analytics
async def manychat_webhook(request: Request):
    # your existing code
"""
