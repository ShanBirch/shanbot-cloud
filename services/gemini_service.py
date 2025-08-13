import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Gemini API key and model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Default to gemini-2.0-flash-thinking-exp-01-21 if not specified
GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL",
                         "gemini-2.0-flash-thinking-exp-01-21")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY environment variable not set")
else:
    logger.info(f"Using Gemini model: {GEMINI_MODEL}")

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)


class GeminiService:
    """Service for interacting with Google's Gemini API"""

    def __init__(self):
        """Initialize the Gemini service"""
        self.models = None
        if GEMINI_API_KEY:
            try:
                self.models = genai.list_models()
                logger.info(
                    f"Available models: {[model.name for model in self.models]}")
            except Exception as e:
                logger.error(f"Error listing models: {e}")
                logger.error(traceback.format_exc())

    async def complete(self, prompt, model=None, temperature=0.7, max_tokens=2048):
        """
        Generate text completion using Gemini

        Args:
            prompt (str): The prompt to generate a completion for
            model (str, optional): The model to use. Defaults to None, which will use the GEMINI_MODEL.
            temperature (float, optional): Controls randomness. Defaults to 0.7.
            max_tokens (int, optional): Max tokens to generate. Defaults to 2048.

        Returns:
            str: The text response from Gemini
        """
        try:
            # Use the specified model or fall back to GEMINI_MODEL from .env
            model_to_use = model or GEMINI_MODEL
            logger.info(f"Using model for completion: {model_to_use}")

            # Create the generative model
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            # Initialize model
            model = genai.GenerativeModel(
                model_name=model_to_use,
                generation_config=generation_config
            )

            # Generate completion
            response = model.generate_content(prompt)

            if response.text:
                # Just return the text directly instead of the JSON object
                return response.text
            else:
                logger.warning("No text generated in response")
                return "Sorry, I couldn't generate a response."

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error generating completion: {error_message}")
            logger.error(traceback.format_exc())
            return "Sorry, I couldn't generate a response."

    async def analyze_sentiment(self, text):
        """
        Analyze sentiment of a text using Gemini

        Args:
            text (str): The text to analyze

        Returns:
            str: The sentiment analysis result
        """
        prompt = f"""
        Please analyze the sentiment of the following text and classify it as one of:
        - Positive
        - Negative
        - Neutral
        
        Also provide a brief explanation of why you classified it that way.
        
        Text to analyze: "{text}"
        
        Format your response as:
        Sentiment: [classification]
        Explanation: [brief explanation]
        """

        result = await self.complete(prompt)
        return result

    async def split_message(self, message):
        """
        Split a message into multiple parts if it should be sent as multiple messages

        Args:
            message (str): The message to split

        Returns:
            list: A list of message parts
        """
        prompt = f"""
        Analyze this message and determine if it should be sent as a single message or split into multiple messages:
        
        "{message}"
        
        If it should be a single message, respond with:
        SINGLE_MESSAGE
        
        If it should be split, provide each part on a new line with "PART:" prefix, like:
        PART: First part of the message
        PART: Second part of the message
        
        Base your decision on natural breaks, message length, and conversational flow.
        """

        result = await self.complete(prompt)

        if "SINGLE_MESSAGE" in result:
            return [message]

        parts = []
        for line in result.split("\n"):
            if line.strip().startswith("PART:"):
                part = line.strip()[5:].strip()
                if part:
                    parts.append(part)

        if not parts:
            return [message]

        return parts


# Create a singleton instance
gemini_service = GeminiService()
