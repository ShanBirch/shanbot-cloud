import google.generativeai as genai
import logging
import time
from typing import Optional
from .config import (
    GEMINI_API_KEY,
    GEMINI_MODEL_PRO,
    GEMINI_MODEL_FLASH,
    GEMINI_MODEL_FLASH_STANDARD,
    RETRY_DELAY,
    MAX_RETRIES
)

logger = logging.getLogger(__name__)

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}", exc_info=True)


def call_gemini_with_retry(model_name: str, prompt: str, retry_count: int = 0) -> Optional[str]:
    """
    Call Gemini API with retry logic and multiple fallback models.
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) and retry_count < MAX_RETRIES:
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Rate limit hit for {model_name}. Falling back to flash-thinking model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            else:
                wait_time = RETRY_DELAY * (retry_count + 1)
                logger.warning(
                    f"Rate limit hit. Waiting {wait_time} seconds before retry {retry_count + 1} on {model_name}")
                time.sleep(wait_time)
                return call_gemini_with_retry(model_name, prompt, retry_count + 1)
        elif retry_count < MAX_RETRIES:
            if model_name == GEMINI_MODEL_PRO:
                logger.warning(
                    f"Main model failed: {e}. Trying first fallback model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt, retry_count + 1)
            elif model_name == GEMINI_MODEL_FLASH:
                logger.warning(
                    f"First fallback model failed: {e}. Trying second fallback model after delay.")
                time.sleep(RETRY_DELAY)
                return call_gemini_with_retry(GEMINI_MODEL_FLASH_STANDARD, prompt, retry_count + 1)
        logger.error(f"All Gemini attempts failed: {e}")
        return None


async def get_ai_response(prompt: str) -> Optional[str]:
    """Get AI response using Gemini models with fallbacks."""
    try:
        # First try with GEMINI_MODEL_PRO
        response = call_gemini_with_retry(GEMINI_MODEL_PRO, prompt)
        if response:
            return response

        # If that fails, try GEMINI_MODEL_FLASH
        logger.warning("Primary model failed, trying FLASH model...")
        response = call_gemini_with_retry(GEMINI_MODEL_FLASH, prompt)
        if response:
            return response

        # Last resort, try GEMINI_MODEL_FLASH_STANDARD
        logger.warning("FLASH model failed, trying FLASH_STANDARD model...")
        response = call_gemini_with_retry(GEMINI_MODEL_FLASH_STANDARD, prompt)
        if response:
            return response

        logger.error("All Gemini models failed to generate response")
        return None

    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return None
