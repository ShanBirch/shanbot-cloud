"""
Core Action Handler
==================
Central orchestrator for all webhook actions and message processing.
"""

from action_handlers.ad_response_handler import AdResponseHandler
from .trainerize_action_handler import TrainerizeActionHandler
from .calorie_action_handler import CalorieActionHandler
from .form_check_handler import FormCheckHandler
from webhook_handlers import (
    get_ai_response, get_user_data, update_analytics_data,
    call_gemini_with_retry, update_manychat_fields, build_member_chat_prompt
)
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Import from the main webhook_handlers (not the app one)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("shanbot_core")


class CoreActionHandler:
    """Central handler for all webhook actions and message processing."""

    @staticmethod
    async def detect_and_handle_action(ig_username: str, message_text: str, subscriber_id: str,
                                       first_name: str, last_name: str, user_message_timestamp_iso: str, fb_ad: bool = False) -> bool:
        """Main action detection and handling logic."""
        try:
            logger.info(
                f"[CoreAction] Processing message from {ig_username}: '{message_text[:100]}...'")

            # Persist the incoming USER message to the unified messages table immediately
            try:
                from app.dashboard_modules.dashboard_sqlite_utils import add_message_to_history
                add_message_to_history(ig_username=ig_username, message_type='user',
                                       message_text=message_text or '', message_timestamp=user_message_timestamp_iso)
            except Exception as persist_e:
                logger.warning(
                    f"[CoreAction] Could not append user message to messages for {ig_username}: {persist_e}")

            # Get user data and current state
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            conversation_history = metrics.get('conversation_history', [])

            # Check for ad response first
            is_ad_response, scenario, confidence = await AdResponseHandler.is_ad_response(
                ig_username, message_text, metrics
            )

            logger.info(
                f"[CoreAction] Ad detection result for {ig_username}: is_ad={is_ad_response}, scenario={scenario}, confidence={confidence}%")

            if is_ad_response and confidence >= 50:
                logger.info(
                    f"[CoreAction] Detected ad response from {ig_username} (confidence: {confidence}%)")

                # Update user state for ad flow
                update_analytics_data(ig_username, "", "", subscriber_id, first_name, last_name,
                                      is_in_ad_flow=True, ad_scenario=scenario, lead_source='plant_based_challenge')

                # Handle ad response
                success = await AdResponseHandler.handle_ad_response(
                    ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso,
                    scenario, metrics, fb_ad
                )

                if success:
                    logger.info(
                        f"[CoreAction] Successfully handled ad response for {ig_username}")
                    return True
                else:
                    logger.warning(
                        f"[CoreAction] Ad response handling failed for {ig_username}")

            # Check for Trainerize actions
            trainerize_handled = await TrainerizeActionHandler.handle_trainerize_actions(
                ig_username, message_text, subscriber_id, first_name, last_name
            )

            if trainerize_handled:
                logger.info(
                    f"[CoreAction] Handled Trainerize action for {ig_username}")
                return True

            # Check for calorie tracking
            calorie_handled = await CalorieActionHandler.handle_calorie_actions(
                ig_username, message_text, subscriber_id, first_name, last_name
            )

            if calorie_handled:
                logger.info(
                    f"[CoreAction] Handled calorie action for {ig_username}")
                return True

            # Check for form check videos
            form_check_handled = await FormCheckHandler.handle_form_check(
                ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso
            )

            if form_check_handled:
                logger.info(
                    f"[CoreAction] Handled form check for {ig_username}")
                return True

            # No specific action detected, handle as general conversation
            logger.info(
                f"[CoreAction] No specific action detected for {ig_username}, processing as general conversation")
            return await CoreActionHandler._handle_general_conversation(
                ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso, fb_ad
            )

        except Exception as e:
            logger.error(
                f"[CoreAction] Error processing action for {ig_username}: {e}")
            return False

    @staticmethod
    async def run_core_processing_after_buffer(ig_username: str, message_text: str, subscriber_id: str,
                                               first_name: str, last_name: str, user_message_timestamp_iso: str) -> None:
        """Run core processing after message buffering."""
        try:
            logger.info(
                f"[CoreBuffer] Running buffered processing for {ig_username}")

            # Get user data to check if they're already in ad flow
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            is_in_ad_flow = metrics.get('is_in_ad_flow', False)

            logger.info(
                f"[CoreBuffer] User {ig_username} ad flow status: is_in_ad_flow={is_in_ad_flow}")

            # If user is already in ad flow, handle as ad response
            if is_in_ad_flow:
                logger.info(
                    f"[CoreBuffer] User {ig_username} is already in ad flow - routing to ad response handler")

                scenario = metrics.get('ad_scenario', 1)
                success = await AdResponseHandler.handle_ad_response(
                    ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso,
                    scenario, metrics, False  # fb_ad parameter
                )

                if success:
                    logger.info(
                        f"[CoreBuffer] Successfully handled ad response for {ig_username}")
                    return
                else:
                    logger.warning(
                        f"[CoreBuffer] Ad response handling failed for {ig_username}")

            # Otherwise, run the main action detection
            handled = await CoreActionHandler.detect_and_handle_action(
                ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso
            )

            if not handled:
                logger.warning(
                    f"[CoreBuffer] No handler processed message for {ig_username}")

        except Exception as e:
            logger.error(
                f"[CoreBuffer] Error in buffered processing for {ig_username}: {e}")

    @staticmethod
    async def _handle_general_conversation(ig_username: str, message_text: str, subscriber_id: str,
                                           first_name: str, last_name: str, user_message_timestamp_iso: str, fb_ad: bool = False) -> bool:
        """Handle general conversation that doesn't match specific actions."""
        try:
            # Debug logging to see what we received
            logger.info(
                f"[CoreGeneral] Called with ig_username='{ig_username}', message_text='{message_text}', subscriber_id='{subscriber_id}', first_name='{first_name}', last_name='{last_name}'")

            # Process media URLs in the message before building prompt
            processed_message_text = message_text
            try:
                from webhook_handlers import process_conversation_for_media
                processed_message_text = process_conversation_for_media(
                    message_text)
                if processed_message_text != message_text:
                    logger.info(
                        f"[CoreGeneral] Processed media in message for {ig_username}: {processed_message_text[:100]}...")
            except Exception as e:
                logger.error(
                    f"[CoreGeneral] Error processing media for {ig_username}: {e}")
                processed_message_text = message_text  # Fallback to original

            # Get user data for context
            _, metrics, _ = get_user_data(ig_username, subscriber_id)

            # Fetch appropriate few-shot examples (vegan or general)
            few_shot_examples = []
            try:
                from app.dashboard_modules.dashboard_sqlite_utils import is_user_in_vegan_flow, get_vegan_few_shot_examples, get_good_few_shot_examples

                if is_user_in_vegan_flow(ig_username):
                    few_shot_examples = get_vegan_few_shot_examples(limit=50)
                    logger.info(
                        f"[CoreGeneral] Using {len(few_shot_examples)} vegan few-shot examples for {ig_username}")
                else:
                    few_shot_examples = get_good_few_shot_examples(limit=50)
                    logger.info(
                        f"[CoreGeneral] Using {len(few_shot_examples)} general few-shot examples for {ig_username}")
            except Exception as e:
                logger.warning(
                    f"[CoreGeneral] Could not fetch few-shot examples for {ig_username}: {e}")

            # Use the dedicated prompt builder function
            prompt, prompt_type = build_member_chat_prompt(
                client_data=metrics,
                current_message=processed_message_text,
                full_name=f"{first_name} {last_name}".strip(),
                few_shot_examples=few_shot_examples
            )

            response = await get_ai_response(prompt)

            if response:
                # Ensure we have a valid ig_username before queuing
                if not ig_username or ig_username.strip() == '':
                    ig_username = f"user_{subscriber_id}"
                    logger.warning(
                        f"[CoreGeneral] Using fallback ig_username '{ig_username}' for general conversation")

                # Queue response for review
                from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
                review_id = add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=processed_message_text,
                    incoming_message_timestamp=user_message_timestamp_iso,
                    generated_prompt_text=prompt,
                    proposed_response_text=response,
                    prompt_type=prompt_type
                )

                if review_id:
                    logger.info(
                        f"[CoreGeneral] Queued general response (ID: {review_id}) for {ig_username}")

                    # Update analytics
                    update_analytics_data(
                        ig_username, processed_message_text, response, subscriber_id, first_name, last_name, fb_ad=fb_ad)
                    return True
                else:
                    logger.error(
                        f"[CoreGeneral] Failed to queue response for {ig_username}")
            else:
                logger.error(
                    f"[CoreGeneral] No response generated for {ig_username}")

            return False

        except Exception as e:
            logger.error(
                f"[CoreGeneral] Error handling general conversation for {ig_username}: {e}", exc_info=True)
            return False

    @staticmethod
    async def _dedup_and_rewrite_if_needed(ig_username: str, subscriber_id: str, generated_response: str) -> str:
        """Check for duplicate questions and rewrite if needed."""
        try:
            recent_questions = CoreActionHandler._get_recent_ai_questions(
                ig_username)

            if not recent_questions:
                return generated_response

            # Check if response contains similar questions
            dedup_prompt = f"""
            Recent AI questions to this user:
            {chr(10).join(recent_questions)}
            
            Current response:
            {generated_response}
            
            If the current response asks questions very similar to recent ones, rewrite it to:
            1. Acknowledge their previous responses if relevant
            2. Ask different, more progressive questions
            3. Move the conversation forward
            
            If no similar questions, return the original response unchanged.
            
            Return only the final response text.
            """

            rewritten = await call_gemini_with_retry("gemini-2.5-flash-lite", dedup_prompt)
            return rewritten if rewritten else generated_response

        except Exception as e:
            logger.error(
                f"[CoreDedup] Error in deduplication for {ig_username}: {e}")
            return generated_response

    @staticmethod
    def _get_recent_ai_questions(ig_username: str, limit: int = 3) -> list:
        """Get recent AI questions for duplicate detection."""
        from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT proposed_response_text 
                FROM response_review_queue 
                WHERE user_ig_username = ? 
                AND proposed_response_text LIKE '%?%'
                ORDER BY created_at DESC 
                LIMIT ?
            """, (ig_username, limit))

            rows = cursor.fetchall()

            questions = []
            for row in rows:
                response_text = row[0]
                # Extract questions (simple heuristic)
                sentences = response_text.split('.')
                for sentence in sentences:
                    if '?' in sentence:
                        questions.append(sentence.strip() + '?')

            return questions[:limit]

        except Exception as e:
            logger.error(
                f"[CoreQuestions] Error getting recent questions for {ig_username}: {e}")
            return []
        finally:
            if conn:
                conn.close()
