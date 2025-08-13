"""
Shanbot Nutrition Handler
========================
Handles all nutrition and diet-related messages including:
- Calorie tracking requests
- Meal planning questions
- Food logging
- Nutritional advice
- Diet modifications
"""

import logging
import asyncio
import os
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime

from utilities import (
    get_user_data,
    update_analytics_data,
    call_gemini_with_retry,
    update_manychat_fields
)
from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
from app import prompts

logger = logging.getLogger("shanbot_nutrition")


class NutritionHandler:
    """Handler for nutrition and diet-related messages."""

    def __init__(self):
        """Initialize nutrition handler."""
        logger.info("NutritionHandler initialized")

    async def handle_nutrition_question(self, ig_username: str, message_text: str,
                                        subscriber_id: str, first_name: str, last_name: str,
                                        timestamp: str) -> bool:
        """Handle nutrition-related requests."""
        try:
            logger.info(
                f"[Nutrition] Processing request from {ig_username}: {message_text[:50]}...")

            # Analyze nutrition request type
            request_type = await self._analyze_nutrition_request(message_text)

            if request_type == "calorie_tracking":
                return await self._handle_calorie_tracking(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "meal_planning":
                return await self._handle_meal_planning(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "food_logging":
                return await self._handle_food_logging(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "recipe_request":
                return await self._handle_recipe_request(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            elif request_type == "nutritional_advice":
                return await self._handle_nutritional_advice(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

            else:
                # General nutrition question
                return await self._handle_general_nutrition_question(
                    ig_username, message_text, subscriber_id, first_name, last_name, timestamp
                )

        except Exception as e:
            logger.error(
                f"[Nutrition] Error handling request from {ig_username}: {e}")
            return False

    async def _analyze_nutrition_request(self, message_text: str) -> str:
        """Analyze the type of nutrition request."""
        try:
            analysis_prompt = f"""
            Analyze this nutrition-related message and classify the request type.
            
            MESSAGE: "{message_text}"
            
            REQUEST TYPES:
            - calorie_tracking: Wants to track calories or macros
            - meal_planning: Asking about meal plans or meal prep
            - food_logging: Reporting what they ate for analysis
            - recipe_request: Asking for specific recipes
            - nutritional_advice: General nutrition guidance/education
            - supplement_question: About supplements or vitamins
            
            Reply with just the request type.
            """

            response = await call_gemini_with_retry("gemini-2.0-flash", analysis_prompt)
            request_type = response.strip().lower()

            valid_types = ["calorie_tracking", "meal_planning", "food_logging",
                           "recipe_request", "nutritional_advice", "supplement_question"]

            if request_type not in valid_types:
                request_type = "nutritional_advice"

            logger.info(f"[Nutrition] Request type: {request_type}")
            return request_type

        except Exception as e:
            logger.error(f"[Nutrition] Request analysis error: {e}")
            return "nutritional_advice"

    async def _handle_calorie_tracking(self, ig_username: str, message_text: str,
                                       subscriber_id: str, first_name: str, last_name: str,
                                       timestamp: str) -> bool:
        """Handle calorie tracking requests."""
        try:
            # Check if user has access to calorie tracking tools
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)
            has_trainerize = metrics.get('has_trainerize_account', False)

            # Try to use CalorieTracker if available
            calorie_response = await self._try_calorie_tracker(ig_username, message_text)

            if calorie_response:
                # CalorieTracker handled it
                logger.info(
                    f"[Nutrition] CalorieTracker processed request for {ig_username}")
                return True

            # Generate manual calorie tracking response
            nutrition_targets = metrics.get('nutrition_targets', {})
            daily_calories = nutrition_targets.get('calories', 'Not set')
            daily_protein = nutrition_targets.get('protein', 'Not set')

            prompt = f"""
            A client is asking about calorie tracking.
            
            CLIENT INFO:
            - Name: {first_name}
            - Has Trainerize: {has_trainerize}
            - Daily calorie target: {daily_calories}
            - Daily protein target: {daily_protein}g
            
            REQUEST: "{message_text}"
            
            Generate a helpful response that:
            1. Addresses their calorie tracking question
            2. Provides practical tracking tips
            3. Mentions their targets if available
            4. Suggests tools/apps if they don't have Trainerize
            5. Uses Shannon's supportive coaching tone
            
            Keep it actionable and encouraging.
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
                    prompt_type="nutrition_calorie_tracking"
                )

                if review_id:
                    logger.info(
                        f"[Nutrition] Queued calorie tracking response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_calorie_question=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Nutrition] Calorie tracking error: {e}")
            return False

    async def _try_calorie_tracker(self, ig_username: str, message_text: str) -> bool:
        """Try to use the CalorieTracker system."""
        try:
            # Check if CalorieTracker is available
            try:
                from calorie_manager_calorietracker import CalorieTracker_CalorieTracker

                # Initialize CalorieTracker
                calorie_tracker = CalorieTracker_CalorieTracker()

                # Try to process the calorie request
                # This would need to be adapted based on the CalorieTracker interface
                success = await calorie_tracker.process_food_entry(ig_username, message_text)

                if success:
                    logger.info(
                        f"[Nutrition] CalorieTracker successfully processed for {ig_username}")
                    return True

            except ImportError:
                logger.info(
                    "[Nutrition] CalorieTracker not available, using manual processing")
            except Exception as e:
                logger.warning(f"[Nutrition] CalorieTracker error: {e}")

            return False

        except Exception as e:
            logger.error(f"[Nutrition] CalorieTracker attempt error: {e}")
            return False

    async def _handle_meal_planning(self, ig_username: str, message_text: str,
                                    subscriber_id: str, first_name: str, last_name: str,
                                    timestamp: str) -> bool:
        """Handle meal planning requests."""
        try:
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            diet_type = metrics.get('diet_type', 'Unknown')
            dietary_restrictions = metrics.get('dietary_restrictions', 'None')
            nutrition_targets = metrics.get('nutrition_targets', {})

            prompt = f"""
            A client is asking about meal planning.
            
            CLIENT INFO:
            - Name: {first_name}
            - Diet type: {diet_type}
            - Dietary restrictions: {dietary_restrictions}
            - Nutrition targets: {nutrition_targets}
            
            REQUEST: "{message_text}"
            
            Generate a meal planning response that:
            1. Addresses their specific request
            2. Considers their diet type and restrictions
            3. Provides practical meal prep tips
            4. Suggests balanced meal combinations
            5. Uses Shannon's knowledgeable but accessible tone
            
            Keep it practical and actionable.
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
                    prompt_type="nutrition_meal_planning"
                )

                if review_id:
                    logger.info(
                        f"[Nutrition] Queued meal planning response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_meal_planning_request=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Nutrition] Meal planning error: {e}")
            return False

    async def _handle_food_logging(self, ig_username: str, message_text: str,
                                   subscriber_id: str, first_name: str, last_name: str,
                                   timestamp: str) -> bool:
        """Handle food logging and analysis."""
        try:
            # Analyze the food log entry
            food_analysis = await self._analyze_food_entry(message_text)

            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)
            nutrition_targets = metrics.get('nutrition_targets', {})

            prompt = f"""
            A client is sharing what they ate for analysis/feedback.
            
            CLIENT: {first_name}
            FOOD LOG: "{message_text}"
            ANALYSIS: {food_analysis}
            NUTRITION TARGETS: {nutrition_targets}
            
            Provide feedback that:
            1. Acknowledges their food choices positively
            2. Gives constructive nutritional feedback
            3. Suggests improvements if needed
            4. Relates to their goals and targets
            5. Uses Shannon's encouraging coaching style
            
            Be supportive while being helpful.
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
                    prompt_type="nutrition_food_logging"
                )

                if review_id:
                    logger.info(
                        f"[Nutrition] Queued food logging response for {ig_username}")

                    # Store food log for tracking
                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_food_log=message_text,
                        last_food_log_date=datetime.now().date().isoformat()
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Nutrition] Food logging error: {e}")
            return False

    async def _analyze_food_entry(self, message_text: str) -> str:
        """Analyze a food entry for nutritional content."""
        try:
            analysis_prompt = f"""
            Analyze this food log entry for nutritional content and balance.
            
            FOOD LOG: "{message_text}"
            
            Provide a brief analysis covering:
            - Overall nutritional balance
            - Protein content assessment
            - Vegetable/fiber content
            - Potential improvements
            
            Keep it concise and constructive.
            """

            analysis = await call_gemini_with_retry("gemini-2.0-flash", analysis_prompt)
            return analysis or "General food intake noted."

        except Exception as e:
            logger.error(f"[Nutrition] Food analysis error: {e}")
            return "Food intake logged for review."

    async def _handle_recipe_request(self, ig_username: str, message_text: str,
                                     subscriber_id: str, first_name: str, last_name: str,
                                     timestamp: str) -> bool:
        """Handle recipe requests."""
        try:
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            diet_type = metrics.get('diet_type', 'Unknown')
            dietary_restrictions = metrics.get('dietary_restrictions', 'None')

            prompt = f"""
            A client is asking for a recipe.
            
            CLIENT INFO:
            - Name: {first_name}
            - Diet type: {diet_type}
            - Dietary restrictions: {dietary_restrictions}
            
            REQUEST: "{message_text}"
            
            Provide a recipe response that:
            1. Addresses their specific request
            2. Fits their diet type and restrictions
            3. Includes ingredients and basic instructions
            4. Mentions nutritional benefits
            5. Uses Shannon's helpful and encouraging tone
            
            Keep it practical and easy to follow.
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
                    prompt_type="nutrition_recipe_request"
                )

                if review_id:
                    logger.info(
                        f"[Nutrition] Queued recipe response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_recipe_request=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Nutrition] Recipe request error: {e}")
            return False

    async def _handle_nutritional_advice(self, ig_username: str, message_text: str,
                                         subscriber_id: str, first_name: str, last_name: str,
                                         timestamp: str) -> bool:
        """Handle general nutritional advice requests."""
        try:
            user_data, metrics, conversations = get_user_data(
                ig_username, subscriber_id)

            fitness_goal = metrics.get('primary_fitness_goal', 'Unknown')
            diet_type = metrics.get('diet_type', 'Unknown')

            prompt = f"""
            A client is asking for nutritional advice.
            
            CLIENT INFO:
            - Name: {first_name}
            - Fitness goal: {fitness_goal}
            - Diet type: {diet_type}
            
            QUESTION: "{message_text}"
            
            Provide nutritional advice that:
            1. Addresses their specific question
            2. Considers their goals and diet type
            3. Gives evidence-based guidance
            4. Includes practical implementation tips
            5. Uses Shannon's knowledgeable but approachable tone
            
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
                    prompt_type="nutrition_advice"
                )

                if review_id:
                    logger.info(
                        f"[Nutrition] Queued nutritional advice response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_nutrition_advice_request=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Nutrition] Nutritional advice error: {e}")
            return False

    async def _handle_general_nutrition_question(self, ig_username: str, message_text: str,
                                                 subscriber_id: str, first_name: str, last_name: str,
                                                 timestamp: str) -> bool:
        """Handle general nutrition questions that don't fit other categories."""
        try:
            prompt = f"""
            A user has a general nutrition question.
            
            USER: {first_name}
            QUESTION: "{message_text}"
            
            Provide a helpful response that:
            1. Addresses their question clearly
            2. Gives practical, actionable advice
            3. Encourages healthy habits
            4. Uses Shannon's supportive coaching style
            5. Suggests they consider coaching for personalized nutrition help
            
            Keep it encouraging and informative.
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
                    prompt_type="nutrition_general_question"
                )

                if review_id:
                    logger.info(
                        f"[Nutrition] Queued general nutrition response for {ig_username}")

                    update_analytics_data(
                        ig_username, message_text, response, subscriber_id, first_name, last_name,
                        last_general_nutrition_question=message_text
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"[Nutrition] General nutrition question error: {e}")
            return False
