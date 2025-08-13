"""
Form Check Handler
=================
Handles form check video analysis and exercise technique feedback.
"""

from techniqueanalysis import get_video_analysis
from app.dashboard_modules.dashboard_sqlite_utils import add_response_to_review_queue
from webhook_handlers import get_user_data, update_analytics_data, call_gemini_with_retry
import logging
import subprocess
import os
from typing import Dict, Any, Optional, Tuple

# Import from the main webhook_handlers (not the app one)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("shanbot_formcheck")


class FormCheckHandler:
    """Handles form check video analysis."""

    @staticmethod
    async def handle_form_check(ig_username: str, message_text: str, subscriber_id: str,
                                first_name: str, last_name: str, user_message_timestamp_iso: str) -> bool:
        """Handle form check video analysis."""
        try:
            # Check if message contains video or form check request
            is_form_check = await FormCheckHandler._is_form_check_request(message_text)

            if not is_form_check:
                return False

            logger.info(f"[FormCheck] Handling form check for {ig_username}")

            # Get user data
            _, metrics, _ = get_user_data(ig_username, subscriber_id)
            client_analysis = metrics.get('client_analysis', {})

            # Check if video URL is present in the message
            video_url = FormCheckHandler._extract_video_url(message_text)

            if video_url:
                # Analyze the video using the URL
                analysis_result = await FormCheckHandler._analyze_form_check_video_url(
                    video_url, message_text, ig_username, client_analysis
                )

                if analysis_result:
                    response = analysis_result
                else:
                    response = "I'm having trouble analyzing your form check video right now. Can you try uploading it again or describe what exercise you're doing?"
            else:
                # No video found, ask for clarification
                response = await FormCheckHandler._generate_form_check_request_response(message_text, client_analysis)

            # Queue response
            review_id = add_response_to_review_queue(
                user_ig_username=ig_username,
                user_subscriber_id=subscriber_id,
                incoming_message_text=message_text,
                incoming_message_timestamp=user_message_timestamp_iso,
                generated_prompt_text="Form check analysis",
                proposed_response_text=response,
                prompt_type="form_check"
            )

            if review_id:
                logger.info(
                    f"[FormCheck] Queued form check response (ID: {review_id}) for {ig_username}")
                update_analytics_data(
                    ig_username, message_text, response, subscriber_id, first_name, last_name)
                return True

            return False

        except Exception as e:
            logger.error(
                f"[FormCheck] Error handling form check for {ig_username}: {e}")
            return False

    @staticmethod
    async def _is_form_check_request(message_text: str) -> bool:
        """Detect if message is a form check request."""
        # Check for video URL first - if there's a video, likely a form check
        if FormCheckHandler._has_video_url(message_text):
            return True

        form_check_keywords = [
            'form check', 'check my form', 'form', 'technique',
            'how did i do', 'how does this look', 'feedback on',
            'critique', 'analyze', 'video', 'movement'
        ]

        exercise_keywords = [
            'squat', 'deadlift', 'bench', 'press', 'curl',
            'row', 'pull', 'push', 'lift', 'exercise'
        ]

        message_lower = message_text.lower()

        # Must have form check indicator OR exercise + request for feedback
        has_form_check = any(
            keyword in message_lower for keyword in form_check_keywords)
        has_exercise = any(
            keyword in message_lower for keyword in exercise_keywords)
        has_question = '?' in message_text or 'how' in message_lower

        return has_form_check or (has_exercise and has_question)

    @staticmethod
    def _has_video_url(message_text: str) -> bool:
        """Check if message contains video URLs."""
        import re
        url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"
        return bool(re.search(url_pattern, message_text))

    @staticmethod
    def _extract_video_url(message_text: str) -> Optional[str]:
        """Extract video URL from message."""
        import re
        url_pattern = r"(https?://lookaside\.fbsbx\.com/ig_messaging_cdn/\?asset_id=[\w-]+&signature=[\w\-_.~]+)"
        match = re.search(url_pattern, message_text)
        return match.group(1) if match else None

    @staticmethod
    async def _check_video_availability(ig_username: str, timestamp: str) -> bool:
        """Check if video is available for analysis."""
        try:
            # Look for video files in client directories
            video_extensions = ['.mp4', '.mov', '.avi', '.m4v']

            possible_paths = [
                f"clients/{ig_username}/",
                f"clients/{ig_username.lower()}/",
                f"temp_videos/{ig_username}/",
                "temp_videos/"
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    for file in os.listdir(path):
                        if any(file.lower().endswith(ext) for ext in video_extensions):
                            # Check if file is recent (within last hour)
                            file_path = os.path.join(path, file)
                            file_time = os.path.getmtime(file_path)

                            # If timestamp available, check proximity
                            if timestamp:
                                try:
                                    from datetime import datetime
                                    import dateutil.parser

                                    msg_time = dateutil.parser.parse(
                                        timestamp).timestamp()
                                    if abs(file_time - msg_time) < 3600:  # Within 1 hour
                                        logger.info(
                                            f"[FormCheck] Found recent video for {ig_username}: {file}")
                                        return True
                                except:
                                    pass

                            # Fallback: check if file is less than 1 hour old
                            import time
                            if time.time() - file_time < 3600:
                                logger.info(
                                    f"[FormCheck] Found recent video for {ig_username}: {file}")
                                return True

            return False

        except Exception as e:
            logger.error(
                f"[FormCheck] Error checking video availability for {ig_username}: {e}")
            return False

    @staticmethod
    async def _analyze_form_check_video_url(video_url: str, message_text: str, ig_username: str, client_analysis: Dict) -> Optional[str]:
        """Analyze form check video using URL and get_video_analysis."""
        try:
            logger.info(
                f"[FormCheckVideo] Analyzing video for {ig_username}: {video_url[:50]}...")

            # Extract description from message (remove URL)
            user_description = message_text.replace(video_url, "").strip()

            # Use the techniqueanalysis function to analyze the video
            import os
            analysis_result = get_video_analysis(
                video_url=video_url,
                api_key=os.getenv("GEMINI_API_KEY",
                                  "AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y"),
                primary_model="gemini-2.5-flash-lite",
                fallback_model="gemini-2.0-flash-thinking-exp-01-21",
                final_fallback_model="gemini-2.0-flash"
            )

            if not analysis_result or "Error" in analysis_result or "failed" in analysis_result.lower():
                logger.error(
                    f"[FormCheckVideo] Failed to analyze video: {analysis_result}")
                return "Sorry mate, had a bit of trouble analysing that video. Can you try uploading it again or describe what exercise you're doing?"

            # Add some context based on client analysis if available
            try:
                if client_analysis and isinstance(analysis_result, str):
                    context_prompt = f"""
                    Enhance this form check analysis with client-specific advice:
                    
                    Original Analysis: {analysis_result}
                    
                    Client Profile: {client_analysis}
                    User Description: {user_description}
                    
                    Provide the enhanced analysis in Shannon's casual Australian coaching style.
                    Keep it encouraging but specific about technique improvements.
                    """

                    enhanced_analysis = await call_gemini_with_retry("gemini-2.5-flash-lite", context_prompt)
                    if enhanced_analysis:
                        return enhanced_analysis

            except Exception as e:
                logger.error(f"[FormCheckVideo] Error enhancing analysis: {e}")

            # Return original analysis if enhancement fails
            return analysis_result

        except Exception as e:
            logger.error(
                f"[FormCheckVideo] Error analyzing video for {ig_username}: {e}")
            return "Sorry mate, had trouble analyzing that video. Can you try again or tell me what exercise you're working on?"

    @staticmethod
    async def _analyze_form_check_video(ig_username: str, message_text: str, client_analysis: Dict) -> Optional[str]:
        """Analyze form check video using technique analysis."""
        try:
            logger.info(
                f"[FormCheck] Starting video analysis for {ig_username}")

            # Try to run technique analysis script
            try:
                # Look for technique analysis script
                script_path = "techniqueanalysis.py"
                if not os.path.exists(script_path):
                    logger.warning(
                        f"[FormCheck] Technique analysis script not found: {script_path}")
                    return await FormCheckHandler._generate_manual_form_feedback(message_text, client_analysis)

                # Run the analysis
                result = subprocess.run([
                    "python", script_path,
                    "--username", ig_username,
                    "--message", message_text
                ], capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    analysis_output = result.stdout.strip()
                    if analysis_output:
                        logger.info(
                            f"[FormCheck] Successfully analyzed video for {ig_username}")
                        return analysis_output
                    else:
                        logger.warning(
                            f"[FormCheck] Empty analysis output for {ig_username}")
                else:
                    logger.error(
                        f"[FormCheck] Analysis script failed for {ig_username}: {result.stderr}")

            except subprocess.TimeoutExpired:
                logger.error(
                    f"[FormCheck] Video analysis timeout for {ig_username}")
            except Exception as script_error:
                logger.error(
                    f"[FormCheck] Script execution error for {ig_username}: {script_error}")

            # Fallback to manual feedback
            return await FormCheckHandler._generate_manual_form_feedback(message_text, client_analysis)

        except Exception as e:
            logger.error(
                f"[FormCheck] Error analyzing video for {ig_username}: {e}")
            return None

    @staticmethod
    async def _generate_manual_form_feedback(message_text: str, client_analysis: Dict) -> str:
        """Generate manual form feedback when video analysis isn't available."""
        try:
            feedback_prompt = f"""
            Provide form check feedback for this request:
            
            Request: "{message_text}"
            
            Client Profile: {client_analysis}
            
            Since I can't analyze the video directly, provide:
            1. General technique cues for the exercise mentioned
            2. Common mistakes to watch for
            3. Specific advice based on their profile
            4. Request for more details if needed
            
            Be encouraging and helpful while acknowledging the limitation.
            """

            response = await call_gemini_with_retry("gemini-2.5-flash-lite", feedback_prompt)

            if response:
                return response
            else:
                return "I'd love to help with your form check! I'm having some technical difficulties analyzing videos right now. Can you describe what exercise you're doing and any specific concerns you have? I can provide technique tips based on that!"

        except Exception as e:
            logger.error(f"[FormCheck] Error generating manual feedback: {e}")
            return "I'd be happy to help with your form check! Can you tell me more about the exercise and what specific feedback you're looking for?"

    @staticmethod
    async def _generate_form_check_request_response(message_text: str, client_analysis: Dict) -> str:
        """Generate response when no video is found but form check is requested."""
        try:
            response_prompt = f"""
            Generate a helpful response for a form check request where no video was found:
            
            Request: "{message_text}"
            
            Client Profile: {client_analysis}
            
            The response should:
            1. Acknowledge their form check request
            2. Ask them to upload a video if they haven't
            3. Offer to provide general technique tips in the meantime
            4. Be encouraging and supportive
            
            Keep it conversational and helpful.
            """

            response = await call_gemini_with_retry("gemini-2.5-flash-lite", response_prompt)

            if response:
                return response
            else:
                return "I'd love to check your form! Can you upload a video of your exercise? If you already sent one, it might take a moment to process. In the meantime, let me know what exercise you're working on and I can share some key technique points!"

        except Exception as e:
            logger.error(f"[FormCheck] Error generating request response: {e}")
            return "I'd be happy to help with your form check! Please upload a video of your exercise so I can give you specific feedback."
