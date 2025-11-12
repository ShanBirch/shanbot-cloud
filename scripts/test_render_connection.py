#!/usr/bin/env python3
"""
Quick test to verify your Render webhook is accessible and working.

Usage:
    python scripts/test_render_connection.py
"""

import os
import sys
from pathlib import Path
import requests

# Load environment variables from webhook_config.env
config_file = Path(__file__).parent.parent / "webhook_config.env"
if config_file.exists():
    print(f"📄 Loading config from {config_file}\n")
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

base_url = os.getenv('REMOTE_WEBHOOK_BASE_URL')
token = os.getenv('REMOTE_WEBHOOK_TOKEN')

if not base_url:
    print("❌ ERROR: REMOTE_WEBHOOK_BASE_URL not set!")
    print("\nPlease edit webhook_config.env and set your Render URL:")
    print("  REMOTE_WEBHOOK_BASE_URL=https://your-app-name.onrender.com")
    sys.exit(1)

print(f"🔗 Testing connection to: {base_url}\n")
print("=" * 60)

# Test 1: Health check
print("\n1️⃣  Testing /health endpoint...")
try:
    response = requests.get(f"{base_url}/health", timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Health check passed: {data}")
    else:
        print(f"   ❌ Health check failed: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ❌ Connection failed: {e}")
    print("\n💡 Possible issues:")
    print("   - Render URL is incorrect")
    print("   - Render service is sleeping (first request takes ~30 seconds)")
    print("   - Render service is not deployed")
    sys.exit(1)

# Test 2: Root endpoint
print("\n2️⃣  Testing / endpoint...")
try:
    response = requests.get(base_url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Root endpoint working: {data.get('message', 'OK')}")
    else:
        print(f"   ⚠️  Unexpected status: {response.status_code}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 3: Contacts endpoint (may require token)
print("\n3️⃣  Testing /webhook/manychat/contacts endpoint...")
try:
    params = {}
    if token:
        params['token'] = token
        print(f"   🔑 Using admin token: {token[:8]}...")
    
    response = requests.get(
        f"{base_url}/webhook/manychat/contacts",
        params=params,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        count = data.get('count', 0)
        print(f"   ✅ Contacts endpoint working: {count} contact(s) found")
        if count > 0:
            print(f"   📋 Contacts:")
            for contact in data.get('contacts', [])[:5]:  # Show first 5
                key = contact.get('contact_key', 'unknown')
                meta = contact.get('metadata', {})
                name = meta.get('display_name', 'N/A')
                print(f"      - {key} ({name})")
    elif response.status_code == 403:
        print(f"   ⚠️  Access denied (403)")
        print(f"   💡 You need to set REMOTE_WEBHOOK_TOKEN in webhook_config.env")
        print(f"   💡 It should match WEBHOOK_ADMIN_TOKEN on Render")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 4: Logs endpoint (may require token)
print("\n4️⃣  Testing /webhook/manychat/logs endpoint...")
try:
    params = {'limit': 5}
    if token:
        params['token'] = token
    
    response = requests.get(
        f"{base_url}/webhook/manychat/logs",
        params=params,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        contacts = data.get('contacts', [])
        total_messages = sum(len(c.get('messages', [])) for c in contacts)
        print(f"   ✅ Logs endpoint working: {len(contacts)} contact(s), {total_messages} message(s)")
        
        if total_messages > 0:
            print(f"   📨 Recent messages:")
            for contact in contacts[:3]:  # Show first 3 contacts
                key = contact.get('contact_key', 'unknown')
                messages = contact.get('messages', [])
                for msg in messages[:2]:  # Show first 2 messages per contact
                    direction = msg.get('direction', '?')
                    text = msg.get('text', '<no text>')[:50]
                    print(f"      [{direction}] {key}: {text}...")
    elif response.status_code == 403:
        print(f"   ⚠️  Access denied (403) - token required")
    else:
        print(f"   ❌ Failed: {response.status_code}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("\n✅ Connection test complete!")
print("\nNext steps:")
print("  1. If all tests passed, run: python scripts/sync_and_check_messages.py")
print("  2. Send a test message through ManyChat")
print("  3. Run sync script again to see the message")
print("\n💡 Tip: Check Render logs at https://dashboard.render.com to see webhook activity")

