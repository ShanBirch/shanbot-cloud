#!/usr/bin/env python3
"""
Send a test webhook to your Render service to verify it's receiving and storing messages.

Usage:
    python scripts/send_test_webhook.py
"""

import requests
import json
from datetime import datetime, timezone

# Test payload mimicking ManyChat
test_payload = {
    "id": "test_subscriber_123",
    "ig_username": "test_user",
    "name": "Test User",
    "last_input_text": "This is a test message from Cursor!",
    "ig_last_interaction": datetime.now(timezone.utc).isoformat(),
    "custom_fields": {
        "o1 input": "This is a test message from Cursor!"
    }
}

webhook_url = "https://shanbot-webhook.onrender.com/webhook/manychat"

print("📤 Sending test webhook to Render...")
print(f"URL: {webhook_url}")
print(f"Payload: {json.dumps(test_payload, indent=2)}\n")

try:
    response = requests.post(webhook_url, json=test_payload, timeout=30)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}\n")
    
    if response.status_code == 200:
        print("✅ Test webhook sent successfully!")
        print("\n💡 Now check Render logs to see if it was received:")
        print("   https://dashboard.render.com → shanbot-webhook → Logs")
        print("\n   Look for: 'Stored inbound message' or similar")
    else:
        print(f"⚠️  Unexpected status code: {response.status_code}")
        
except Exception as e:
    print(f"❌ Failed to send webhook: {e}")

