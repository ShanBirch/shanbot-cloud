"""
Action Router
============
Central router that coordinates between all action handlers.
"""

from action_handlers.ad_response_handler import AdResponseHandler
from action_handlers.core_action_handler import CoreActionHandler
from action_handlers.calorie_action_handler import CalorieActionHandler
from services.message_buffer import MessageBuffer
from webhook_handlers import get_user_data
from app.dashboard_modules.dashboard_sqlite_utils import get_user_metrics_json, is_user_in_calorie_flow
import logging
from typing import Dict, Any, Optional, Tuple
import sys
import os

# Import from the main webhook_handlers (not the app one)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("shanbot_router")


class ActionRouter:
    """Central router for coordinating webhook actions."""

    @staticmethod
    async def route_webhook_message(ig_username: str, message_text: str, subscriber_id: str,
                                    first_name: str, last_name: str, user_message_timestamp_iso: str, fb_ad: bool = False) -> Dict[str, Any]:
        """Route incoming webhook message to appropriate handlers."""
        try:
            logger.info(
                f"[Router] Routing message from {ig_username}: '{message_text[:50]}...'")

            # --- Early Ad Response Override ---
            # If this looks like a high-confidence ad response (e.g., "vegan challenge"),
            # handle it immediately before any calorie-flow overrides.
            try:
                is_ad_response, scenario, ad_confidence = await AdResponseHandler.is_ad_response(
                    ig_username, message_text, {"conversation_history": []}
                )
                if is_ad_response and ad_confidence >= 85:
                    logger.info(
                        f"[Router] High-confidence ad response detected for {ig_username} (confidence: {ad_confidence}%) - overriding calorie flow checks")
                    # Fetch metrics to pass along if available
                    _, metrics_override, _ = get_user_data(ig_username, subscriber_id)
                    success = await AdResponseHandler.handle_ad_response(
                        ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso,
                        scenario, metrics_override, fb_ad
                    )
                    return {
                        "status": "processed_ad_response_override",
                        "success": success
                    }
            except Exception as e:
                logger.warning(f"[Router] Early ad override check failed for {ig_username}: {e}")

            # --- Calorie Flow Override ---
            # If user is in the calorie flow, all messages go to the calorie handler first.
            if is_user_in_calorie_flow(ig_username):
                handled = await CalorieActionHandler.handle_calorie_actions(
                    ig_username, message_text, subscriber_id, first_name, last_name
                )
                return {
                    "status": "processed_in_calorie_flow",
                    "success": handled
                }

            # Strict override: calorie tracking trigger must bypass ad flow
            try:
                normalized = ' '.join(
                    (message_text or '').strip().lower().split())
                if normalized in ('track my cals', 'track my cals plz'):
                    # If calorie setup is pending, process directly and skip buffering entirely
                    try:
                        metrics_json = get_user_metrics_json(ig_username)
                        if isinstance(metrics_json, dict) and metrics_json.get('pending_calorie_setup'):
                            handled = await CalorieActionHandler.handle_calorie_actions(
                                ig_username, message_text, subscriber_id, first_name, last_name
                            )
                            return {
                                "status": "processed_calorie_pending_direct",
                                "success": handled
                            }
                    except Exception:
                        pass
                    handled = await CalorieActionHandler.handle_calorie_actions(
                        ig_username, message_text, subscriber_id, first_name, last_name
                    )
                    return {
                        "status": "processed_calorie_trigger",
                        "success": handled
                    }

                # If the user is in pending calorie setup, route ALL messages to calorie handler to complete setup
                try:
                    metrics_json = get_user_metrics_json(ig_username)
                    if isinstance(metrics_json, dict) and metrics_json.get('pending_calorie_setup'):
                        handled = await CalorieActionHandler.handle_calorie_actions(
                            ig_username, message_text, subscriber_id, first_name, last_name
                        )
                        return {
                            "status": "processed_calorie_pending",
                            "success": handled
                        }
                except Exception:
                    pass
                # Bypass ad flow for media URL only if user is already in calorie flow (pending or active)
                if isinstance(message_text, str) and 'lookaside.fbsbx.com/ig_messaging_cdn/' in message_text:
                    try:
                        _, m, _ = get_user_data(ig_username, subscriber_id)
                        in_flow = False
                        metrics_json = m.get('metrics_json') or {}
                        if isinstance(metrics_json, dict):
                            in_flow = bool(metrics_json.get(
                                'pending_calorie_setup', False))
                        if not in_flow:
                            # Also check DB flag if present
                            try:
                                from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
                                conn = get_db_connection()
                                cur = conn.cursor()
                                cur.execute(
                                    'SELECT is_in_calorie_flow FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                                row = cur.fetchone()
                                if row and (row[0] == 1 or row[0] == True):
                                    in_flow = True
                            except Exception:
                                pass
                            finally:
                                try:
                                    conn.close()
                                except Exception:
                                    pass
                        if in_flow:
                            handled = await CalorieActionHandler.handle_calorie_actions(
                                ig_username, message_text, subscriber_id, first_name, last_name
                            )
                            return {
                                "status": "processed_food_media",
                                "success": handled
                            }
                    except Exception:
                        pass
            except Exception:
                pass

            # Get user data to determine routing strategy
            _, metrics, _ = get_user_data(ig_username, subscriber_id)

            # --- Check if user is already in ad flow ---
            is_in_ad_flow = metrics.get('is_in_ad_flow', False)
            logger.info(
                f"[Router] User {ig_username} ad flow status: is_in_ad_flow={is_in_ad_flow}")
            if is_in_ad_flow:
                logger.info(
                    f"[Router] User {ig_username} is already in ad flow - routing to ad response handler")

                # Get their ad scenario and state
                scenario = metrics.get('ad_scenario', 1)

                success = await AdResponseHandler.handle_ad_response(
                    ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso,
                    scenario, metrics, fb_ad
                )
                return {
                    "status": "processed_existing_ad_flow",
                    "success": success
                }

            # --- Ad Response Detection (for new ad responses) ---
            try:
                is_ad_response, scenario, ad_confidence = await AdResponseHandler.is_ad_response(
                    ig_username, message_text, metrics
                )

                logger.info(
                    f"[Router] Ad detection complete for {ig_username}: is_ad={is_ad_response}, confidence={ad_confidence}%")

                if is_ad_response:
                    logger.info(
                        f"[Router] Detected ad response for {ig_username} (confidence: {ad_confidence}%) - processing immediately")
                    success = await AdResponseHandler.handle_ad_response(
                        ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso,
                        scenario, metrics, fb_ad
                    )
                    return {
                        "status": "processed_ad_response",
                        "success": success
                    }
            except Exception as e:
                logger.error(
                    f"[Router] Error in ad detection for {ig_username}: {e}")
                # Continue to buffering if ad detection fails

            # Check if user should use message buffering
            if ActionRouter._should_use_buffering(metrics, message_text):
                logger.info(
                    f"[Router] Using message buffering for {ig_username}")

                # Prepare message data for buffering
                message_data = {
                    'ig_username': ig_username,
                    'text': message_text,
                    'subscriber_id': subscriber_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'user_message_timestamp_iso': user_message_timestamp_iso,
                    'timestamp': user_message_timestamp_iso,
                    'fb_ad': fb_ad
                }

                # Add to buffer (this will schedule processing)
                MessageBuffer.add_to_message_buffer(
                    subscriber_id, message_data)

                return {
                    "status": "buffered",
                    "message": "Message added to buffer for processing",
                    "buffer_stats": MessageBuffer.get_buffer_stats(subscriber_id)
                }
            else:
                # Process immediately
                logger.info(
                    f"[Router] Processing immediately for {ig_username}")

                success = await CoreActionHandler.detect_and_handle_action(
                    ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso, fb_ad
                )

                return {
                    "status": "processed",
                    "success": success,
                    "message": "Message processed immediately"
                }

        except Exception as e:
            logger.error(
                f"[Router] Error routing message for {ig_username}: {e}")
            return {
                "status": "error",
                "message": f"Error processing message: {str(e)}"
            }

    @staticmethod
    def _should_use_buffering(metrics: Dict, message_text: str) -> bool:
        """Determine if message should use buffering."""
        try:
            # Check user preferences
            buffer_enabled = metrics.get('use_message_buffering', True)

            if not buffer_enabled:
                return False

            # Check message characteristics
            message_length = len(message_text.strip())

            # Use buffering for short messages (likely quick responses)
            if message_length < 200:
                return True

            # Don't buffer long messages (likely detailed requests)
            if message_length > 500:
                return False

            # Check if user is in active conversation
            conversation_history = metrics.get('conversation_history', [])
            if len(conversation_history) > 0:
                # Get last message timestamp
                last_message = conversation_history[-1]
                last_timestamp = last_message.get('timestamp')

                if last_timestamp:
                    from datetime import datetime, timedelta
                    import dateutil.parser

                    try:
                        last_time = dateutil.parser.parse(last_timestamp)
                        now = datetime.now(last_time.tzinfo)

                        # Use buffering if messages are close together (within 2 minutes)
                        if now - last_time < timedelta(minutes=2):
                            return True
                    except:
                        pass

            # Default to no buffering for new conversations
            return False

        except Exception as e:
            logger.error(f"[Router] Error determining buffering strategy: {e}")
            return False

    @staticmethod
    async def process_direct_message(ig_username: str, message_text: str, subscriber_id: str,
                                     first_name: str, last_name: str, user_message_timestamp_iso: str, fb_ad: bool = False) -> Dict[str, Any]:
        """Process message directly without buffering."""
        try:
            logger.info(f"[Router] Direct processing for {ig_username}")

            success = await CoreActionHandler.detect_and_handle_action(
                ig_username, message_text, subscriber_id, first_name, last_name, user_message_timestamp_iso, fb_ad
            )

            return {
                "status": "processed",
                "success": success,
                "message": "Message processed directly"
            }

        except Exception as e:
            logger.error(
                f"[Router] Error in direct processing for {ig_username}: {e}")
            return {
                "status": "error",
                "message": f"Error processing message: {str(e)}"
            }

    @staticmethod
    def get_routing_stats() -> Dict[str, Any]:
        """Get routing statistics."""
        try:
            # Get buffer stats for all active users
            from services.message_buffer import manychat_message_buffer, user_buffer_task_scheduled

            total_buffered = sum(len(buffer)
                                 for buffer in manychat_message_buffer.values())
            active_buffers = len(
                [uid for uid, scheduled in user_buffer_task_scheduled.items() if scheduled])

            return {
                "total_buffered_messages": total_buffered,
                "active_buffers": active_buffers,
                "total_users_with_buffers": len(manychat_message_buffer)
            }

        except Exception as e:
            logger.error(f"[Router] Error getting routing stats: {e}")
            return {"error": str(e)}

    @staticmethod
    def clear_user_routing_data(subscriber_id: str) -> bool:
        """Clear all routing data for a user."""
        try:
            MessageBuffer.clear_user_buffer(subscriber_id)
            logger.info(f"[Router] Cleared routing data for {subscriber_id}")
            return True

        except Exception as e:
            logger.error(
                f"[Router] Error clearing routing data for {subscriber_id}: {e}")
            return False
