from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
from enum import Enum


class EventType(str, Enum):
    """Types of events that can be received from ManyChat"""
    INSTAGRAM_DM = "instagram_dm"
    FIELD = "field"
    TAG_APPLIED = "tag_applied"
    TAG_REMOVED = "tag_removed"
    SUBSCRIBER_UPDATED = "subscriber_updated"
    NEW_SUBSCRIBER = "new_subscriber"


class WebhookPayload(BaseModel):
    """Payload structure for ManyChat webhooks"""
    trigger: Optional[Dict[str, Any]] = None
    subscriber: Optional[Dict[str, Any]] = None
    conversation: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    event_type: Optional[str] = None
    tag: Optional[str] = None
    field_name: Optional[str] = None
    field_value: Optional[Any] = None

    # For test webhooks
    key: Optional[str] = None
    page_id: Optional[str] = None
    id: Optional[str] = None
    first_name: Optional[str] = None


class WebhookResponse(BaseModel):
    """Response structure for ManyChat webhooks"""
    success: bool = True
    message: str = "Webhook received successfully"
    data: Dict[str, Any] = Field(default_factory=dict)


# Simple string response for direct text output
class TextResponse(str):
    """Simple string response without JSON formatting"""
    pass


class ManyChat_Subscriber(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ManyChat_Webhook_Payload(BaseModel):
    event_name: str
    subscriber: ManyChat_Subscriber
    chat: Optional[Dict[str, Any]] = None
    flow: Optional[Dict[str, Any]] = None
    user_ref: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    status: str = "success"
    message: str = "Webhook received successfully"
    data: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "version": "v2",
                "content": {
                    "messages": [
                        {
                            "type": "text",
                            "text": "Processing your request..."
                        }
                    ],
                    "actions": [
                        {
                            "action": "set_field_value",
                            "field_id": 11944956,
                            "value": "Sample conversation value"
                        },
                        {
                            "action": "set_field_value",
                            "field_id": 11967919,
                            "value": "Sample name value"
                        }
                    ]
                }
            }
        }
