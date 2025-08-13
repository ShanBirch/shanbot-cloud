"""
Ad Response Handler Service
==========================
Detects and handles responses to Instagram ads and marketing content.
"""

import logging
from typing import Dict, Any, List, Tuple
import re

logger = logging.getLogger("shanbot_ad_response")


class AdResponseHandler:
    """Handles detection and processing of ad responses from Instagram users."""

    @staticmethod
    async def detect_ad_intent(ig_username: str, message_text: str,
                               conversation_history: List[Dict[str, Any]]) -> Tuple[bool, str, int]:
        """
        Detect if a message is likely a response to an ad.

        Returns:
            Tuple of (is_ad_response, scenario, confidence_percentage)
        """
        try:
            logger.info(
                f"[AdResponse] Analyzing message from {ig_username} for ad intent")

            # Clean and normalize message text
            text_lower = message_text.lower().strip()

            # Define ad response indicators
            ad_response_keywords = [
                'saw your ad', 'from your ad', 'from the ad', 'your advertisement',
                'saw your post', 'instagram ad', 'sponsored post', 'your promotion',
                'fitness program', 'weight loss', 'transformation', 'coaching',
                'challenge', 'workout plan', 'meal plan', 'personal trainer'
            ]

            # Define high-intent phrases that suggest ad response
            high_intent_phrases = [
                'interested', 'want to know more', 'tell me more', 'how much',
                'sign up', 'join', 'start', 'get started', 'more info',
                'details', 'how does it work', 'what do you offer'
            ]

            # Check for direct ad mentions
            direct_ad_mentions = any(
                keyword in text_lower for keyword in ad_response_keywords)

            # Check for high intent phrases
            high_intent_detected = any(
                phrase in text_lower for phrase in high_intent_phrases)

            # Analyze conversation history for context
            is_first_message = len(conversation_history) == 0

            # Calculate confidence score
            confidence = 0
            scenario = "unknown"

            if direct_ad_mentions:
                confidence += 80
                scenario = "direct_ad_mention"
                logger.info(
                    f"[AdResponse] Direct ad mention detected: {confidence}%")

            elif high_intent_detected and is_first_message:
                confidence += 70
                scenario = "high_intent_first_message"
                logger.info(
                    f"[AdResponse] High intent first message: {confidence}%")

            elif is_first_message and len(text_lower) < 100:
                # Short first message might be ad response
                confidence += 40
                scenario = "short_first_message"

                # Look for fitness-related keywords
                fitness_keywords = [
                    'fitness', 'workout', 'exercise', 'gym', 'training',
                    'weight', 'lose', 'gain', 'muscle', 'fat', 'diet',
                    'nutrition', 'healthy', 'health', 'body', 'shape'
                ]

                if any(keyword in text_lower for keyword in fitness_keywords):
                    confidence += 30
                    scenario = "fitness_related_first_message"

            elif not is_first_message:
                # For existing conversations, lower the ad response likelihood
                confidence = max(0, confidence - 30)
                scenario = "existing_conversation"

            # Additional context analysis
            if 'help' in text_lower or 'support' in text_lower:
                confidence += 20

            if any(word in text_lower for word in ['hi', 'hello', 'hey']):
                if is_first_message:
                    confidence += 10

            # Determine if this is likely an ad response
            is_ad_response = confidence >= 50

            logger.info(
                f"[AdResponse] Analysis complete: {is_ad_response}, {scenario}, {confidence}%")

            return is_ad_response, scenario, confidence

        except Exception as e:
            logger.error(
                f"[AdResponse] Error detecting ad intent for {ig_username}: {e}")
            return False, "error", 0

    @staticmethod
    def get_ad_response_context(scenario: str, confidence: int) -> Dict[str, Any]:
        """Get context information for ad response handling."""

        context_map = {
            "direct_ad_mention": {
                "priority": "high",
                "response_type": "ad_acknowledgment",
                "next_action": "provide_program_info",
                "urgency": "immediate"
            },
            "high_intent_first_message": {
                "priority": "high",
                "response_type": "interest_confirmation",
                "next_action": "gather_goals",
                "urgency": "quick"
            },
            "fitness_related_first_message": {
                "priority": "medium",
                "response_type": "gentle_engagement",
                "next_action": "ask_about_goals",
                "urgency": "normal"
            },
            "short_first_message": {
                "priority": "medium",
                "response_type": "friendly_inquiry",
                "next_action": "understand_needs",
                "urgency": "normal"
            },
            "existing_conversation": {
                "priority": "low",
                "response_type": "context_aware",
                "next_action": "continue_conversation",
                "urgency": "low"
            }
        }

        default_context = {
            "priority": "low",
            "response_type": "general",
            "next_action": "assess_situation",
            "urgency": "low"
        }

        context = context_map.get(scenario, default_context)
        context["confidence"] = confidence
        context["scenario"] = scenario

        return context

    @staticmethod
    def should_use_ad_flow(confidence: int, scenario: str) -> bool:
        """Determine if the ad response flow should be used."""
        # Use ad flow for high-confidence ad responses
        if confidence >= 70:
            return True

        # Use ad flow for medium confidence with specific scenarios
        if confidence >= 50 and scenario in ["high_intent_first_message", "fitness_related_first_message"]:
            return True

        return False
