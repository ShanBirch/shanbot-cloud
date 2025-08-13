"""
Calorie Action Handler
=====================
Handles calorie tracking, food logging, and nutritional analysis.
"""

from calorietracker import get_calorie_analysis, describe_food_image
from calorietracker import (
    get_calorie_analysis as analyze_calories,
    # New helper for description-only flow
)
from app.dashboard_modules.dashboard_sqlite_utils import (
    add_response_to_review_queue,
    get_nutrition_targets,
    upsert_nutrition_targets,
    log_meal_and_update_calorie_tracking,
    get_calorie_summary_text,
    get_user_metrics_json,
    set_user_metrics_json_field,
    get_db_connection,
    user_has_nutrition_profile,
    set_user_in_calorie_flow,
    upsert_user_nutrition_profile,
)
from webhook_handlers import get_user_data, update_analytics_data, call_gemini_with_retry
from webhook_utils import calculate_targets
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
import asyncio

# Import from the main webhook_handlers (not the app one)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("shanbot_calories")


class CalorieActionHandler:
    """Handles calorie tracking and food analysis."""

    @staticmethod
    async def handle_calorie_actions(ig_username: str, message_text: str, subscriber_id: str,
                                     first_name: str, last_name: str) -> bool:
        """Handle calorie-related actions."""
        try:
            # If there is a pending meal (15–30s buffer), capture user's text as description and finalize immediately
            try:
                from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
                conn_chk = get_db_connection()
                cur_chk = conn_chk.cursor()
                cur_chk.execute(
                    'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                row_chk = cur_chk.fetchone()
                current_chk = json.loads(
                    row_chk[0]) if row_chk and row_chk[0] else {}
                nutrition_chk = current_chk.get('nutrition') or {}
                pending_meal = nutrition_chk.get('pending_meal') or {}
                conn_chk.close()

                if pending_meal and isinstance(message_text, str) and 'http' not in message_text.lower():
                    # Save description and finalize now
                    user_desc = message_text.strip().rstrip(' .,!')
                    if user_desc:
                        try:
                            conn_upd = get_db_connection()
                            cur_upd = conn_upd.cursor()
                            cur_upd.execute(
                                'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                            row_upd = cur_upd.fetchone()
                            current = json.loads(
                                row_upd[0]) if row_upd and row_upd[0] else {}
                            current.setdefault('nutrition', {})
                            pm = current['nutrition'].get('pending_meal') or {}
                            pm['user_desc'] = user_desc
                            current['nutrition']['pending_meal'] = pm
                            cur_upd.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?', (json.dumps(
                                current), ig_username))
                            conn_upd.commit()
                            conn_upd.close()
                        except Exception:
                            pass
                        # Finalize now (skip wait since user just sent the description)
                        await CalorieActionHandler._finalize_pending_meal(
                            ig_username, subscriber_id, first_name, last_name, skip_wait=True
                        )
                        return True
            except Exception:
                pass
            # If no pending meal yet but a short description arrives while in calorie flow, buffer it for the next image (handles out-of-order delivery)
            try:
                if isinstance(message_text, str) and 'http' not in message_text.lower():
                    candidate_desc = message_text.strip().rstrip(' .,!')
                    normalized_cmd = ' '.join(candidate_desc.lower().split())
                    known_cmds = {
                        'track my cals', 'track my cals plz', 'track my calories', 'track calories', 'track my meal', 'track meal'
                    }
                    if 0 < len(candidate_desc) <= 60 and normalized_cmd not in known_cmds:
                        # Guard: only capture if user is in calorie flow; otherwise don't swallow general chat
                        in_flow_ok = False
                        try:
                            from app.dashboard_modules.dashboard_sqlite_utils import is_user_in_calorie_flow as _is_in_flow
                            in_flow_ok = bool(_is_in_flow(ig_username))
                        except Exception:
                            in_flow_ok = False
                        if not in_flow_ok:
                            return False
                        from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
                        from datetime import datetime, timedelta
                        conn_buf = get_db_connection()
                        cur_buf = conn_buf.cursor()
                        cur_buf.execute(
                            'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                        row_buf = cur_buf.fetchone()
                        current_buf = json.loads(
                            row_buf[0]) if row_buf and row_buf[0] else {}
                        current_buf.setdefault('nutrition', {})
                        nutrition_buf = current_buf['nutrition']
                        # Only set if there is no active pending_meal
                        if not nutrition_buf.get('pending_meal'):
                            nutrition_buf['pending_desc'] = {
                                'text': candidate_desc,
                                'created_at': datetime.now().isoformat(),
                                'expires_at': (datetime.now() + timedelta(seconds=30)).isoformat()
                            }
                            current_buf['nutrition'] = nutrition_buf
                            cur_buf.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?', (json.dumps(
                                current_buf), ig_username))
                            conn_buf.commit()
                        conn_buf.close()
                        return True
            except Exception:
                pass
            # If within rename grace window and user sends a short text, treat it as meal rename
            try:
                _, m, _ = get_user_data(ig_username, subscriber_id)
                metrics_json = m.get('metrics_json') or {}
                nutrition = metrics_json.get('nutrition') or {}
                rename_until = nutrition.get('meal_rename_until')
                if rename_until and message_text and len(message_text.strip()) <= 40 and 'http' not in message_text.lower():
                    from datetime import datetime
                    if datetime.fromisoformat(rename_until) > datetime.now():
                        from app.dashboard_modules.dashboard_sqlite_utils import rename_last_meal
                        new_name = message_text.strip().rstrip(' .,!')
                        if new_name:
                            if rename_last_meal(ig_username, new_name):
                                try:
                                    from webhook_handlers import send_manychat_message
                                    await send_manychat_message(subscriber_id, f"Updated meal name: {new_name}")
                                except Exception:
                                    pass
                                return True
            except Exception:
                pass
            # STRICT calorie tracking phrase gate: only exact phrase should trigger tracking flow
            if isinstance(message_text, str):
                normalized = ' '.join(message_text.strip().lower().split())
                if normalized in ('track my cals', 'track my cals plz'):
                    return await CalorieActionHandler._handle_macro_tracking(
                        ig_username, message_text, subscriber_id, first_name, last_name
                    )

            # If we're waiting on nutrition profile details, try to complete setup from this message
            try:
                metrics_json = get_user_metrics_json(ig_username)
                if isinstance(metrics_json, dict) and metrics_json.get('pending_calorie_setup'):
                    completed = await CalorieActionHandler._try_complete_calorie_setup(
                        ig_username, subscriber_id, message_text, first_name, last_name
                    )
                    if completed:
                        return True
                    else:
                        # If still pending and their message is a media URL, prompt them to send details first
                        if CalorieActionHandler._has_media_url(message_text):
                            try:
                                from webhook_handlers import send_manychat_message
                                await send_manychat_message(subscriber_id, "Quick one! Can you send your weight, height, DOB, activity level and goal first? Then I'll track this meal.")
                            except Exception:
                                pass
                            return True
            except Exception:
                pass

            # Check for food logging BUT only if user is in/near calorie flow
            if await CalorieActionHandler._is_food_log(message_text):
                try:
                    # Gate by flow flags to avoid unsolicited analysis on random food pics
                    in_flow_flag = False
                    try:
                        from app.dashboard_modules.dashboard_sqlite_utils import is_user_in_calorie_flow as _is_in_flow
                        in_flow_flag = bool(_is_in_flow(ig_username))
                    except Exception:
                        in_flow_flag = False

                    metrics_json = get_user_metrics_json(ig_username) or {}
                    pending_setup = bool(
                        metrics_json.get('pending_calorie_setup'))
                    nutrition = metrics_json.get('nutrition') or {}
                    rename_until = nutrition.get('meal_rename_until')
                    in_rename = False
                    if rename_until:
                        from datetime import datetime
                        try:
                            in_rename = datetime.fromisoformat(
                                rename_until) > datetime.now()
                        except Exception:
                            in_rename = False

                    if not (in_flow_flag or pending_setup or in_rename):
                        # Not in calorie context → ignore food images
                        return False
                except Exception:
                    return False

                # Ensure daily reset before logging any meal
                try:
                    from app.dashboard_modules.dashboard_sqlite_utils import reset_daily_calorie_tracking_if_new_day
                    reset_daily_calorie_tracking_if_new_day(ig_username)
                except Exception:
                    pass
                return await CalorieActionHandler._handle_food_log(
                    ig_username, message_text, subscriber_id, first_name, last_name
                )

            # Check for calorie questions
            if await CalorieActionHandler._is_calorie_question(message_text):
                return await CalorieActionHandler._handle_calorie_question(
                    ig_username, message_text, subscriber_id, first_name, last_name
                )

            # Check for macro tracking
            if await CalorieActionHandler._is_macro_tracking(message_text):
                return await CalorieActionHandler._handle_macro_tracking(
                    ig_username, message_text, subscriber_id, first_name, last_name
                )

            return False

        except Exception as e:
            logger.error(
                f"[CalorieAction] Error handling calorie actions for {ig_username}: {e}")
            return False

    @staticmethod
    async def _is_food_log(message_text: str) -> bool:
        """Detect if message is a food log entry."""
        # Check for food image URL
        if CalorieActionHandler._has_media_url(message_text):
            return True

        food_indicators = [
            'ate', 'had', 'breakfast', 'lunch', 'dinner', 'snack',
            'meal', 'food', 'calories', 'protein', 'carbs'
        ]

        quantity_patterns = [
            r'\d+\s*(g|grams|oz|ounces|cups?|tbsp|tsp)',
            r'\d+\s*(calories|cal|kcal)',
            r'\d+\s*(servings?|portions?)'
        ]

        message_lower = message_text.lower()

        # Must have food indicator and quantity/measurement
        has_food_indicator = any(
            indicator in message_lower for indicator in food_indicators)
        has_quantity = any(re.search(pattern, message_lower)
                           for pattern in quantity_patterns)

        return has_food_indicator and (has_quantity or len(message_text.split()) > 3)

    @staticmethod
    def _has_media_url(message_text: str) -> bool:
        """Check if message contains media URLs."""
        url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"
        return bool(re.search(url_pattern, message_text))

    @staticmethod
    def _extract_media_url(message_text: str) -> Optional[str]:
        """Extract media URL from message."""
        url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"
        match = re.search(url_pattern, message_text)
        return match.group(1) if match else None

    @staticmethod
    async def _is_calorie_question(message_text: str) -> bool:
        """Detect if message is asking about calories.
        STRICT: Do not auto-detect via keywords anymore to avoid false positives.
        Only the exact phrase gate in handle_calorie_actions triggers tracking.
        """
        return False

    @staticmethod
    async def _is_macro_tracking(message_text: str) -> bool:
        """Detect if message is about macro tracking.
        STRICT: Only exact phrase 'track my cals plz' should trigger (handled in handle_calorie_actions).
        """
        return False

    @staticmethod
    async def _handle_food_log(ig_username: str, message_text: str, subscriber_id: str,
                               first_name: str, last_name: str) -> bool:
        """Handle food logging."""
        try:
            logger.info(f"[CalorieLog] Handling food log for {ig_username}")

            # Get user data
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            client_analysis = metrics.get('client_analysis', {})
            nutrition_targets = metrics.get('nutrition_targets', {})

            # Check if this is an image-based food message
            media_url = CalorieActionHandler._extract_media_url(message_text)

            if media_url:
                # If we have nutrition targets, proceed with full tracking. Otherwise ask for details first.
                has_targets = bool(get_nutrition_targets(ig_username))
                if has_targets:
                    # Start 15s pending window to allow user to add a description
                    try:
                        from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
                        from datetime import datetime, timedelta
                        import random as _random
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute(
                            'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                        row = cur.fetchone()
                        current = json.loads(row[0]) if row and row[0] else {}
                        current.setdefault('nutrition', {})
                        delay_seconds = int(_random.randint(15, 30))
                        current['nutrition']['pending_meal'] = {
                            'media_url': media_url,
                            'created_at': datetime.now().isoformat(),
                            'expires_at': (datetime.now() + timedelta(seconds=delay_seconds)).isoformat(),
                            'user_desc': message_text.replace(media_url, '').strip()
                        }
                        cur.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?', (json.dumps(
                            current), ig_username))
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                    # Launch background finalize after 15s
                    asyncio.create_task(CalorieActionHandler._finalize_pending_meal(
                        ig_username, subscriber_id, first_name, last_name))
                    # No user-facing message; silently buffer for 15s and finalize
                    return True
                else:
                    set_user_metrics_json_field(
                        ig_username, 'pending_calorie_setup', True)
                    ask_msg = (
                        "Quick one! Can you send your weight, height, DOB, activity level and goal first?"
                        " Then I'll track this meal."
                    )
                    try:
                        from webhook_handlers import send_manychat_message
                        await send_manychat_message(subscriber_id, ask_msg)
                    except Exception:
                        add_response_to_review_queue(
                            user_ig_username=ig_username,
                            user_subscriber_id=subscriber_id,
                            incoming_message_text=message_text,
                            incoming_message_timestamp="",
                            generated_prompt_text="Request nutrition details for calorie setup",
                            proposed_response_text=ask_msg,
                            prompt_type="macro_tracking"
                        )
                    update_analytics_data(
                        ig_username, message_text, ask_msg, subscriber_id, first_name, last_name)
                    return True
            else:
                # For plain text entries, treat as food log text and give gentle feedback only
                food_analysis = await CalorieActionHandler._analyze_food_entry(
                    message_text, client_analysis, nutrition_targets
                )

            if food_analysis:
                response = None
                if media_url and food_analysis.get('raw_analysis'):
                    # Parse numbers from analysis text
                    raw_analysis = food_analysis['raw_analysis']
                    parsed = CalorieActionHandler._parse_macros_from_analysis(
                        raw_analysis)
                    if parsed:
                        # Use user's own description (without URL) as meal name
                        user_desc = message_text.replace(media_url, '').strip()
                        meal_name = user_desc.strip() if user_desc else CalorieActionHandler._extract_meal_name_from_analysis(
                            raw_analysis, 'Meal')
                        if not meal_name or meal_name.lower() == 'meal':
                            meal_name = await CalorieActionHandler._extract_meal_name_via_llm(raw_analysis, user_desc)
                        # Update SQLite calorie tracking
                        log_meal_and_update_calorie_tracking(
                            ig_username=ig_username,
                            meal_description=meal_name,
                            calories=parsed['calories'],
                            protein=parsed['protein'],
                            carbs=parsed['carbs'],
                            fats=parsed['fats']
                        )
                        # Build two-part response: detailed meal line then daily remaining summary
                        summary = get_calorie_summary_text(ig_username) or ""
                        response = (
                            f"{meal_name} — Calories: {parsed['calories']}, P: {parsed['protein']}g, "
                            f"C: {parsed['carbs']}g, F: {parsed['fats']}g\n\n{summary}"
                        )

                        # Keep flow active briefly to allow follow-up rename messages
                        try:
                            from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
                            conn = get_db_connection()
                            cur = conn.cursor()
                            cur.execute(
                                'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                            row = cur.fetchone()
                            metrics = json.loads(
                                row[0]) if row and row[0] else {}
                            from datetime import datetime, timedelta
                            metrics.setdefault('nutrition', {})
                            metrics['nutrition']['meal_rename_until'] = (
                                datetime.now() + timedelta(seconds=90)).isoformat()
                            cur.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?', (json.dumps(
                                metrics), ig_username))
                            conn.commit()
                            conn.close()
                        except Exception:
                            pass
                        # Do not immediately turn off flow; router will allow grace-period follow-up

                if not response:
                    # Fallback to non-tracking feedback
                    response = food_analysis.get(
                        'feedback', 'Thanks for sharing what you ate!')

                # Ensure we have a valid ig_username before sending
                if not ig_username or ig_username.strip() == '':
                    ig_username = f"user_{subscriber_id}"
                    logger.warning(
                        f"[CalorieLog] Using fallback ig_username '{ig_username}' for food log")

                # Send immediately
                try:
                    from webhook_handlers import send_manychat_message
                    await send_manychat_message(subscriber_id, response)
                except Exception:
                    add_response_to_review_queue(
                        user_ig_username=ig_username,
                        user_subscriber_id=subscriber_id,
                        incoming_message_text=message_text,
                        incoming_message_timestamp="",
                        generated_prompt_text="Food log analysis",
                        proposed_response_text=response,
                        prompt_type="food_log"
                    )
                update_analytics_data(
                    ig_username, message_text, response, subscriber_id, first_name, last_name)
                return True

            return False

        except Exception as e:
            logger.error(
                f"[CalorieLog] Error handling food log for {ig_username}: {e}")
            return False

    @staticmethod
    async def _handle_calorie_question(ig_username: str, message_text: str, subscriber_id: str,
                                       first_name: str, last_name: str) -> bool:
        """Handle calorie-related questions."""
        try:
            logger.info(
                f"[CalorieQuestion] Handling calorie question for {ig_username}")

            # Get user data for context
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            client_analysis = metrics.get('client_analysis', {})
            nutrition_targets = metrics.get('nutrition_targets', {})

            # Generate response based on question type
            response = await CalorieActionHandler._generate_calorie_response(
                message_text, client_analysis, nutrition_targets
            )

            if response:
                # Send immediately for Q&A too; fallback to queue if needed
                try:
                    from webhook_handlers import send_manychat_message
                    await send_manychat_message(subscriber_id, response)
                except Exception:
                    review_id = add_response_to_review_queue(
                        user_ig_username=ig_username,
                        user_subscriber_id=subscriber_id,
                        incoming_message_text=message_text,
                        incoming_message_timestamp="",
                        generated_prompt_text="Calorie question response",
                        proposed_response_text=response,
                        prompt_type="calorie_question"
                    )
                    if review_id:
                        logger.info(
                            f"[CalorieQuestion] Queued calorie response (ID: {review_id}) for {ig_username}")
                update_analytics_data(
                    ig_username, message_text, response, subscriber_id, first_name, last_name)
                return True

            return False

        except Exception as e:
            logger.error(
                f"[CalorieQuestion] Error handling calorie question for {ig_username}: {e}")
            return False

    @staticmethod
    async def _handle_macro_tracking(ig_username: str, message_text: str, subscriber_id: str,
                                     first_name: str, last_name: str) -> bool:
        """Handle macro tracking requests."""
        try:
            logger.info(
                f"[MacroTracking] Handling macro tracking for {ig_username}")

            # Set user in calorie flow
            set_user_in_calorie_flow(ig_username, True)

            # Require both a saved profile and valid targets before allowing photo prompt
            profile_exists = user_has_nutrition_profile(ig_username)
            nutrition_targets = get_nutrition_targets(ig_username) or {}

            if not profile_exists or not nutrition_targets:
                # If targets don't exist, ask for them and set a pending flag
                logger.info(
                    f"Nutrition targets for {ig_username} are missing or incomplete. Prompting for setup.")
                set_user_metrics_json_field(
                    ig_username, 'pending_calorie_setup', True)

                prompt_message = (
                    "Sweet! To set your daily calories & macros, just reply with your details separated by a space or comma:\n\n"
                    "• Weight (kg)\n"
                    "• Height (cm)\n"
                    "• DOB (dd/mm/yyyy)\n"
                    "• Activity (sedentary, light, moderate, very)\n"
                    "• Goal (loss, muscle, recomp)\n\n"
                    "For example: 94kg 180cm 05/06/1991 moderate loss"
                )

                try:
                    from webhook_handlers import send_manychat_message
                    await send_manychat_message(subscriber_id, prompt_message)
                except Exception:
                    add_response_to_review_queue(
                        user_ig_username=ig_username,
                        user_subscriber_id=subscriber_id,
                        incoming_message_text=message_text,
                        incoming_message_timestamp="",
                        generated_prompt_text="Request nutrition details for calorie setup",
                        proposed_response_text=prompt_message,
                        prompt_type="macro_tracking"
                    )
                update_analytics_data(
                    ig_username, message_text, prompt_message, subscriber_id, first_name, last_name)
                return True
            else:
                # If targets exist, prompt for the food photo
                logger.info(
                    f"Nutrition targets for {ig_username} are complete. Prompting for food photo.")
                prompt_text = "Calorie tracking start"
                response = "Yep, send a photo of your meal plus a quick description and I'll track it."
                try:
                    from webhook_handlers import send_manychat_message
                    await send_manychat_message(subscriber_id, response)
                except Exception:
                    add_response_to_review_queue(
                        user_ig_username=ig_username,
                        user_subscriber_id=subscriber_id,
                        incoming_message_text=message_text,
                        incoming_message_timestamp="",
                        generated_prompt_text=prompt_text,
                        proposed_response_text=response,
                        prompt_type="macro_tracking"
                    )
                update_analytics_data(
                    ig_username, message_text, response, subscriber_id, first_name, last_name)
                return True

        except Exception as e:
            logger.error(
                f"[MacroTracking] Error handling macro tracking for {ig_username}: {e}")
            return False

    @staticmethod
    async def _analyze_food_image(media_url: str, message_text: str, client_analysis: Dict, nutrition_targets: Dict) -> Optional[Dict]:
        """Classify first, then analyze accordingly (plated vs packaged vs ingredient)."""
        try:
            logger.info(
                f"[FoodImageAnalysis] Analyzing food image: {media_url[:50]}...")

            # Extract description from message (remove URL)
            user_description = message_text.replace(media_url, "").strip()
            if not user_description:
                # Provide a classification hint to improve dish identification (e.g., pizza vs salad)
                user_description = (
                    "Classification hint: strictly identify the visible dish from the image. "
                    "Prefer the primary category (e.g., 'Pizza', 'Burrito', 'Pasta', 'Salad'). "
                    "If round crust, melted cheese, slice cuts, or pizza box are visible, classify as Pizza. "
                    "Avoid calling it a salad unless a leafy greens base clearly dominates. Start your analysis with the dish name."
                )

            import os
            # Fallback: use GEMINI_API_KEY, else GOOGLE_API_KEY, else built-in default (matches existing get_calorie_analysis fallback)
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv(
                "GOOGLE_API_KEY") or "AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y"
            from calorietracker import classify_food_image, analyze_packaged_food, format_packaged_summary, get_calorie_analysis

            # Step 1: classify image
            cls = classify_food_image(
                media_url, api_key, model_name="gemini-2.0-flash") or {}
            item_type = cls.get('item_type')
            dish_hint = cls.get('dish_name')
            try:
                conf = int(cls.get('confidence') or 0)
            except Exception:
                conf = 0

            if item_type == 'packaged':
                pack = analyze_packaged_food(
                    media_url, api_key, model_name="gemini-2.0-flash-thinking-exp-01-21")
                if pack:
                    summary = format_packaged_summary(pack)
                    return {"calories": 0, "feedback": summary, "raw_analysis": summary}
                return {"calories": 0, "feedback": "Packaged item detected. Send the nutrition panel for exact values or tell me how much you had."}

            if item_type == 'unclear' or conf < 60:
                # Don't stop; attempt calorie estimation anyway using any user/dish hint
                from calorietracker import get_calorie_analysis
                raw_analysis = get_calorie_analysis(
                    image_url=media_url,
                    gemini_api_key=api_key,
                    primary_model="gemini-2.0-flash",
                    first_fallback_model="gemini-2.0-flash-thinking-exp-01-21",
                    second_fallback_model="gemini-2.5-flash-lite",
                    user_description=(user_description or dish_hint or "")
                )
                if raw_analysis:
                    return {"calories": 0, "feedback": str(raw_analysis), "raw_analysis": str(raw_analysis)}
                return {"calories": 0, "feedback": "Need a clear plated meal photo (or add a 2-5 word label)."}

            # Step 2: plated/ingredient → calorie estimation (use dish_hint if no user_description)
            raw_analysis = get_calorie_analysis(
                image_url=media_url,
                gemini_api_key=api_key,
                primary_model="gemini-2.0-flash",
                first_fallback_model="gemini-2.0-flash-thinking-exp-01-21",
                second_fallback_model="gemini-2.5-flash-lite",
                user_description=(user_description or dish_hint or "")
            )

            if not raw_analysis or (isinstance(raw_analysis, str) and (
                "error" in raw_analysis.lower() or "failed" in raw_analysis.lower()
            )):
                logger.error(
                    f"[FoodImageAnalysis] Failed to analyze image: {raw_analysis}")
                return {
                    "calories": 0,
                    "feedback": "Sorry mate, had a bit of trouble analysing that pic. Can you try sending it again?"
                }

            # Return raw analysis; parsing happens at caller to log into SQLite
            return {
                "calories": 0,
                "feedback": str(raw_analysis),
                "raw_analysis": str(raw_analysis)
            }

        except Exception as e:
            logger.error(
                f"[FoodImageAnalysis] Error analyzing food image: {e}")
            return {
                "calories": 0,
                "feedback": "Sorry mate, had trouble analyzing that image. Can you try again?"
            }

    @staticmethod
    async def _analyze_food_entry(food_text: str, client_analysis: Dict, nutrition_targets: Dict) -> Dict:
        """Analyze a food entry for calories and macros."""
        try:
            analysis_prompt = f"""
            Analyze this food entry and provide nutritional information:
            
            Food Entry: "{food_text}"
            
            Client Targets: {json.dumps(nutrition_targets, indent=2)}
            
            Provide:
            1. Estimated calories
            2. Protein, carbs, fat (if possible)
            3. Brief feedback on how it fits their goals
            4. Encouragement
            
            Format as JSON:
            {{
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0,
                "feedback": "Great choice! This meal..."
            }}
            """

            response = await call_gemini_with_retry("gemini-2.5-flash-lite", analysis_prompt)

            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Fallback response
                return {
                    "calories": 0,
                    "feedback": "Thanks for logging that! Keep up the great work with tracking your nutrition."
                }

        except Exception as e:
            logger.error(f"[FoodAnalysis] Error analyzing food entry: {e}")
            return {"feedback": "Thanks for sharing what you ate!"}

    @staticmethod
    async def _generate_calorie_response(question: str, client_analysis: Dict, nutrition_targets: Dict) -> str:
        """Generate response to calorie questions."""
        prompt = f"""
        Answer this nutrition question for a client:
        
        Question: "{question}"
        
        Client Profile: {json.dumps(client_analysis, indent=2)}
        Nutrition Targets: {json.dumps(nutrition_targets, indent=2)}
        
        Provide a helpful, personalized answer based on their goals and profile.
        Keep it encouraging and actionable.
        """

        return await call_gemini_with_retry("gemini-2.5-flash-lite", prompt)

    @staticmethod
    async def _generate_macro_guidance(message: str, nutrition_targets: Dict) -> str:
        """Generate macro tracking guidance."""
        prompt = f"""
        Provide macro tracking guidance for this request:
        
        Request: "{message}"
        
        Current Targets: {json.dumps(nutrition_targets, indent=2)}
        
        Give practical advice on:
        1. How to track macros effectively
        2. What foods to focus on for each macro
        3. Simple tips for hitting targets
        
        Keep it encouraging and actionable.
        """

        return await call_gemini_with_retry("gemini-2.0-flash-thinking-exp-01-21", prompt)

    @staticmethod
    def _parse_macros_from_analysis(analysis_text: str) -> Optional[Dict[str, int]]:
        """Extract calories and macros from analysis text."""
        try:
            calories_match = re.search(
                r"calories\s*[=:]?\s*(\d+)", analysis_text, re.I)
            protein_match = re.search(
                r"protein\s*[=:]?\s*(\d+)\s*g", analysis_text, re.I)
            carbs_match = re.search(
                r"carb(?:s|ohydrates)?\s*[=:]?\s*(\d+)\s*g", analysis_text, re.I)
            fats_match = re.search(
                r"fat(?:s)?\s*[=:]?\s*(\d+)\s*g", analysis_text, re.I)
            if all([calories_match, protein_match, carbs_match, fats_match]):
                return {
                    'calories': int(calories_match.group(1)),
                    'protein': int(protein_match.group(1)),
                    'carbs': int(carbs_match.group(1)),
                    'fats': int(fats_match.group(1)),
                }
            return None
        except Exception:
            return None

    @staticmethod
    def _extract_meal_name_from_analysis(analysis_text: str, fallback_name: str = "Meal") -> str:
        """Best-effort extraction of a human-friendly meal name from analysis text."""
        try:
            text = (analysis_text or "").strip()
            if not text:
                return fallback_name

            def _looks_like_macros(s: str) -> bool:
                s_lower = s.lower()
                if any(tok in s_lower for tok in ["calorie", "protein", "carb", "fat", "kcal", "=", ":"]):
                    return True
                if re.search(r"\b\d+\s*g\b", s_lower):
                    return True
                return False

            patterns = [
                r"(?:looks like|appears to be|this is|it is)\s+(?:an?\s+)?([A-Za-z][\w\s\-']{3,60})[\.!]",
                r"^Dish\s*[:\-]\s*([A-Za-z][\w\s\-']{3,60})",
                r"^Meal\s*[:\-]\s*([A-Za-z][\w\s\-']{3,60})",
                r"^Food\s*[:\-]\s*([A-Za-z][\w\s\-']{3,60})",
            ]
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                if m:
                    name = m.group(1).strip()
                    name = re.sub(r"\b(meal|dish)\b$", "", name,
                                  flags=re.IGNORECASE).strip()
                    if not _looks_like_macros(name):
                        clean = name.rstrip(" ,.-")
                        return clean[:1].upper() + clean[1:]

            first_sentence = re.split(r"[\.!?]", text)[0]
            words = first_sentence.split()
            candidate = " ".join(words[:6]).strip()
            if candidate and not _looks_like_macros(candidate):
                clean = candidate.rstrip(" ,.-")
                return clean[:1].upper() + clean[1:]
            return fallback_name
        except Exception:
            return fallback_name

    @staticmethod
    async def _extract_meal_name_via_llm(analysis_text: str, user_description: str = "") -> str:
        """Ask the LLM to return a concise meal name only (2-5 words), no macros."""
        try:
            prompt = f"""
            From the following information, output ONLY a concise meal name (2-5 words). No numbers, macros, or punctuation beyond letters/spaces. Examples: Overnight Oats, Tofu Stir Fry, Veggie Burrito.

            User description (may be empty): {user_description or 'N/A'}
            Analysis:
            {analysis_text}
            """
            name = await call_gemini_with_retry("gemini-2.5-flash-lite", prompt)
            name = (name or "").strip()
            name = re.sub(r"[^A-Za-z\s\-']", "", name).strip()
            words = name.split()
            if len(words) > 5:
                name = " ".join(words[:5])
            if len(name) >= 3 and any(c.isalpha() for c in name):
                return name[:1].upper() + name[1:]
            return "Meal"
        except Exception:
            return "Meal"

    @staticmethod
    async def _try_complete_calorie_setup(ig_username: str, subscriber_id: str, message_text: str,
                                          first_name: str, last_name: str) -> bool:
        """If user replied with nutrition profile, parse, compute, and store targets."""
        try:
            logger.info(
                f"[CalorieSetup] Attempting to parse nutrition details from: '{message_text}'")
            # More robust parsing: accept unit-less numbers, commas or spaces, and common abbreviations
            text_raw = (message_text or "").strip()
            text = text_raw.lower().replace(',', ' ')

            # Extract structured parts with units if present
            weight_match = re.search(r'\b(\d{2,3})\s*k(?:g|gs)?\b', text)
            height_match = re.search(r'\b(\d{3})\s*cm\b', text)
            dob_match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
            activity_match = re.search(
                r'\b(sedentary|sed|light|lite|moderate|mod|very|vig|vigorous)\b', text)
            goal_match = re.search(
                r'\b(loss|cut|fatloss|muscle|gain|bulk|recomp)\b', text)

            # Fallback: pick first two plausible numbers as weight (30–200) and height (130–230)
            numbers = [int(n) for n in re.findall(r'\b(\d{2,4})\b', text)]
            inferred_weight = None
            inferred_height = None
            if not weight_match or not height_match:
                for n in numbers:
                    if inferred_weight is None and 30 <= n <= 200:
                        inferred_weight = n
                        continue
                    if inferred_height is None and 130 <= n <= 230:
                        inferred_height = n
                        break

            weight_val = int(weight_match.group(
                1)) if weight_match else inferred_weight
            height_val = int(height_match.group(
                1)) if height_match else inferred_height

            # Normalize activity and goal
            activity_norm = None
            if activity_match:
                act = activity_match.group(1)
                if act in ("sed",):
                    activity_norm = "sedentary"
                elif act in ("lite",):
                    activity_norm = "light"
                elif act in ("mod",):
                    activity_norm = "moderate"
                elif act in ("very", "vig", "vigorous"):
                    activity_norm = "very"
                else:
                    activity_norm = act

            goal_norm = None
            if goal_match:
                g = goal_match.group(1)
                if g in ("cut", "loss", "fatloss"):
                    goal_norm = "loss"
                elif g in ("gain", "bulk"):
                    goal_norm = "muscle"
                else:
                    goal_norm = g

            onboarding_info = {
                'weight_kg': weight_val,
                'height_cm': height_val,
                'dob': dob_match.group(1) if dob_match else None,
                'activity_level': activity_norm,
                'main_goal': goal_norm,
            }

            # Check if any crucial field is missing
            if not all([onboarding_info['weight_kg'], onboarding_info['height_cm'], onboarding_info['dob'], onboarding_info['activity_level'], onboarding_info['main_goal']]):
                logger.warning(
                    f"[CalorieSetup] Failed to parse all required fields. Parsed: {onboarding_info}")
                retry_msg = "All good! Please reply like: 84kg 184cm 01/12/1993 moderate muscle"
                try:
                    from webhook_handlers import send_manychat_message
                    await send_manychat_message(subscriber_id, retry_msg)
                except Exception:
                    add_response_to_review_queue(
                        user_ig_username=ig_username,
                        user_subscriber_id=subscriber_id,
                        incoming_message_text=message_text,
                        incoming_message_timestamp="",
                        generated_prompt_text="Calorie setup parse retry",
                        proposed_response_text=retry_msg,
                        prompt_type="macro_tracking",
                    )
                update_analytics_data(
                    ig_username, message_text, retry_msg, subscriber_id, first_name, last_name)
                return True

            targets = calculate_targets(onboarding_info)
            if not targets:
                logger.error(
                    "[CalorieSetup] calculate_targets returned None even with parsed info.")
                # Handle this potential error gracefully
                return False

            # Persist targets and initialize daily tracking
            upsert_nutrition_targets(ig_username, targets)
            # Also persist a basic nutrition profile so future checks pass
            try:
                age_val = None
                try:
                    from datetime import datetime, date
                    dob_str = onboarding_info.get('dob')
                    if dob_str:
                        dob_dt = datetime.strptime(dob_str, "%d/%m/%Y").date()
                        today = date.today()
                        age_val = today.year - dob_dt.year - \
                            ((today.month, today.day) < (dob_dt.month, dob_dt.day))
                except Exception:
                    age_val = None
                upsert_user_nutrition_profile(
                    ig_username=ig_username,
                    sex=None,
                    dob=onboarding_info.get('dob'),
                    age=age_val,
                    height_cm=onboarding_info.get('height_cm'),
                    weight_kg=onboarding_info.get('weight_kg'),
                    activity_level=onboarding_info.get('activity_level'),
                    main_goal=onboarding_info.get('main_goal'),
                )
            except Exception as e:
                logger.warning(
                    f"[CalorieSetup] Could not upsert user nutrition profile for {ig_username}: {e}")
            set_user_metrics_json_field(
                ig_username, 'pending_calorie_setup', False)
            logger.info(
                f"[CalorieSetup] Successfully created targets for {ig_username}: {targets['target_calories']} cals")

            confirm_msg = f"All set. Your daily target is {targets['target_calories']} cals. Send a photo to log your first meal."
            try:
                from webhook_handlers import send_manychat_message
                await send_manychat_message(subscriber_id, confirm_msg)
            except Exception:
                add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=message_text,
                    incoming_message_timestamp="",
                    generated_prompt_text="Calorie setup complete",
                    proposed_response_text=confirm_msg,
                    prompt_type="macro_tracking",
                )
            update_analytics_data(
                ig_username, message_text, confirm_msg, subscriber_id, first_name, last_name)
            return True
        except Exception as e:
            logger.error(
                f"[CalorieSetup] CRITICAL Error completing calorie setup for {ig_username}: {e}", exc_info=True)
            return False

    @staticmethod
    async def _finalize_pending_meal(ig_username: str, subscriber_id: str, first_name: str, last_name: str, skip_wait: bool = False) -> None:
        try:
            from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection
            from datetime import datetime
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
            row = cur.fetchone()
            metrics = json.loads(row[0]) if row and row[0] else {}
            nutrition = metrics.get('nutrition') or {}
            pending = nutrition.get('pending_meal') or {}
            if not pending:
                return
            expires_at = pending.get('expires_at')
            media_url = pending.get('media_url')
            user_desc = pending.get('user_desc') or ''

            # Wait until buffer window expires unless explicitly skipping
            if not skip_wait:
                try:
                    if expires_at:
                        expire_dt = datetime.fromisoformat(expires_at)
                        now_dt = datetime.now()
                        wait_seconds = (expire_dt - now_dt).total_seconds()
                        if wait_seconds > 0:
                            await asyncio.sleep(wait_seconds)
                    else:
                        await asyncio.sleep(15)
                except Exception:
                    await asyncio.sleep(15)

                # Refresh pending state to capture any new description sent during the wait
                conn2 = get_db_connection()
                cur2 = conn2.cursor()
                cur2.execute(
                    'SELECT metrics_json FROM users WHERE ig_username = ? LIMIT 1', (ig_username,))
                row2 = cur2.fetchone()
                metrics2 = json.loads(row2[0]) if row2 and row2[0] else {}
                nutrition2 = metrics2.get('nutrition') or {}
                pending2 = nutrition2.get('pending_meal') or {}
                if not pending2:
                    conn2.close()
                    return
                expires_at = pending2.get('expires_at')
                media_url = pending2.get('media_url')
                user_desc = pending2.get('user_desc') or ''
                # Switch to refreshed connection for clearing
                conn.close()
                conn = conn2
                cur = cur2
            # Clear pending state regardless
            nutrition.pop('pending_meal', None)
            metrics['nutrition'] = nutrition
            cur.execute('UPDATE users SET metrics_json = ? WHERE ig_username = ?',
                        (json.dumps(metrics), ig_username))
            conn.commit()
            conn.close()

            if not media_url:
                return

            # Run analysis now using stored user_desc (if any)
            _, client_metrics, _ = get_user_data(ig_username, subscriber_id)
            client_analysis = client_metrics.get('client_analysis', {})
            nutrition_targets = client_metrics.get('nutrition_targets', {})
            msg_text = f"{user_desc} {media_url}".strip()
            food_analysis = await CalorieActionHandler._analyze_food_image(
                media_url, msg_text, client_analysis, nutrition_targets
            )
            if not food_analysis or not food_analysis.get('raw_analysis'):
                return

            raw_analysis = food_analysis['raw_analysis']
            parsed = CalorieActionHandler._parse_macros_from_analysis(
                raw_analysis)
            if not parsed:
                return

            # Pick meal name: prefer user_desc exactly, else analysis/LLM
            if user_desc:
                meal_name = user_desc.strip()
            else:
                meal_name = CalorieActionHandler._extract_meal_name_from_analysis(
                    raw_analysis, 'Meal')
                if not meal_name or meal_name.lower() == 'meal':
                    meal_name = await CalorieActionHandler._extract_meal_name_via_llm(raw_analysis, user_desc)

            # Log meal and send response
            log_meal_and_update_calorie_tracking(
                ig_username=ig_username,
                meal_description=meal_name,
                calories=parsed['calories'],
                protein=parsed['protein'],
                carbs=parsed['carbs'],
                fats=parsed['fats']
            )
            summary = get_calorie_summary_text(ig_username) or ""
            response = (
                f"{meal_name} — Calories: {parsed['calories']}, P: {parsed['protein']}g, "
                f"C: {parsed['carbs']}g, F: {parsed['fats']}g\n\n{summary}"
            )
            try:
                from webhook_handlers import send_manychat_message
                await send_manychat_message(subscriber_id, response)
            except Exception:
                add_response_to_review_queue(
                    user_ig_username=ig_username,
                    user_subscriber_id=subscriber_id,
                    incoming_message_text=msg_text,
                    incoming_message_timestamp="",
                    generated_prompt_text="Food log analysis (finalized)",
                    proposed_response_text=response,
                    prompt_type="food_log"
                )
        except Exception:
            pass
