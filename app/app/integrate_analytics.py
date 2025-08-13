"""
Script to integrate analytics with the manychat webhook
"""

import re
import sys
import os


def integrate_analytics(webhook_file):
    """
    Integrate analytics with the given webhook file.
    """
    print(f"Integrating analytics with {webhook_file}...")

    # Read the file content
    with open(webhook_file, 'r') as f:
        content = f.read()

    # Check if analytics is already integrated
    if "analytics_integration" in content:
        print("Analytics already integrated!")
        return

    # Add import at the top
    import_line = "from analytics_integration import analytics, router as analytics_router, track_conversation_analytics\n"
    app_line_pattern = r"(app\s*=\s*FastAPI\([^)]*\))"

    # Find the app initialization
    app_match = re.search(app_line_pattern, content)
    if not app_match:
        print("Could not find FastAPI app initialization.")
        return

    # Add import after imports
    modified_content = content

    # Find all import statements
    import_pattern = r"^(import|from)\s+.*$"
    import_matches = re.finditer(import_pattern, content, re.MULTILINE)
    last_import_pos = 0

    for match in import_matches:
        last_import_pos = match.end()

    if last_import_pos > 0:
        # Add import after the last import
        modified_content = content[:last_import_pos] + \
            "\n" + import_line + content[last_import_pos:]
    else:
        # Add import at the top
        modified_content = import_line + content

    # Add router after app initialization
    app_init_end = app_match.end()
    router_line = "\n\n# Include analytics router\napp.include_router(analytics_router)\n"

    modified_content = modified_content[:app_init_end] + \
        router_line + modified_content[app_init_end:]

    # Add decorator to webhook endpoints
    webhook_patterns = [
        r"(@app\.post\(\"/webhook/manychat\"\))\s*\n\s*(async\s+def\s+manychat_webhook)",
        r"(@app\.post\(\"/webhook/onboarding\"\))\s*\n\s*(async\s+def\s+onboarding_webhook)",
        r"(@app\.post\(\"/webhook/checkin\"\))\s*\n\s*(async\s+def\s+checkin_webhook)",
        r"(@app\.post\(\"/webhook/member_general_chat\"\))\s*\n\s*(async\s+def\s+member_general_chat_webhook)"
    ]

    # Add decorator to each endpoint
    for pattern in webhook_patterns:
        modified_content = re.sub(
            pattern,
            r"\1\n@track_conversation_analytics\n\2",
            modified_content
        )

    # Create backup
    backup_file = webhook_file + ".bak"
    with open(backup_file, 'w') as f:
        f.write(content)
    print(f"Created backup at {backup_file}")

    # Write modified content
    with open(webhook_file, 'w') as f:
        f.write(modified_content)

    print(f"Successfully integrated analytics with {webhook_file}")
    print("\nYou can now access analytics endpoints:")
    print("- /analytics/global - Overall metrics")
    print("- /analytics/conversation/{subscriber_id} - Conversation metrics")
    print("- /analytics/engagement/{subscriber_id} - Engagement analysis")
    print("- /analytics/export - Export analytics data")


if __name__ == "__main__":
    webhook_file = None

    # Check if file path is provided as argument
    if len(sys.argv) > 1:
        webhook_file = sys.argv[1]
    else:
        # Look for common webhook file names
        common_names = [
            "manychat_webhook.py",
            "manychat_webhook_fullprompt.py",
            "manychat_webhook_fixed.py"
        ]

        for name in common_names:
            if os.path.exists(name):
                webhook_file = name
                break

    if webhook_file:
        integrate_analytics(webhook_file)
    else:
        print("Please provide the webhook file path:")
        print("python integrate_analytics.py path/to/webhook_file.py")
        print("\nOr run this script in the same directory as the webhook file.")
