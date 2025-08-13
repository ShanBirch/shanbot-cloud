"""
Shanbot - A webhook-based chatbot with analytics dashboard
"""

import logging

# Try to import core components, but don't fail if they're missing
try:
    from .core import app, create_app, run_app
except ImportError:
    app = None
    create_app = None
    run_app = None

try:
    from .main import process_manychat_webhook
except ImportError:
    process_manychat_webhook = None
except AttributeError:
    # Handle attribute errors in module imports
    process_manychat_webhook = None

# Import modules that are known to exist and work
# Comment out problematic imports for now
try:
    from .models import (
        ExerciseDefinition,
        WorkoutDefinition,
        BuildProgramRequest,
        MacroTracking,
        MacrosData,
        MealEntry,
        CalorieTracking
    )
except ImportError:
    # Define empty classes as fallbacks
    class ExerciseDefinition:
        pass

    class WorkoutDefinition:
        pass

    class BuildProgramRequest:
        pass

    class MacroTracking:
        pass

    class MacrosData:
        pass

    class MealEntry:
        pass

    class CalorieTracking:
        pass

# Import what's available from prompts module only
try:
    from . import prompts
except ImportError:
    prompts = None

# Comment out other imports that are causing issues
# from .analytics import (
#     update_analytics_data,
#     get_user_data,
#     add_todo_item
# )
# from .nutrition_handler import (
#     update_calorie_tracking,
#     get_current_remaining_macros,
#     format_food_analysis_response
# )
# from .message_processor import (
#     add_to_message_buffer,
#     process_buffered_messages,
#     process_media_url,
#     extract_media_urls,
#     handle_form_check_request,
#     update_manychat_fields
# )
# from .ai_handler import (
#     call_gemini_with_retry,
#     get_ai_response
# )
# from .utils import (
#     get_melbourne_time_str,
#     split_response_into_messages,
#     format_conversation_history,
#     get_response_time_bucket
# )

# Set up package-level logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Version info
__version__ = "1.0.0"
__author__ = "Shannon"
__description__ = "A webhook-based chatbot with analytics dashboard"

# Expose key components
__all__ = [
    # Core components
    "app",
    "create_app",
    "run_app",
    "process_manychat_webhook",

    # Models
    "ExerciseDefinition",
    "WorkoutDefinition",
    "BuildProgramRequest",
    "MacroTracking",
    "MacrosData",
    "MealEntry",
    "CalorieTracking",

    # Analytics
    "update_analytics_data",
    "get_user_data",
    "add_todo_item",

    # Nutrition
    "update_calorie_tracking",
    "get_current_remaining_macros",
    "format_food_analysis_response",

    # Message Processing
    "add_to_message_buffer",
    "process_buffered_messages",
    "process_media_url",
    "extract_media_urls",
    "handle_form_check_request",
    "update_manychat_fields",

    # AI Handler
    "call_gemini_with_retry",
    "get_ai_response",

    # Utils
    "get_melbourne_time_str",
    "split_response_into_messages",
    "format_conversation_history",
    "get_response_time_bucket"
]

# Include prompts module in __all__
__all__.append("prompts")
