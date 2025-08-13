"""
Shanbot Workout Handler
======================
Handles all workout and training-related messages including:
- Workout program requests
- Exercise questions
- Training schedule queries
- Form technique questions
- Program modifications
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from utilities import (
    get_user_data,
    update_analytics_data,
    call_gemini_with_retry,
    update_manychat_fields
)
from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
from app import prompts

logger = logging.getLogger("shanbot_workout")


class WorkoutHandler:
    """Handler for workout and training-related messages."""

    def __init__(self):
        """Initialize workout handler."""
        logger.info("WorkoutHandler initialized")

    async def handle_workout_request(self, ig_username: str, message_text: str,
                                     subscriber_id: str, first_name: str, last_name: str,
                                     timestamp: str) -> bool:
        """Handle workout-related requests."""
        try:
            logger.info(
                f"[Workout] Processing request from {ig_username}: {message_text[:50]}...")

            # Get user data for context
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            # Check if user has Trainerize access
            has_trainerize = metrics.get('has_trainerize_account', False)
            client_status = metrics.get('client_status', 'Unknown')

            # Analyze workout request type
            request_type = await self._analyze_workout_request(message_text, conversations)

            if request_type == "trainerize_needed" and not has_trainerize:
                return await self._handle_trainerize_signup_needed(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "program_modification" and has_trainerize:
                return await self._handle_program_modification(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "exercise_question":
                return await self._handle_exercise_question(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "schedule_question":
                return await self._handle_schedule_question(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            else:
                # General workout advice
                return await self._handle_general_workout_advice(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

        except Exception as e:
            logger.error(
                f"[Workout] Error handling request from {ig_username}: {e}")
            return False

    async def _analyze_workout_request(self, message_text: str,
                                       conversation_history: list) -> str:
        """Analyze the type of workout request."""
        try:
            context = "\n".join([
                f"{msg.get('type', 'user')}: {msg.get('text', '')}"
                for msg in conversation_history[-3:]
            ])

            analysis_prompt = f"""
            Analyze this workout-related message and classify the request type.
            
            CONVERSATION CONTEXT:
            {context if context else "[New conversation]"}
            
            MESSAGE: "{message_text}"
            
            REQUEST TYPES:
            - trainerize_needed: Needs access to workout program/app
            - program_modification: Wants to change existing program
            - exercise_question: Asking about specific exercises/techniques
            - schedule_question: Asking about workout timing/frequency
            - general_advice: General workout advice/motivation
            
            Reply with just the request type.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", analysis_prompt)
            request_type = response.strip().lower()

            if request_type not in ["trainerize_needed", "program_modification", "exercise_question",
                                    "schedule_question", "general_advice"]:
                request_type = "general_advice"

            logger.info(f"[Workout] Request type: {request_type}")
            return request_type

        except Exception as e:
            logger.error(f"[Workout] Request analysis error: {e}")
            return "general_advice"

    async def _handle_trainerize_signup_needed(self, ig_username: str, message_text: str,
                                               subscriber_id: str, first_name: str, last_name: str,
                                               timestamp: str) -> bool:
        """Handle requests that require Trainerize access."""
        try:
            # Generate response encouraging onboarding
            prompt = f"""
            A user is asking about workout programs but doesn't have access to Trainerize yet.
            Generate a helpful response that:
            1. Acknowledges their workout question
            2. Explains they need access to the coaching program
            3. Encourages them to book a consultation or sign up
            4. Uses Shannon's friendly Australian tone
            
            User message: "{message_text}"
            User name: {first_name}
            
            Keep it concise and action-oriented.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", prompt)

            if response:
                # Queue for review
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp=timestamp,
                    generated_prompt_text=prompt,
                    proposed_response_text=response,
                    prompt_type="workout_trainerize_needed"
                )

                if review_id:
                    logger.info(
                        f"[Workout] Queued Trainerize signup response for {ig_username}")

                    # Update analytics
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        needs_trainerize_access=True
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Workout] Trainerize signup error: {e}")
            return False

    async def _handle_program_modification(self, ig_username: str, message_text: str,
                                           subscriber_id: str, first_name: str, last_name: str,
                                           timestamp: str) -> bool:
        """Handle requests to modify existing workout programs."""
        try:
            # Get user data for program context
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            current_program = metrics.get('current_workout_program', 'Unknown')
            training_days = metrics.get('training_days', 'Unknown')

            prompt = f"""
            A client wants to modify their workout program.
            
            CLIENT INFO:
            - Name: {first_name}
            - Current program: {current_program}
            - Training days: {training_days}
            
            REQUEST: "{message_text}"
            
            Generate a response that:
            1. Acknowledges their modification request
            2. Asks clarifying questions if needed
            3. Explains next steps (updating in Trainerize)
            4. Uses Shannon's coaching tone
            
            Keep it professional but friendly.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", prompt)

            if response:
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp=timestamp,
                    generated_prompt_text=prompt,
                    proposed_response_text=response,
                    prompt_type="workout_program_modification"
                )

                if review_id:
                    logger.info(
                        f"[Workout] Queued program modification response for {ig_username}")

                    # Flag for manual attention
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        needs_program_update=True,
                        program_modification_request=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Workout] Program modification error: {e}")
            return False

    async def _handle_exercise_question(self, ig_username: str, message_text: str,
                                        subscriber_id: str, first_name: str, last_name: str,
                                        timestamp: str) -> bool:
        """Handle questions about specific exercises or techniques."""
        try:
            prompt = f"""
            A client is asking about a specific exercise or technique.
            
            CLIENT: {first_name}
            QUESTION: "{message_text}"
            
            Provide a helpful response that:
            1. Answers their specific question
            2. Gives practical tips or cues
            3. Mentions safety considerations if relevant
            4. Encourages them to share videos for form checks
            5. Uses Shannon's coaching expertise and tone
            
            Keep it informative but accessible.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", prompt)

            if response:
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp=timestamp,
                    generated_prompt_text=prompt,
                    proposed_response_text=response,
                    prompt_type="workout_exercise_question"
                )

                if review_id:
                    logger.info(
                        f"[Workout] Queued exercise question response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_exercise_question=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Workout] Exercise question error: {e}")
            return False

    async def _handle_schedule_question(self, ig_username: str, message_text: str,
                                        subscriber_id: str, first_name: str, last_name: str,
                                        timestamp: str) -> bool:
        """Handle questions about workout scheduling and frequency."""
        try:
            # Get user data for personalized advice
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            fitness_goal = metrics.get('primary_fitness_goal', 'Unknown')
            activity_level = metrics.get('activity_level', 'Unknown')

            prompt = f"""
            A client is asking about workout scheduling/frequency.
            
            CLIENT INFO:
            - Name: {first_name}
            - Fitness goal: {fitness_goal}
            - Activity level: {activity_level}
            
            QUESTION: "{message_text}"
            
            Provide scheduling advice that:
            1. Addresses their specific question
            2. Considers their goal and activity level
            3. Gives practical, realistic recommendations
            4. Mentions recovery importance
            5. Uses Shannon's knowledgeable but approachable tone
            
            Keep it actionable and motivating.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", prompt)

            if response:
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp=timestamp,
                    generated_prompt_text=prompt,
                    proposed_response_text=response,
                    prompt_type="workout_schedule_question"
                )

                if review_id:
                    logger.info(
                        f"[Workout] Queued schedule question response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_schedule_question=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Workout] Schedule question error: {e}")
            return False

    async def _handle_general_workout_advice(self, ig_username: str, message_text: str,
                                             subscriber_id: str, first_name: str, last_name: str,
                                             timestamp: str) -> bool:
        """Handle general workout advice and motivation."""
        try:
            prompt = f"""
            A user is asking for general workout advice or motivation.
            
            USER: {first_name}
            MESSAGE: "{message_text}"
            
            Provide a helpful response that:
            1. Addresses their message with relevant advice
            2. Gives actionable tips they can implement
            3. Encourages consistency and progress
            4. Uses Shannon's motivational coaching style
            5. Suggests they consider coaching for personalized help
            
            Keep it encouraging and practical.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", prompt)

            if response:
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp=timestamp,
                    generated_prompt_text=prompt,
                    proposed_response_text=response,
                    prompt_type="workout_general_advice"
                )

                if review_id:
                    logger.info(
                        f"[Workout] Queued general advice response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_workout_advice_request=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Workout] General advice error: {e}")
            return False
