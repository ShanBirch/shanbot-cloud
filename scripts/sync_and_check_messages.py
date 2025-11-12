#!/usr/bin/env python3
"""
Simplified script to sync messages from Render and display them.

This script:
1. Fetches messages from your Render webhook
2. Saves them locally to conversation_logs/
3. Displays the most recent inbound messages

Usage:
    python scripts/sync_and_check_messages.py
    python scripts/sync_and_check_messages.py -n 100  # show 100 messages
"""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import check_messages
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from webhook_config.env if it exists
config_file = Path(__file__).parent.parent / "webhook_config.env"
if config_file.exists():
    print(f"Loading config from {config_file}")
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Check if REMOTE_WEBHOOK_BASE_URL is set
if not os.getenv('REMOTE_WEBHOOK_BASE_URL'):
    print("❌ ERROR: REMOTE_WEBHOOK_BASE_URL not set!")
    print("\nPlease edit webhook_config.env and set your Render URL:")
    print("  REMOTE_WEBHOOK_BASE_URL=https://your-app-name.onrender.com")
    sys.exit(1)

# Import and run the check_messages script with --sync-remote flag
from scripts.check_messages import main, build_parser

# Modify sys.argv to add --sync-remote flag
if '--sync-remote' not in sys.argv:
    sys.argv.append('--sync-remote')

print(f"🔄 Syncing messages from {os.getenv('REMOTE_WEBHOOK_BASE_URL')}...\n")
main()

