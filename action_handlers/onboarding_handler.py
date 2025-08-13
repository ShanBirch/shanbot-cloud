"""
Shanbot Onboarding Handler
==========================
Handles onboarding interest and enrollment processes including:
- Initial coaching interest
- Program information requests
- Trial setup coordination
- Client intake processes
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

logger = logging.getLogger("shanbot_onboarding")


class OnboardingHandler:
    """Handler for onboarding interest and enrollment."""

    def __init__(self):
        """Initialize onboarding handler."""
        logger.info("OnboardingHandler initialized")

    async def handle_onboarding_interest(self, ig_username: str, message_text: str,
                                         subscriber_id: str, first_name: str, last_name: str,
                                         timestamp: str) -> bool:
        """Handle onboarding interest and enrollment requests."""
        try:
            logger.info(
                f"[Onboarding] Processing interest from {ig_username}: {message_text[:50]}...")

            # Get user data for context
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            # Analyze onboarding request type
            request_type = await self._analyze_onboarding_request(message_text, conversations)

            if request_type == "program_inquiry":
                return await self._handle_program_inquiry(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "pricing_question":
                return await self._handle_pricing_question(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "trial_interest":
                return await self._handle_trial_interest(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "booking_request":
                return await self._handle_booking_request(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "ready_to_start":
                return await self._handle_ready_to_start(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            else:
                # General onboarding interest
                return await self._handle_general_interest(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

        except Exception as e:
            logger.error(
                f"[Onboarding] Error handling interest from {ig_username}: {e}")
            return False

    async def _analyze_onboarding_request(self, message_text: str,
                                          conversation_history: list) -> str:
        """Analyze the type of onboarding request."""
        try:
            context = "\n".join([
                f"{msg.get('type', 'user')}: {msg.get('text', '')}"
                for msg in conversation_history[-3:]
            ])

            analysis_prompt = f"""
            Analyze this message from someone interested in coaching and classify the request type.
            
            CONVERSATION CONTEXT:
            {context if context else "[New conversation]"}
            
            MESSAGE: "{message_text}"
            
            REQUEST TYPES:
            - program_inquiry: Asking about coaching programs/services
            - pricing_question: Asking about costs/pricing
            - trial_interest: Interested in trying a trial/free period
            - booking_request: Wants to book a call/consultation
            - ready_to_start: Ready to sign up and begin
            - general_interest: General interest in coaching
            
            Reply with just the request type.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", analysis_prompt)
            request_type = response.strip().lower()

            valid_types = ["program_inquiry", "pricing_question", "trial_interest",
                           "booking_request", "ready_to_start", "general_interest"]

            if request_type not in valid_types:
                request_type = "general_interest"

            logger.info(f"[Onboarding] Request type: {request_type}")
            return request_type

        except Exception as e:
            logger.error(f"[Onboarding] Request analysis error: {e}")
            return "general_interest"

    async def _handle_program_inquiry(self, ig_username: str, message_text: str,
                                      subscriber_id: str, first_name: str, last_name: str,
                                      timestamp: str) -> bool:
        """Handle program information inquiries."""
        try:
            prompt = f"""
            A potential client is asking about Shannon's coaching programs.
            
            CLIENT: {first_name}
            INQUIRY: "{message_text}"
            
            Generate a response that:
            1. Thanks them for their interest
            2. Provides overview of coaching services (1:1 coaching, personalized plans)
            3. Mentions key benefits (plant-based nutrition, sustainable results)
            4. Explains the personalized approach
            5. Suggests a consultation call to discuss their specific needs
            6. Uses Shannon's welcoming and professional tone
            
            Keep it informative but not overwhelming.
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
                    prompt_type="onboarding_program_inquiry"
                )

                if review_id:
                    logger.info(
                        f"[Onboarding] Queued program inquiry response for {ig_username}")

                    # Mark as sales lead
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        lead_status="program_inquiry",
                        inquiry_date=datetime.now().isoformat(),
                        sales_stage="information"
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Onboarding] Program inquiry error: {e}")
            return False

    async def _handle_pricing_question(self, ig_username: str, message_text: str,
                                       subscriber_id: str, first_name: str, last_name: str,
                                       timestamp: str) -> bool:
        """Handle pricing and investment questions."""
        try:
            prompt = f"""
            A potential client is asking about pricing for Shannon's coaching.
            
            CLIENT: {first_name}
            QUESTION: "{message_text}"
            
            Generate a response that:
            1. Acknowledges their pricing question
            2. Explains that pricing is personalized based on their needs
            3. Mentions the value and transformation focus
            4. Offers a free consultation to discuss their goals and pricing
            5. Emphasizes the investment in their health and results
            6. Uses Shannon's value-focused but approachable tone
            
            Keep it positive and value-oriented.
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
                    prompt_type="onboarding_pricing_question"
                )

                if review_id:
                    logger.info(
                        f"[Onboarding] Queued pricing question response for {ig_username}")

                    # High-intent lead
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        lead_status="pricing_inquiry",
                        inquiry_date=datetime.now().isoformat(),
                        sales_stage="consideration",
                        lead_priority="high"
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Onboarding] Pricing question error: {e}")
            return False

    async def _handle_trial_interest(self, ig_username: str, message_text: str,
                                     subscriber_id: str, first_name: str, last_name: str,
                                     timestamp: str) -> bool:
        """Handle trial or free period interest."""
        try:
            prompt = f"""
            A potential client is interested in trying a trial or free period.
            
            CLIENT: {first_name}
            MESSAGE: "{message_text}"
            
            Generate a response that:
            1. Expresses excitement about their interest
            2. Explains the free consultation process
            3. Mentions what they'll get in the trial/consultation
            4. Provides clear next steps to book
            5. Creates urgency without being pushy
            6. Uses Shannon's enthusiastic and encouraging tone
            
            Keep it motivating and action-oriented.
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
                    prompt_type="onboarding_trial_interest"
                )

                if review_id:
                    logger.info(
                        f"[Onboarding] Queued trial interest response for {ig_username}")

                    # Very high-intent lead
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        lead_status="trial_interest",
                        inquiry_date=datetime.now().isoformat(),
                        sales_stage="trial",
                        lead_priority="very_high"
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Onboarding] Trial interest error: {e}")
            return False

    async def _handle_booking_request(self, ig_username: str, message_text: str,
                                      subscriber_id: str, first_name: str, last_name: str,
                                      timestamp: str) -> bool:
        """Handle booking requests for consultations."""
        try:
            prompt = f"""
            A potential client wants to book a consultation call.
            
            CLIENT: {first_name}
            REQUEST: "{message_text}"
            
            Generate a response that:
            1. Shows enthusiasm for their booking request
            2. Provides clear booking instructions or link
            3. Explains what to expect in the consultation
            4. Mentions any preparation they should do
            5. Confirms the next steps
            6. Uses Shannon's professional but warm tone
            
            Keep it clear and actionable.
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
                    prompt_type="onboarding_booking_request"
                )

                if review_id:
                    logger.info(
                        f"[Onboarding] Queued booking request response for {ig_username}")

                    # Conversion-ready lead
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        lead_status="booking_requested",
                        inquiry_date=datetime.now().isoformat(),
                        sales_stage="conversion",
                        lead_priority="urgent"
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Onboarding] Booking request error: {e}")
            return False

    async def _handle_ready_to_start(self, ig_username: str, message_text: str,
                                     subscriber_id: str, first_name: str, last_name: str,
                                     timestamp: str) -> bool:
        """Handle messages from people ready to start coaching."""
        try:
            prompt = f"""
            A potential client is ready to start coaching right away.
            
            CLIENT: {first_name}
            MESSAGE: "{message_text}"
            
            Generate a response that:
            1. Celebrates their commitment to getting started
            2. Outlines the immediate next steps
            3. Explains the onboarding process
            4. Sets expectations for timeline
            5. Provides contact information or booking links
            6. Uses Shannon's excited and supportive tone
            
            Keep it organized and action-focused.
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
                    prompt_type="onboarding_ready_to_start"
                )

                if review_id:
                    logger.info(
                        f"[Onboarding] Queued ready-to-start response for {ig_username}")

                    # Immediate conversion opportunity
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        lead_status="ready_to_start",
                        inquiry_date=datetime.now().isoformat(),
                        sales_stage="conversion",
                        lead_priority="immediate"
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Onboarding] Ready to start error: {e}")
            return False

    async def _handle_general_interest(self, ig_username: str, message_text: str,
                                       subscriber_id: str, first_name: str, last_name: str,
                                       timestamp: str) -> bool:
        """Handle general coaching interest."""
        try:
            prompt = f"""
            Someone is showing general interest in coaching.
            
            POTENTIAL CLIENT: {first_name}
            MESSAGE: "{message_text}"
            
            Generate a response that:
            1. Thanks them for their interest
            2. Asks about their specific goals or challenges
            3. Briefly explains how Shannon can help
            4. Offers a free consultation to learn more
            5. Keeps the conversation going naturally
            6. Uses Shannon's friendly and engaging tone
            
            Keep it conversational and inviting.
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
                    prompt_type="onboarding_general_interest"
                )

                if review_id:
                    logger.info(
                        f"[Onboarding] Queued general interest response for {ig_username}")

                    # New lead to nurture
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        lead_status="general_interest",
                        inquiry_date=datetime.now().isoformat(),
                        sales_stage="awareness",
                        lead_priority="medium"
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Onboarding] General interest error: {e}")
            return False
