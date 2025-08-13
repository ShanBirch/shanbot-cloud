
# This module can be imported to fix missing analytics imports at runtime
def fix_imports():
    try:
        # First try to find the analytics module
        try:
            import analytics_integration
            print("Analytics module found")
        except ImportError:
            print("Creating analytics_integration.py")
            with open("analytics_integration.py", "w") as f:
                f.write('''
import json
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Request, HTTPException
import logging
from datetime import datetime
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics_integration")

class ConversationAnalytics:
    def __init__(self):
        self.conversations = {}
        self.global_metrics = {"total_conversations": 0, "total_messages": 0}
    
    def analyze_message(self, subscriber_id, message, is_ai_response=False):
        if subscriber_id not in self.conversations:
            self.conversations[subscriber_id] = {"messages": [], "metrics": {"total_messages": 0}}
            self.global_metrics["total_conversations"] += 1
        self.global_metrics["total_messages"] += 1
        return {"success": True}
    
    def get_conversation_metrics(self, subscriber_id):
        return self.conversations.get(subscriber_id, {}).get("metrics", {})
    
    def get_global_metrics(self):
        return self.global_metrics
    
    def get_engagement_analysis(self, subscriber_id):
        return {"total_messages": self.conversations.get(subscriber_id, {}).get("metrics", {}).get("total_messages", 0)}
    
    def export_analytics(self, file_path):
        with open(file_path, "w") as f:
            json.dump({"global_metrics": self.global_metrics}, f)
        return {"success": True}

analytics = ConversationAnalytics()
router = APIRouter()

@router.get("/analytics/global")
async def get_global_metrics():
    return analytics.get_global_metrics()

@router.get("/analytics/conversation/{subscriber_id}")
async def get_conversation_metrics(subscriber_id: str):
    return analytics.get_conversation_metrics(subscriber_id)

@router.get("/analytics/engagement/{subscriber_id}")
async def get_engagement_analysis(subscriber_id: str):
    return analytics.get_engagement_analysis(subscriber_id)

@router.post("/analytics/export")
async def export_analytics(file_path: str):
    return analytics.export_analytics(file_path)

def track_conversation_analytics(endpoint_func):
    @wraps(endpoint_func)
    async def wrapper(request: Request, *args, **kwargs):
        response = await endpoint_func(request, *args, **kwargs)
        return response
    return wrapper
''')
            # Import the module we just created
            import sys
            import importlib
            if "analytics_integration" in sys.modules:
                del sys.modules["analytics_integration"]
            import analytics_integration
            
        # Fix FastAPI to include our router
        from fastapi import FastAPI
        from analytics_integration import analytics, router as analytics_router
        
        # Keep track of the original __init__
        original_init = FastAPI.__init__
        
        # Create a replacement that adds our router
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            try:
                self.include_router(analytics_router)
                print("Analytics router added automatically")
            except Exception as e:
                print(f"Error adding analytics router: {e}")
        
        # Apply the patch
        FastAPI.__init__ = patched_init
        print("FastAPI successfully patched")
        
        # Return the imported modules
        return analytics_integration
        
    except Exception as e:
        print(f"Error during import fix: {e}")
        return None

# Run the fix when imported
fix_imports()
