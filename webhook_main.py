"""
Shanbot Webhook - Main Application
==================================
Clean, modular webhook application for Shanbot Instagram automation.

This is the main entry point that coordinates all webhook functionality
through a clean, organized structure.
"""

import sqlite3
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Import update_analytics_data from app.analytics
from app.analytics import update_analytics_data
from action_router import ActionRouter
from calendly_integration import run_booking_check

import uvicorn
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Add app directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(current_dir, 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Configure logging with comprehensive noise filtering
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('shanbot_webhook.log'),
        logging.StreamHandler()
    ]
)

# Create a comprehensive noise filter


class NoiseFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage().lower()
        # Hide "changes detected" messages
        if "changes detected" in message:
            return False
        # Hide WatchFiles messages
        if "watchfiles" in message:
            return False
        # Hide reloader messages
        if "reloader" in message:
            return False
        # Hide uvicorn access logs
        if "uvicorn.access" in record.name:
            return False
        # Hide multiprocessing messages
        if "multiprocessing" in message:
            return False
        # Hide spawn messages
        if "spawn" in message:
            return False
        return True


# Apply the filter to the root logger and specific loggers
logging.getLogger().addFilter(NoiseFilter())
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
logging.getLogger("watchfiles.filters").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

logger = logging.getLogger("shanbot_webhook")

# Simple stub functions to avoid import issues


def verify_manychat_signature(payload: bytes, headers: dict) -> bool:
    """Verify ManyChat webhook signature."""
    manychat_signature = headers.get(
        'X-ManyChat-Signature') or headers.get('x-manychat-signature')
    if not manychat_signature:
        logger.info(
            "No X-ManyChat-Signature header found. Proceeding without signature verification.")
    return True


async def trigger_instagram_analysis_for_user() -> None:
    """Trigger Instagram analysis for active users."""
    logger.info(
        "Instagram analysis would be triggered here (currently disabled)")


def get_user_data(subscriber_id: str) -> Dict[str, Any]:
    """Get user data from database."""
    logger.info(f"Getting user data for subscriber: {subscriber_id}")
    # This is a stub - in real implementation, this would query the database
    return {"subscriber_id": subscriber_id, "status": "active"}

# Lifespan context manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup and shutdown tasks."""
    logger.info("[Startup] Shanbot Webhook starting up...")

    # Start Calendly booking check task
    logger.info("[Startup] Starting Calendly booking check task...")
    try:
        # Create a proper async task for the booking check
        async def run_calendly_check():
            while True:
                try:
                    # Run the booking check (this is a sync function)
                    count = run_booking_check()
                    if count > 0:
                        logger.info(
                            f"✅ Found and processed {count} new booking(s)")
                    else:
                        logger.info("✅ No new bookings found")
                except Exception as e:
                    logger.error(f"❌ Error in Calendly booking check: {e}")

                # Wait 30 minutes before next check
                await asyncio.sleep(1800)  # 30 minutes

        # Start the background task
        asyncio.create_task(run_calendly_check())
        logger.info("[Startup] ✓ Calendly booking check task started")
    except Exception as e:
        logger.error(f"[Startup] Failed to start Calendly booking check: {e}")

    yield

    logger.info("[Shutdown] Shanbot Webhook shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Shanbot Webhook",
    description="Instagram automation webhook for fitness coaching",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create action router
action_router = ActionRouter()

# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================


@app.post("/webhook/manychat")
async def manychat_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle ManyChat webhooks."""
    try:
        # Get raw payload
        payload = await request.body()
        headers = dict(request.headers)

        # Verify signature (stub function)
        if not verify_manychat_signature(payload, headers):
            logger.warning("ManyChat signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse JSON payload
        data = await request.json()
        logger.info(f"Received ManyChat webhook: {json.dumps(data, indent=2)}")

        # Extract key fields
        subscriber_id = data.get("id")
        ig_username = data.get("ig_username")
        message_text = data.get("last_input_text", "")

        if not subscriber_id:
            logger.error("Missing subscriber ID in webhook payload")
            raise HTTPException(
                status_code=400, detail="Missing subscriber ID")

        # Handle Facebook leads with null ig_username
        if ig_username is None or ig_username == "null":
            # Create consistent identifier for Facebook leads
            first_name = data.get("first_name", "")
            last_name = data.get("last_name", "")
            if first_name and last_name:
                ig_username = f"fb_{first_name.lower()}_{last_name.lower()}_{subscriber_id[-4:]}"
            else:
                ig_username = f"fb_user_{subscriber_id}"
            logger.info(
                f"Facebook lead detected - using consistent ig_username: {ig_username}")

        # Process the message
        result = await ActionRouter.route_webhook_message(
            ig_username=ig_username,
            message_text=message_text,
            subscriber_id=subscriber_id,
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            user_message_timestamp_iso=data.get(
                "ig_last_interaction", datetime.now().isoformat()),
            fb_ad=data.get("custom_fields", {}).get("fb ad", False)
        )

        return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"Error processing ManyChat webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "service": "shanbot-webhook"
    }


@app.get("/debug")
async def debug_info():
    """Debug information endpoint."""
    try:
        return {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "current_directory": os.getcwd(),
            "environment_variables": {
                "MANYCHAT_API_KEY": bool(os.getenv("MANYCHAT_API_KEY")),
                "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
                "INSTAGRAM_GRAPH_API_TOKEN": bool(os.getenv("INSTAGRAM_GRAPH_API_TOKEN")),
            }
        }
    except Exception as e:
        logger.error(f"[Debug] Error generating debug info: {e}")
        return {"error": str(e)}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Shanbot Webhook Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001,
                        help="Port to bind to")
    parser.add_argument("--reload", action="store_true",
                        help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")

    args = parser.parse_args()

    logger.info(f"[Main] Starting Shanbot Webhook on {args.host}:{args.port}")

    # Suppress noisy uvicorn logs
    import logging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.filters").setLevel(logging.WARNING)

    uvicorn.run(
        "webhook_main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["."] if args.reload else None,
        log_level=args.log_level,
        access_log=False,  # Hide access logs to reduce noise
        log_config=None  # Use our custom logging config
    )
