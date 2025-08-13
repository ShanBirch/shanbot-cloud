import subprocess
import time
import os
import sys
from fastapi import FastAPI, Request
import uvicorn
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("webhook_runner")

# Import the FastAPI app from manychat_webhook.py
try:
    from app.manychat_webhook import app
    logger.info("Successfully imported the webhook app")
except ImportError as e:
    logger.error(f"Error importing webhook app: {str(e)}")
    sys.exit(1)


def run_ngrok():
    """Start ngrok to expose the local webhook server to the internet"""
    ngrok_path = r"C:\Users\Shannon\Downloads\ngrok-temp\ngrok.exe"

    # Check if the ngrok path exists
    if not os.path.exists(ngrok_path):
        logger.error(f"Ngrok executable not found at {ngrok_path}")
        logger.info(
            "Please download ngrok from https://ngrok.com/download and place it in the correct location")
        return None

    # Start ngrok in a separate process
    logger.info("Starting ngrok tunnel...")
    try:
        ngrok_process = subprocess.Popen(
            [ngrok_path, "http", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait a bit for ngrok to start
        time.sleep(5)

        # Display information to the user
        logger.info("\n" + "="*60)
        logger.info(
            "Ngrok is running - your public URL will be visible in the ngrok interface")
        logger.info(
            "Use the URL shown in the ngrok terminal that ends with /webhook/manychat")
        logger.info(
            "For example: https://xxxx-xx-xx-xxx-xxx.ngrok-free.app/webhook/manychat")
        logger.info("="*60 + "\n")

        # Also add a test endpoint you can use
        logger.info("You can test the webhook with the following endpoints:")
        logger.info("- Health check: <your-ngrok-url>/health")
        logger.info("- Test update: <your-ngrok-url>/test/1243475080")
        logger.info("="*60 + "\n")

        # Return the process so it can be terminated later
        return ngrok_process
    except Exception as e:
        logger.error(f"Error starting ngrok: {str(e)}")
        return None


if __name__ == "__main__":
    logger.info("Starting ManyChat webhook server...")

    # Start ngrok in a separate thread
    ngrok_process = run_ngrok()

    # Run the API server
    try:
        logger.info("Starting FastAPI server...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        # Clean up processes
        if ngrok_process:
            ngrok_process.terminate()
            logger.info("Ngrok tunnel stopped")
