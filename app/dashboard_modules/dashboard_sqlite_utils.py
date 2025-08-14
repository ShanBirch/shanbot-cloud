import logging
logger = logging.getLogger("dashboard_sqlite_utils_stub")

def add_response_to_review_queue(**kwargs):
    logger.info("[stub] add_response_to_review_queue called with keys: %s", list(kwargs.keys()))
    # Return a fake review_id so upstream logic can proceed
    return 1

def add_message_to_history(**kwargs):
    logger.info("[stub] add_message_to_history called")
    return None
