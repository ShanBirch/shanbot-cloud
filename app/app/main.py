
from fastapi import FastAPI, APIRouter
import logging
from app import webhook_handlers, onboarding_handlers

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="Shanbot API",
    description="API for Shanbot, the AI-powered fitness coaching automation system.",
    version="1.0.0"
)

# Create routers for different parts of the application
main_router = APIRouter()
webhook_router = APIRouter(prefix="/webhook", tags=["Webhooks"])


@main_router.get("/", summary="Root Health Check")
async def root():
    """
    Root endpoint for basic health check.
    Confirms that the server is running.
    """
    return {"message": "Shanbot API is running."}


@main_router.get("/health", summary="Detailed Health Check")
async def health_check():
    """
    Provides a detailed health check of the application.
    """
    return {"status": "ok", "message": "Service is healthy."}

# Include routers from other handler modules
app.include_router(main_router)
app.include_router(webhook_handlers.router,
                   prefix="/webhook", tags=["Webhook Handlers"])
app.include_router(onboarding_handlers.router,
                   prefix="/onboarding", tags=["Onboarding"])


@app.on_event("startup")
async def startup_event():
    """
    Actions to perform on application startup.
    e.g., initialize database connections, load models, etc.
    """
    logging.info("Shanbot application starting up...")
    # In the future, we can add database initialization here
    # from app.utils.database_utils import initialize_schema
    # initialize_schema()
    logging.info("Shanbot application startup complete.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
