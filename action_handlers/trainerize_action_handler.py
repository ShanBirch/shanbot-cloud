"""
Trainerize Action Handler
========================
Handles all Trainerize-related actions including workout requests and automation.
"""

from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
from webhook_handlers import get_user_data, update_analytics_data, call_gemini_with_retry
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple

# Import from the main webhook_handlers (not the app one)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("shanbot_trainerize")


class TrainerizeActionHandler:
    """Handles Trainerize-related actions and automation."""

    @staticmethod
    async def handle_trainerize_actions(ig_username: str, message_text: str, subscriber_id: str,
                                        first_name: str, last_name: str) -> bool:
        """Handle Trainerize-related actions."""
        try:
            # Check for workout requests
            if await TrainerizeActionHandler._is_workout_request(message_text):
                return await TrainerizeActionHandler._handle_workout_request(
                    ig_username, message_text, subscriber_id, first_name, last_name
                )

            # Check for program building requests
            if await TrainerizeActionHandler._is_program_build_request(message_text):
                return await TrainerizeActionHandler._handle_program_build_request(
                    ig_username, message_text, subscriber_id, first_name, last_name
                )

            return False

        except Exception as e:
            logger.error(
                f"[TrainerizeAction] Error handling Trainerize actions for {ig_username}: {e}")
            return False

    @staticmethod
    async def _is_workout_request(message_text: str) -> bool:
        """Detect if message is a workout request.
        STRICT: Only trigger when the message is exactly 'adjust my workout plz' (case-insensitive, ignoring whitespace).
        """
        if not isinstance(message_text, str):
            return False
        normalized = ' '.join(message_text.strip().lower().split())
        return normalized == 'adjust my workout plz'

    @staticmethod
    async def _is_program_build_request(message_text: str) -> bool:
        """Detect if message is a program building request."""
        build_keywords = [
            'build program', 'create program', 'make program',
            'design program', 'set up program', 'program me',
            'trainerize program', 'workout program'
        ]

        message_lower = message_text.lower()
        return any(keyword in message_lower for keyword in build_keywords)

    @staticmethod
    async def _handle_workout_request(ig_username: str, message_text: str, subscriber_id: str,
                                      first_name: str, last_name: str) -> bool:
        """Handle workout request."""
        try:
            logger.info(
                f"[TrainerizeWorkout] Handling workout request for {ig_username}")

            # Get user data for context
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            conversation_history = metrics.get('conversation_history', [])
            client_analysis = metrics.get('client_analysis', {})

            # Check if user is a client
            client_status = metrics.get('client_status', 'Prospect')

            if client_status not in ['Trial Client', 'Paid Client']:
                # Not a client, suggest onboarding
                response = await TrainerizeActionHandler._generate_onboarding_suggestion(ig_username, message_text)
            else:
                # Is a client, can provide workout
                response = await TrainerizeActionHandler._generate_workout_response(
                    ig_username, message_text, client_analysis, conversation_history
                )

            if response:
                # Queue response for review
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp="",
                    generated_prompt_text="Workout request handling",
                    proposed_response_text=response,
                    prompt_type="workout_request"
                )

                if review_id:
                    logger.info(
                        f"[TrainerizeWorkout] Queued workout response (ID: {review_id}) for {ig_username}")
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name)
                    return True

            return False

        except Exception as e:
            logger.error(
                f"[TrainerizeWorkout] Error handling workout request for {ig_username}: {e}")
            return False

    @staticmethod
    async def _handle_program_build_request(ig_username: str, message_text: str, subscriber_id: str,
                                            first_name: str, last_name: str) -> bool:
        """Handle program building request."""
        try:
            logger.info(
                f"[TrainerizeBuild] Handling program build request for {ig_username}")

            # Import Trainerize automation
            from trainerize_automation import TrainerizeAutomation

            # Get user data
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            client_analysis = metrics.get('client_analysis', {})

            # Check if user is a client
            client_status = metrics.get('client_status', 'Prospect')

            if client_status not in ['Trial Client', 'Paid Client']:
                response = "I'd love to build you a personalized program! First, let's get you set up as a client so I can access your fitness profile and goals. Would you like to start the onboarding process?"
            else:
                # Attempt to build program
                try:
                    automation = TrainerizeAutomation()

                    # Extract program requirements from message
                    program_type = await TrainerizeActionHandler._extract_program_type(message_text)

                    # Build program based on client data
                    success = await automation.build_workout_program(
                        ig_username=ig_username,
                        program_type=program_type,
                        client_data=client_analysis
                    )

                    if success:
                        response = f"Great! I've built your {program_type} program in Trainerize. Check your app - it should be ready to go! Let me know if you need any adjustments."

                        # Update client status
                        update_analytics_data(ig_username, "", "", subscriber_id, first_name, last_name,
                                              program_built=True)
                    else:
                        response = "I had some trouble building your program automatically. Let me check your account and get back to you shortly!"

                except Exception as automation_error:
                    logger.error(
                        f"[TrainerizeBuild] Automation error for {ig_username}: {automation_error}")
                    response = "I'm having some technical difficulties building your program right now. Let me sort this out and get back to you!"

            # Queue response
            review_id = add_response_to_review_queue(
                user_ig_username=ig_username,
                user_subscriber_id=subscriber_id,
                incoming_message_text=message_text,
                incoming_message_timestamp="",
                generated_prompt_text="Program build request handling",
                proposed_response_text=response,
                prompt_type="program_build"
            )

            if review_id:
                logger.info(
                    f"[TrainerizeBuild] Queued program build response (ID: {review_id}) for {ig_username}")
                update_analytics_data(
                    ig_username, message_text, response, subscriber_id, first_name, last_name)
                return True

            return False

        except Exception as e:
            logger.error(
                f"[TrainerizeBuild] Error handling program build for {ig_username}: {e}")
            return False

    @staticmethod
    async def _generate_onboarding_suggestion(ig_username: str, message_text: str) -> str:
        """Generate onboarding suggestion for non-clients."""
        suggestions = [
            "I'd love to help you with workouts! To give you the best personalized program, I'll need to learn about your goals and experience first. Ready to get started with a quick onboarding?",
            "Great question about workouts! I can definitely help, but first let's get you set up as a client so I can create something perfect for your goals. Want to begin the onboarding process?",
            "I'm excited to help with your fitness journey! To provide the most effective workout plan, I'll need some info about your experience, goals, and preferences. Shall we start the onboarding?"
        ]

        import random
        return random.choice(suggestions)

    @staticmethod
    async def _generate_workout_response(ig_username: str, message_text: str, client_analysis: Dict,
                                         conversation_history: list) -> str:
        """Generate workout response for existing clients."""
        prompt = f"""
        Generate a helpful workout response for a client.
        
        Client: {ig_username}
        Request: {message_text}
        
        Client Analysis: {json.dumps(client_analysis, indent=2)}
        
        Provide a specific, actionable workout recommendation based on their profile.
        Include exercises, sets, reps, and any relevant modifications.
        Keep it encouraging and personalized.
        """

        return await call_gemini_with_retry("gemini-2.0-flash-thinking-exp-01-21", prompt)

    @staticmethod
    async def _extract_program_type(message_text: str) -> str:
        """Extract program type from message."""
        message_lower = message_text.lower()

        if any(word in message_lower for word in ['strength', 'muscle', 'bulk', 'gain']):
            return "strength"
        elif any(word in message_lower for word in ['cardio', 'endurance', 'running', 'conditioning']):
            return "cardio"
        elif any(word in message_lower for word in ['weight loss', 'fat loss', 'lean', 'cut']):
            return "weight_loss"
        elif any(word in message_lower for word in ['functional', 'mobility', 'movement']):
            return "functional"
        else:
            return "general_fitness"
