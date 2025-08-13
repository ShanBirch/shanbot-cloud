"""
Wix Onboarding Handler
=====================
Handles Wix form submissions for direct client onboarding.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from webhook_handlers import get_user_data
from todo_utils import add_todo_item
from app.dashboard_modules.dashboard_sqlite_utils import get_db_connection

logger = logging.getLogger("shanbot_wix")


class WixOnboardingHandler:
    """Handles Wix form submissions for direct onboarding."""

    @staticmethod
    def map_wix_form_to_client_data(form_data: Dict) -> Optional[Dict]:
        """Map Wix form data to client data structure."""
        try:
            # Handle Wix form structure
            submissions = form_data.get('submissions', [])
            field_map = {}

            for submission in submissions:
                label = submission.get('label', '').lower()
                value = submission.get('value', '')
                field_map[label] = value

            # Extract personal info
            email = field_map.get('email') or form_data.get('email')
            first_name = field_map.get(
                'first name') or field_map.get('firstname')
            last_name = field_map.get('last name') or field_map.get('lastname')
            phone = field_map.get('phone') or field_map.get('phonenumber')

            full_name = f"{first_name or ''} {last_name or ''}".strip(
            ) or 'Unknown'

            # Physical stats
            weight_str = field_map.get('weight', '').replace(
                'kgs', '').replace('kg', '').strip()
            weight = float(weight_str) if weight_str.replace(
                '.', '').isdigit() else 70

            height_str = field_map.get('height', '').replace('cm', '').strip()
            height = float(height_str) if height_str.replace(
                '.', '').isdigit() else 170

            # Calculate age from birthday
            birthday = field_map.get('birthday')
            age = 30  # default
            if birthday:
                try:
                    birth_date = datetime.strptime(birthday, '%Y-%m-%d')
                    today = datetime.now()
                    age = today.year - birth_date.year - \
                        ((today.month, today.day) <
                         (birth_date.month, birth_date.day))
                except:
                    age = 30

            # Fitness and dietary info
            primary_goal = field_map.get('fitness goal') or 'muscle_gain'
            activity_level = field_map.get(
                'activity level') or 'moderately_active'
            gym_access = field_map.get('gym access') or field_map.get(
                'training location') or 'full_gym'
            training_days = field_map.get('training days') or 'monday-friday'
            training_experience = field_map.get(
                'training experience') or 'beginner'

            dietary_type = form_data.get('dietaryType') or 'plant-based'
            dietary_restrictions = form_data.get('dietaryRestrictions') or ''
            disliked_foods = form_data.get('dislikedFoods') or ''

            regular_breakfast = form_data.get('regularBreakfast') or ''
            regular_lunch = form_data.get('regularLunch') or ''
            regular_dinner = form_data.get('regularDinner') or ''

            exercise_dislikes = form_data.get('exerciseDislikes') or ''

            # Build client data structure
            client_data = {
                "personal_info": {
                    "email": {"value": email or "", "confidence": 95},
                    "full_name": {"value": full_name, "confidence": 95},
                    "phone": {"value": phone or "", "confidence": 95},
                    "age": {"value": int(age), "confidence": 90}
                },
                "physical_info": {
                    "weight": {"value": weight, "unit": "kg", "confidence": 95},
                    "height": {"value": height, "unit": "cm", "confidence": 95},
                    "target_weight": {"value": weight + 5 if primary_goal == 'muscle_gain' else weight - 5, "unit": "kg", "confidence": 90},
                    "primary_fitness_goal": {"value": primary_goal, "confidence": 95}
                },
                "training_info": {
                    "activity_level": {"value": activity_level, "confidence": 90},
                    "gym_access": {"value": gym_access, "confidence": 95},
                    "training_days": {"value": training_days, "confidence": 90},
                    "training_experience": {"value": training_experience, "confidence": 85}
                },
                "dietary_info": {
                    "diet_type": {"value": dietary_type, "confidence": 95},
                    "dietary_restrictions": {"value": dietary_restrictions, "confidence": 90},
                    "disliked_foods": {"value": disliked_foods, "confidence": 90},
                    "regular_meals": {
                        "breakfast": {"value": regular_breakfast or "oats with protein", "confidence": 85},
                        "lunch": {"value": regular_lunch or "salad with protein", "confidence": 85},
                        "dinner": {"value": regular_dinner or "plant-based protein with vegetables", "confidence": 85}
                    }
                },
                "exercise_preferences": {
                    "dislikes": {"value": exercise_dislikes, "confidence": 90},
                    "current_routine": {"value": "none", "confidence": 95}
                }
            }

            logger.info(
                f"[WixMapping] Successfully mapped form data for: {full_name}")
            return client_data

        except Exception as e:
            logger.error(f"[WixMapping] Error mapping form data: {e}")
            return None

    @staticmethod
    async def process_wix_onboarding(ig_username: str, subscriber_id: str, client_data: Dict):
        """Process Wix onboarding using existing system."""
        try:
            logger.info(f"[WixOnboarding] Processing for {ig_username}")

            from post_onboarding_handler import PostOnboardingHandler
            import os

            # Get API key
            gemini_api_key = os.getenv(
                "GEMINI_API_KEY") or "AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y"
            handler = PostOnboardingHandler(gemini_api_key)

            # Convert to expected format
            converted_data = WixOnboardingHandler._convert_to_expected_format(
                client_data)
            if not converted_data:
                logger.error(
                    f"[WixOnboarding] Failed to convert data for {ig_username}")
                return False

            # Calculate nutrition
            nutrition_data = handler._calculate_nutrition(converted_data)
            if not nutrition_data:
                logger.error(
                    f"[WixOnboarding] Failed to calculate nutrition for {ig_username}")
                return False

            # Process onboarding
            success_flags = await handler.process_onboarding_with_fixed_data(
                ig_username=ig_username,
                subscriber_id=subscriber_id,
                direct_client_data=converted_data,
                nutrition_targets_override=nutrition_data
            )

            client_added = success_flags.get("client_added_success", False)
            meal_plan_uploaded = success_flags.get(
                "meal_plan_upload_success", False)
            workout_program_built = success_flags.get(
                "workout_program_build_success", False)

            overall_success = client_added and meal_plan_uploaded and workout_program_built

            if overall_success:
                logger.info(f"[WixOnboarding] Success for {ig_username}")

                # Store in database
                try:
                    import sqlite3
                    conn = sqlite3.connect("app/analytics_data_good.sqlite")
                    cursor = conn.cursor()

                    client_full_name = client_data.get('personal_info', {}).get(
                        'full_name', {}).get('value', ig_username)
                    client_first_name = client_data.get('personal_info', {}).get(
                        'first_name', {}).get('value', '')
                    client_last_name = client_data.get('personal_info', {}).get(
                        'last_name', {}).get('value', '')

                    cursor.execute("""
                        INSERT OR REPLACE INTO users 
                        (ig_username, subscriber_id, first_name, last_name, email, source, created_at, client_status)
                        VALUES (?, ?, ?, ?, ?, 'wix_form', ?, 'Trial Client')
                    """, (
                        ig_username, subscriber_id, client_first_name, client_last_name,
                        client_data.get('personal_info', {}).get(
                            'email', {}).get('value', ''),
                        datetime.now().isoformat()
                    ))

                    conn.commit()
                    conn.close()
                    logger.info(
                        f"[WixOnboarding] Stored user record for {ig_username}")

                except Exception as db_error:
                    logger.error(f"[WixOnboarding] Database error: {db_error}")

                # Add dashboard notification
                notification_message = f"New Trial Member - {client_full_name} (IG: @{ig_username}): "
                notification_message += "Client Added to Trainerize. " if client_added else "Client addition FAILED. "
                notification_message += "Meal Plan Added. " if meal_plan_uploaded else "Meal Plan FAILED. "
                notification_message += "Workout Program Added." if workout_program_built else "Workout Program FAILED."

                add_todo_item(ig_username, client_full_name,
                              notification_message, "pending")

            else:
                logger.error(f"[WixOnboarding] Failed for {ig_username}")

            return overall_success

        except Exception as e:
            logger.error(f"[WixOnboarding] Processing error: {e}")
            return False

    @staticmethod
    def _convert_to_expected_format(wix_client_data: Dict) -> Dict:
        """Convert Wix data to expected format."""
        try:
            personal_info = wix_client_data.get('personal_info', {})
            physical_info = wix_client_data.get('physical_info', {})
            training_info = wix_client_data.get('training_info', {})
            dietary_info = wix_client_data.get('dietary_info', {})

            # Map activity level to integer
            activity_level_str = training_info.get('activity_level', {}).get(
                'value', 'moderately_active').lower()
            activity_level_map = {
                'sedentary': 1, 'lightly active': 2, 'moderately active': 3,
                'very active': 4, 'extra active': 5
            }
            converted_activity_level = activity_level_map.get(
                activity_level_str, 3)

            # Build converted structure
            converted_data = {
                "personal_info": {
                    "email": {"value": personal_info.get('email', {}).get('value', ''), "confidence": 95},
                    "full_name": {"value": personal_info.get('full_name', {}).get('value', ''), "confidence": 95},
                    "phone": {"value": personal_info.get('phone', {}).get('value', ''), "confidence": 95},
                    "birth_date": {"value": personal_info.get('birth_date', {}).get('value', '1990-06-05'), "confidence": 95},
                    "gender": {"value": personal_info.get('gender', {}).get('value', 'male'), "confidence": 95}
                },
                "physical_info": {
                    "current_weight_kg": {"value": float(physical_info.get('weight', {}).get('value', 70)), "confidence": 95},
                    "height_cm": {"value": float(physical_info.get('height', {}).get('value', 170)), "confidence": 95},
                    "primary_fitness_goal": {"value": physical_info.get('primary_fitness_goal', {}).get('value', 'muscle_gain'), "confidence": 95},
                    "specific_weight_goal_kg": {"value": float(physical_info.get('target_weight', {}).get('value', 75)), "confidence": 90},
                    "activity_level": {"value": converted_activity_level, "confidence": 95}
                },
                "dietary_info": {
                    "diet_type": {"value": dietary_info.get('diet_type', {}).get('value', 'plant-based'), "confidence": 95},
                    "regular_meals": dietary_info.get('regular_meals', {}),
                    "meal_notes": {"value": dietary_info.get('meal_notes', {}).get('value', 'prefers plant-based meals'), "confidence": 95},
                    "other_dietary_restrictions": {"value": dietary_info.get('dietary_restrictions', {}).get('value', ''), "confidence": 95},
                    "disliked_foods": {"value": dietary_info.get('disliked_foods', {}).get('value', ''), "confidence": 95}
                },
                "training_info": {
                    "current_routine": {"value": training_info.get('current_routine', {}).get('value', 'none'), "confidence": 95},
                    "training_location": {"value": training_info.get('gym_access', {}).get('value', 'full_gym'), "confidence": 95},
                    "disliked_exercises": {"value": training_info.get('disliked_exercises', {}).get('value', ''), "confidence": 95},
                    "liked_exercises": {"value": training_info.get('liked_exercises', {}).get('value', ''), "confidence": 95},
                    "training_days": {"value": training_info.get('training_days', {}).get('value', 'monday-friday'), "confidence": 95}
                },
                "general_info": {
                    "location": {"value": personal_info.get('location', {}).get('value', 'Melbourne'), "confidence": 95}
                }
            }

            logger.info(
                f"[WixConversion] Successfully converted data structure")
            return converted_data

        except Exception as e:
            logger.error(f"[WixConversion] Conversion error: {e}")
            return None
