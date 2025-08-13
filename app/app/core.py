from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
from typing import Dict

# Initialize logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Instagram Webhook Receiver")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy"}


@app.get("/debug")
async def debug_endpoint(request: Request):
    """Debug endpoint that returns all query parameters and headers"""
    query_params = dict(request.query_params)
    headers = dict(request.headers)

    logger.info(f"DEBUG ENDPOINT ACCESSED - Query params: {query_params}")

    # Handle Facebook verification
    if "hub.mode" in query_params and "hub.verify_token" in query_params and "hub.challenge" in query_params:
        mode = query_params.get("hub.mode")
        token = query_params.get("hub.verify_token")
        challenge = query_params.get("hub.challenge")

        logger.info(
            f"DEBUG: Facebook verification detected! Mode: {mode}, Token: {token}, Challenge: {challenge}")

        verify_token = "Shanbotcyywp7nyk"
        if mode == "subscribe" and token == verify_token:
            logger.info("DEBUG: Token verification successful")
        else:
            logger.warning(
                f"DEBUG: Token verification failed. Expected: {verify_token}, Got: {token}")

        return PlainTextResponse(content=challenge)

    return {
        "status": "debug",
        "query_params": query_params,
        "headers": {k: v for k, v in headers.items()},
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint that redirects to health check"""
    logger.info("Root endpoint accessed")
    return {"status": "Shanbot API running", "message": "Use /webhook endpoints for functionality"}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app


def run_app():
    """Run the FastAPI application with uvicorn."""
    uvicorn.run(
        "app.core:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=["c:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot"],
        timeout_keep_alive=300,
        timeout_graceful_shutdown=300,
        limit_concurrency=100,
        backlog=2048
    )
