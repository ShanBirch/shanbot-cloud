# Monkey patch for analytics integration
import sys
import importlib
from fastapi import FastAPI

# Import the analytics module
try:
    from analytics_integration import analytics, router as analytics_router
    print("Analytics module imported successfully")
except ImportError:
    print("Warning: analytics_integration module not found")
    analytics = None
    analytics_router = None

# Patch FastAPI to automatically include the analytics router
original_init = FastAPI.__init__

def patched_init(self, *args, **kwargs):
    # Call the original init
    original_init(self, *args, **kwargs)
    
    # Add our router if available
    if analytics_router:
        try:
            self.include_router(analytics_router)
            print("Analytics router added to FastAPI app")
        except Exception as e:
            print(f"Error adding analytics router: {e}")

# Apply the patch
FastAPI.__init__ = patched_init

# Also patch the manychat_webhook_fullprompt module if it's imported
if "manychat_webhook_fullprompt" in sys.modules:
    print("Patching existing manychat_webhook_fullprompt module")
    module = sys.modules["manychat_webhook_fullprompt"]
    if hasattr(module, "app") and isinstance(module.app, FastAPI):
        if analytics_router:
            try:
                module.app.include_router(analytics_router)
                print("Added analytics router to existing app")
            except Exception as e:
                print(f"Error adding router to existing app: {e}")
        
        # Add analytics attributes to the module
        if analytics and not hasattr(module, "analytics"):
            module.analytics = analytics
            print("Added analytics to module")
        
        if not hasattr(module, "track_conversation_analytics"):
            from analytics_integration import track_conversation_analytics
            module.track_conversation_analytics = track_conversation_analytics
            print("Added track_conversation_analytics to module")
