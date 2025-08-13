import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from .config import ANALYTICS_FILE_PATH
from .models import CalorieTracking

logger = logging.getLogger(__name__)


def update_calorie_tracking(ig_username: str, calories: int, protein: int, carbs: int, fats: int) -> Optional[Dict]:
    """Update user's calorie tracking and return remaining values."""
    try:
        logger.info(
            f"Updating calorie tracking for {ig_username} - Calories: {calories}, P: {protein}g, C: {carbs}g, F: {fats}g")

        with open(ANALYTICS_FILE_PATH, 'r') as f:
            data = json.load(f)

        # Find the user
        for user_id, user_data in data['conversations'].items():
            if isinstance(user_data, dict) and 'metrics' in user_data:
                metrics = user_data['metrics']
                if isinstance(metrics, dict) and metrics.get('ig_username') == ig_username:
                    calorie_tracking = metrics.get('calorie_tracking', {})
                    logger.info(
                        f"Found user's calorie tracking data: {json.dumps(calorie_tracking, indent=2)}")

                    # Check if it's a new day
                    current_date = datetime.now(
                        timezone.utc).strftime("%Y-%m-%d")
                    if calorie_tracking.get('current_date') != current_date:
                        logger.info(f"New day detected. Resetting tracking.")
                        # Reset for new day
                        calorie_tracking.update({
                            'current_date': current_date,
                            'calories_consumed': 0,
                            'remaining_calories': calorie_tracking['daily_target'],
                            'macros': {
                                'protein': {
                                    'daily_target': calorie_tracking['macros']['protein']['daily_target'],
                                    'consumed': 0,
                                    'remaining': calorie_tracking['macros']['protein']['daily_target']
                                },
                                'carbs': {
                                    'daily_target': calorie_tracking['macros']['carbs']['daily_target'],
                                    'consumed': 0,
                                    'remaining': calorie_tracking['macros']['carbs']['daily_target']
                                },
                                'fats': {
                                    'daily_target': calorie_tracking['macros']['fats']['daily_target'],
                                    'consumed': 0,
                                    'remaining': calorie_tracking['macros']['fats']['daily_target']
                                }
                            },
                            'meals_today': []
                        })

                    # Update consumed values
                    calorie_tracking['calories_consumed'] += calories
                    calorie_tracking['remaining_calories'] = calorie_tracking['daily_target'] - \
                        calorie_tracking['calories_consumed']

                    # Update macros
                    calorie_tracking['macros']['protein']['consumed'] += protein
                    calorie_tracking['macros']['protein']['remaining'] = calorie_tracking['macros'][
                        'protein']['daily_target'] - calorie_tracking['macros']['protein']['consumed']

                    calorie_tracking['macros']['carbs']['consumed'] += carbs
                    calorie_tracking['macros']['carbs']['remaining'] = calorie_tracking['macros'][
                        'carbs']['daily_target'] - calorie_tracking['macros']['carbs']['consumed']

                    calorie_tracking['macros']['fats']['consumed'] += fats
                    calorie_tracking['macros']['fats']['remaining'] = calorie_tracking['macros'][
                        'fats']['daily_target'] - calorie_tracking['macros']['fats']['consumed']

                    # Add meal to today's meals
                    meal_entry = {
                        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "calories": calories,
                        "protein": protein,
                        "carbs": carbs,
                        "fats": fats
                    }
                    calorie_tracking['meals_today'].append(meal_entry)

                    # Save updated data
                    metrics['calorie_tracking'] = calorie_tracking
                    with open(ANALYTICS_FILE_PATH, 'w') as f:
                        json.dump(data, f, indent=2)

                    # Return remaining values
                    remaining = {
                        "remaining_calories": calorie_tracking['remaining_calories'],
                        "remaining_protein": calorie_tracking['macros']['protein']['remaining'],
                        "remaining_carbs": calorie_tracking['macros']['carbs']['remaining'],
                        "remaining_fats": calorie_tracking['macros']['fats']['remaining']
                    }
                    logger.info(
                        f"Returning remaining values: {json.dumps(remaining, indent=2)}")
                    return remaining

        logger.warning(f"User {ig_username} not found in analytics data")
        return None

    except Exception as e:
        logger.error(f"Error updating calorie tracking: {e}", exc_info=True)
        return None


def get_current_remaining_macros(ig_username: str) -> Optional[Dict]:
    """Get the current remaining calories and macros from analytics data."""
    try:
        with open(ANALYTICS_FILE_PATH, 'r') as f:
            data = json.load(f)

        # Find the user
        for user_id, user_data in data['conversations'].items():
            if isinstance(user_data, dict) and 'metrics' in user_data:
                metrics = user_data['metrics']
                if isinstance(metrics, dict) and metrics.get('ig_username') == ig_username:
                    calorie_tracking = metrics.get('calorie_tracking', {})

                    # Return current remaining values
                    return {
                        "remaining_calories": calorie_tracking.get('remaining_calories', 0),
                        "remaining_protein": calorie_tracking.get('macros', {}).get('protein', {}).get('remaining', 0),
                        "remaining_carbs": calorie_tracking.get('macros', {}).get('carbs', {}).get('remaining', 0),
                        "remaining_fats": calorie_tracking.get('macros', {}).get('fats', {}).get('remaining', 0)
                    }

        logger.warning(f"User {ig_username} not found in analytics data")
        return None

    except Exception as e:
        logger.error(f"Error getting remaining macros: {e}", exc_info=True)
        return None


def format_food_analysis_response(calories: int, protein: int, carbs: int, fats: int, ig_username: str) -> str:
    """Format the food analysis response with remaining calories and macros."""
    try:
        # Update tracking and get remaining values
        remaining = update_calorie_tracking(
            ig_username, calories, protein, carbs, fats)

        if remaining:
            return (f"This meal contains:\n"
                    f"Calories: {calories}kcal (Remaining today: {remaining['remaining_calories']}kcal)\n"
                    f"Protein: {protein}g (Remaining: {remaining['remaining_protein']}g)\n"
                    f"Carbs: {carbs}g (Remaining: {remaining['remaining_carbs']}g)\n"
                    f"Fats: {fats}g (Remaining: {remaining['remaining_fats']}g)")
        else:
            return f"Calories = {calories}, Protein = {protein}g, Carbs = {carbs}g, Fats = {fats}g"

    except Exception as e:
        logger.error(f"Error formatting food analysis response: {e}")
        return f"Calories = {calories}, Protein = {protein}g, Carbs = {carbs}g, Fats = {fats}g"
