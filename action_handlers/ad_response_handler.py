
from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
from app import prompts
from app.general_utils import get_melbourne_time_str, format_conversation_history, clean_and_dedupe_history
from app.ai_handler import get_ai_response
from utilities import process_conversation_for_media
import logging
from typing import Dict, Any

# Import from the main webhook_handlers (not the app one)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("shanbot_ad_handler")


class AdResponseHandler:
    """Handles responses to Instagram/Facebook ads."""

    @staticmethod
    async def is_ad_response(ig_username: str, message_text: str, metrics: Dict) -> tuple[bool, int, int]:
        """Determine if a message is a response to an ad. Returns (is_ad, scenario, confidence)."""
        logger.info(
            f"[AdResponse] Analyzing message from {ig_username}: '{message_text}' for ad intent")
        text = message_text.lower()
        scenario = 3  # Default to plant_based
        confidence = 0

        ad_keywords = ["challenge", "vegan challenge",
                       "vegetarian challenge", "learn more", "get started"]

        # Check for vegan challenge (with typo tolerance)
        if ("vegan" in text and "challeng" in text) or "vegan challenge" in text:
            logger.info(
                f"[AdResponse] Found vegan challenge reference in text")
            scenario = 1
            confidence = 90
        elif ("vegetarian" in text and "challeng" in text) or "vegetarian challenge" in text:
            logger.info(
                f"[AdResponse] Found vegetarian challenge reference in text")
            scenario = 2
            confidence = 90
        # Check for vegan + program/join/weight loss combinations
        elif "vegan" in text and any(program_word in text for program_word in ["program", "join", "weight loss", "weightloss", "fitness", "training"]):
            logger.info(
                f"[AdResponse] Found vegan + program/join/weight loss reference in text")
            scenario = 1
            confidence = 85
        elif "vegetarian" in text and any(program_word in text for program_word in ["program", "join", "weight loss", "weightloss", "fitness", "training"]):
            logger.info(
                f"[AdResponse] Found vegetarian + program/join/weight loss reference in text")
            scenario = 2
            confidence = 85
        elif any(keyword in text for keyword in ad_keywords):
            matched_keywords = [kw for kw in ad_keywords if kw in text]
            logger.info(f"[AdResponse] Found ad keywords: {matched_keywords}")
            scenario = 3
            confidence = 80

        # Check for short first messages (common for ad responses)
        conv_history_len = len(metrics.get('conversation_history', []))
        if confidence == 0 and conv_history_len <= 1 and len(message_text.split()) < 10:
            logger.info(
                f"[AdResponse] Short first message detected (history: {conv_history_len}, words: {len(message_text.split())})")
            confidence = 40

        is_ad = confidence >= 50

        logger.info(
            f"[AdResponse] Final result: is_ad={is_ad}, scenario={scenario}, confidence={confidence}%")

        return is_ad, scenario, confidence

    @staticmethod
    async def handle_ad_response(ig_username: str, message_text: str, subscriber_id: str,
                                 first_name: str, last_name: str, user_message_timestamp_iso: str,
                                 scenario: int, metrics: dict, fb_ad: bool = False) -> bool:
        """Handle ad response by generating a scripted reply."""
        try:
            logger.info(
                f"[AdResponse] Handling ad response for {ig_username} with scenario {scenario}")

            # Prepare data for prompt
            current_time = get_melbourne_time_str()
            bio_context = metrics.get(
                'client_analysis', {}).get('profile_bio', '')

            # Process media URLs in the message before building conversation
            processed_message_text = message_text
            try:
                # Import the media processing function
                processed_message_text = process_conversation_for_media(
                    message_text)
                if processed_message_text != message_text:
                    logger.info(
                        f"[AdResponse] Processed media in message for {ig_username}: {processed_message_text[:100]}...")
            except Exception as e:
                logger.error(
                    f"[AdResponse] Error processing media for {ig_username}: {e}")
                processed_message_text = message_text  # Fallback to original

            # Debug conversation history
            conversation_history_raw = metrics.get('conversation_history', [])
            logger.info(
                f"[AdResponse] Raw conversation history for {ig_username}: {len(conversation_history_raw)} entries")
            logger.info(
                f"[AdResponse] History sample: {conversation_history_raw[-3:] if conversation_history_raw else 'EMPTY'}")

            # Clean and dedupe for clearer prompting
            conversation_history = clean_and_dedupe_history(
                conversation_history_raw, max_items=40)

            full_conversation = format_conversation_history(
                conversation_history) + f"\\nUser: {processed_message_text}"
            logger.info(
                f"[AdResponse] Formatted conversation: {full_conversation[:200]}...")

            script_state = metrics.get('ad_script_state', 'step1')

            challenge_types = {1: 'vegan', 2: 'vegetarian', 3: 'plant_based'}
            challenge_type = challenge_types.get(scenario, 'plant_based')

            # Build prompt using ad response template
            prompt = prompts.COMBINED_AD_RESPONSE_PROMPT_TEMPLATE.format(
                current_melbourne_time_str=current_time,
                ig_username=ig_username,
                script_state=script_state,
                ad_scenario=scenario,
                full_conversation=full_conversation
            )

            # Generate AI response
            ai_response = await get_ai_response(prompt)

            if not ai_response:
                logger.error(
                    f"[AdResponse] Failed to generate AI response for {ig_username}")
                return False

            # ✅ CRITICAL: Tag user as being in ad flow so subsequent messages use this flow
            try:
                import sqlite3
                conn = sqlite3.connect(
                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite")
                cursor = conn.cursor()

                # Check if user exists, if not create basic entry
                cursor.execute(
                    "SELECT ig_username FROM users WHERE ig_username = ?", (ig_username,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO users (ig_username, subscriber_id, lead_source, is_in_ad_flow, ad_script_state, ad_scenario) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (ig_username, subscriber_id, 'paid_plant_based_challenge', True, 'step1', scenario))
                    logger.info(
                        f"[AdResponse] Created new user entry for {ig_username} with ad flow flags")
                else:
                    # Advance script state based on user interaction
                    current_state = metrics.get('ad_script_state', 'step1')
                    next_state = AdResponseHandler._advance_script_state(
                        current_state, message_text)

                    logger.info(
                        f"[AdResponse] Executing UPDATE for {ig_username} with values: lead_source=paid_plant_based_challenge, is_in_ad_flow=True, ad_script_state={next_state}, ad_scenario={scenario}")

                    cursor.execute("""
                        UPDATE users 
                        SET lead_source = ?, is_in_ad_flow = ?, ad_script_state = ?, ad_scenario = ? 
                        WHERE ig_username = ?
                    """, ('paid_plant_based_challenge', True, next_state, scenario, ig_username))

                    rows_affected = cursor.rowcount
                    logger.info(
                        f"[AdResponse] UPDATE affected {rows_affected} rows for {ig_username}")
                    logger.info(
                        f"[AdResponse] Updated {ig_username}: {current_state} → {next_state}")

                conn.commit()
                logger.info(
                    f"[AdResponse] Database commit completed for {ig_username}")
                conn.close()
                logger.info(
                    f"[AdResponse] Successfully tagged {ig_username} for ad flow (scenario={scenario})")
            except Exception as e:
                logger.error(
                    f"[AdResponse] Failed to tag {ig_username} for ad flow: {e}")

            # Ensure we have a valid ig_username before queuing
            if not ig_username or ig_username.strip() == '':
                ig_username = f"user_{subscriber_id}"
                logger.warning(
                    f"[AdResponse] Using fallback ig_username '{ig_username}' for ad response")

            # Check auto mode status for ad responses
            should_auto_process = False
            try:
                from app.dashboard_modules.auto_mode_state import is_vegan_ad_auto_mode_active

                # Check if user is a paying client (should always be manual)
                client_status = metrics.get('client_status', 'Not a Client')
                is_paying_client = client_status in [
                    'Trial Member', 'Paying Member', 'Active Client']

                if is_paying_client:
                    logger.info(
                        f"[AdResponse] {ig_username} is a paying client - manual review required")
                    should_auto_process = False
                elif is_vegan_ad_auto_mode_active():
                    logger.info(
                        f"[AdResponse] 🌱 VEGAN AD AUTO MODE ACTIVE - Auto-processing ad response for {ig_username}")
                    should_auto_process = True
                else:
                    logger.info(
                        f"[AdResponse] Vegan ad auto mode OFF - manual review required for {ig_username}")
                    should_auto_process = False

            except ImportError:
                logger.warning(
                    "Could not import auto_mode_state, assuming manual review for ad response")
                should_auto_process = False

            # Persist the incoming USER message immediately
            try:
                from app.dashboard_modules.dashboard_sqlite_utils import add_message_to_history
                add_message_to_history(ig_username=ig_username, message_type='user',
                                       message_text=message_text or '', message_timestamp=user_message_timestamp_iso)
            except Exception as persist_e:
                logger.warning(
                    f"[AdResponse] Could not append user message for {ig_username}: {persist_e}")

            # Add to review queue with appropriate status
            review_status = 'auto_scheduled' if should_auto_process else 'pending_review'
            review_id = add_response_to_review_queue(
                user_ig_username=ig_username,
                user_subscriber_id=subscriber_id,
                incoming_message_text=processed_message_text,
                incoming_message_timestamp=user_message_timestamp_iso,
                generated_prompt_text=prompt,
                proposed_response_text=ai_response,
                prompt_type="facebook_ad_response",
                status=review_status
            )

            # If auto mode is active, schedule the response
            if should_auto_process and review_id:
                try:
                    # Create scheduled response entry directly
                    from datetime import datetime, timedelta
                    import random

                    # Calculate delay (30-90 seconds for immediate response)
                    delay_seconds = random.randint(30, 90)
                    scheduled_time = datetime.now() + timedelta(seconds=delay_seconds)

                    # Insert into scheduled_responses table
                    conn = sqlite3.connect(
                        r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite")
                    cursor = conn.cursor()

                    # Ensure table exists
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS scheduled_responses (
                            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            review_id INTEGER,
                            user_ig_username TEXT,
                            user_subscriber_id TEXT,
                            response_text TEXT,
                            incoming_message_text TEXT,
                            incoming_message_timestamp TEXT,
                            user_response_time TEXT,
                            calculated_delay_minutes REAL,
                            scheduled_send_time TEXT,
                            status TEXT DEFAULT 'scheduled',
                            user_notes TEXT,
                            manual_context TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    cursor.execute("""
                        INSERT INTO scheduled_responses (
                            review_id, user_ig_username, user_subscriber_id, response_text,
                            incoming_message_text, incoming_message_timestamp, user_response_time,
                            calculated_delay_minutes, scheduled_send_time, status, user_notes, manual_context
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        review_id,
                        ig_username,
                        subscriber_id,
                        ai_response,
                        processed_message_text,
                        user_message_timestamp_iso,
                        user_message_timestamp_iso,
                        delay_seconds / 60.0,  # Convert to minutes
                        scheduled_time.isoformat(),
                        'scheduled',
                        '[AUTO-SCHEDULED] Vegan Ad Response',
                        ''
                    ))

                    conn.commit()
                    conn.close()

                    logger.info(
                        f"[AdResponse] ✅ Auto-scheduled ad response for {ig_username} (Review ID: {review_id})")
                    logger.info(
                        f"[AdResponse] 📅 Will send at: {scheduled_time.strftime('%H:%M:%S')}")

                except Exception as e:
                    logger.error(
                        f"[AdResponse] Error scheduling auto response: {e}")
            elif review_id:
                logger.info(
                    f"[AdResponse] Queued ad response for manual review (Review ID: {review_id})")
            else:
                logger.error(
                    f"[AdResponse] ❌ Failed to queue ad response for {ig_username}")

            # Also add AI response to conversation history for complete context
            try:
                from datetime import datetime, timedelta
                # Calculate AI response timestamp (user timestamp + realistic delay)
                import random
                try:
                    user_msg_timestamp = datetime.fromisoformat(
                        user_message_timestamp_iso.split('+')[0])
                    delay_seconds = random.randint(
                        30, 90)  # Realistic response delay
                    ai_response_timestamp = (
                        user_msg_timestamp + timedelta(seconds=delay_seconds)).isoformat()
                except (ValueError, AttributeError):
                    ai_response_timestamp = datetime.now().isoformat()

                # Save AI response to messages table for conversation history (use same format as user messages)
                conn = sqlite3.connect(
                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO messages (ig_username, subscriber_id, timestamp, sender, message)
                    VALUES (?, ?, ?, ?, ?)
                """, (ig_username, subscriber_id, ai_response_timestamp, 'ai', ai_response))
                conn.commit()
                conn.close()
                logger.info(
                    f"[AdResponse] Added AI response to conversation history for {ig_username}")
            except Exception as e:
                logger.error(
                    f"[AdResponse] Failed to add AI response to conversation history: {e}")

            return True
        except Exception as e:
            logger.error(
                f"[AdResponse] Error handling ad response for {ig_username}: {e}", exc_info=True)
            return False

    @staticmethod
    def _advance_script_state(current_state: str, message_text: str) -> str:
        """Advance script state based on user response patterns."""
        try:
            message_lower = message_text.lower()

            # State progression logic for vegan challenge flow
            if current_state == 'step1':
                # After initial interest, move to step2 (goal gathering)
                return 'step2'

            elif current_state == 'step2':
                # After they share goals/struggles, move to step3 (call proposal)
                if len(message_text.split()) > 3:  # Substantial response about goals
                    return 'step3'
                return 'step2'  # Stay in step2 if response too short

            elif current_state == 'step3':
                # After call proposal, check their response
                if any(word in message_lower for word in ['yes', 'sure', 'okay', 'ok', 'sounds good', 'definitely']):
                    return 'step4'  # They agreed to call - send booking link
                elif any(word in message_lower for word in ['no', 'not really', 'cant', 'busy', 'maybe later']):
                    return 'step2'  # They declined call - back to gathering info
                return 'step3'  # Stay in step3 if unclear response

            elif current_state == 'step4':
                # After booking link sent, conversation complete or back to step2 for more info
                if any(word in message_lower for word in ['booked', 'scheduled', 'thanks', 'thank you']):
                    return 'completed'
                return 'step2'  # Continue gathering info if they have questions

            elif current_state == 'completed':
                # Keep them in completed state
                return 'completed'

            else:
                # Default fallback
                return 'step2'

        except Exception as e:
            logger.error(f"Error advancing script state: {e}")
            return current_state  # Stay in current state if error
