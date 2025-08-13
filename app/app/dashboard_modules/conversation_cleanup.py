#!/usr/bin/env python3
"""
Conversation Cleanup Utility
Fixes timestamp alignment issues and removes duplicate messages from conversation history.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re

logger = logging.getLogger(__name__)


def fix_conversation_timestamps(ig_username: str, dry_run: bool = True) -> Dict[str, any]:
    """
    Fix timestamp alignment issues for a specific user's conversation.

    Args:
        ig_username: Instagram username to fix
        dry_run: If True, only analyze issues without making changes

    Returns:
        Dictionary with analysis results and changes made
    """
    results = {
        'ig_username': ig_username,
        'issues_found': [],
        'changes_made': [],
        'total_messages': 0,
        'duplicates_found': 0,
        'timestamp_collisions': 0,
        'manychat_contamination': 0
    }

    try:
        # Connect to database
        conn = sqlite3.connect("../analytics_data_good.sqlite")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all messages for this user
        cursor.execute("""
            SELECT * FROM messages 
            WHERE ig_username = ? 
            ORDER BY timestamp ASC
        """, (ig_username,))

        messages = cursor.fetchall()
        results['total_messages'] = len(messages)

        if not messages:
            results['issues_found'].append("No messages found for this user")
            return results

        # Analyze issues
        previous_msg = None
        duplicates_to_remove = []
        timestamp_fixes = []

        for i, msg in enumerate(messages):
            msg_dict = dict(msg)

            # Check for ManyChat contamination
            if '{{cuf_' in msg_dict['text'] or 'Shannon:' in msg_dict['text']:
                results['manychat_contamination'] += 1
                results['issues_found'].append(
                    f"Message {i+1} contains ManyChat variables or conversation chain")

            # Check for duplicate content
            if previous_msg:
                # Check if current message is a duplicate
                if (msg_dict['text'].strip() == previous_msg['text'].strip() and
                        msg_dict['type'] == previous_msg['type']):
                    results['duplicates_found'] += 1
                    duplicates_to_remove.append(msg_dict['id'])
                    results['issues_found'].append(
                        f"Duplicate message found: ID {msg_dict['id']}")

                # Check for timestamp collisions (same timestamp or within 1 second)
                try:
                    current_time = datetime.fromisoformat(
                        msg_dict['timestamp'].split('+')[0])
                    prev_time = datetime.fromisoformat(
                        previous_msg['timestamp'].split('+')[0])

                    time_diff = abs((current_time - prev_time).total_seconds())

                    if time_diff < 2:  # Less than 2 seconds apart
                        results['timestamp_collisions'] += 1

                        # Calculate proper spacing for AI responses
                        if msg_dict['type'] == 'ai' and previous_msg['type'] == 'user':
                            # AI should respond 30-90 seconds after user
                            proper_timestamp = prev_time + \
                                timedelta(seconds=45)
                            timestamp_fixes.append({
                                'message_id': msg_dict['id'],
                                'old_timestamp': msg_dict['timestamp'],
                                'new_timestamp': proper_timestamp.isoformat(),
                                'reason': 'AI response too close to user message'
                            })
                            results['issues_found'].append(
                                f"Timestamp collision: Message {msg_dict['id']} only {time_diff}s after previous")

                except (ValueError, KeyError) as e:
                    results['issues_found'].append(
                        f"Invalid timestamp format: {e}")

            previous_msg = msg_dict

        # Apply fixes if not dry run
        if not dry_run:
            # Remove duplicates
            for msg_id in duplicates_to_remove:
                cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                results['changes_made'].append(
                    f"Removed duplicate message ID {msg_id}")

            # Fix timestamps
            for fix in timestamp_fixes:
                cursor.execute("""
                    UPDATE messages 
                    SET timestamp = ? 
                    WHERE id = ?
                """, (fix['new_timestamp'], fix['message_id']))
                results['changes_made'].append(
                    f"Fixed timestamp for message ID {fix['message_id']}")

            conn.commit()

        conn.close()

    except Exception as e:
        logger.error(f"Error fixing conversation for {ig_username}: {e}")
        results['issues_found'].append(f"Error during processing: {e}")

    return results


def clean_manychat_messages(ig_username: str, dry_run: bool = True) -> List[str]:
    """
    Clean up ManyChat contaminated messages by extracting just the user's actual message.

    Args:
        ig_username: Instagram username to clean
        dry_run: If True, only show what would be cleaned

    Returns:
        List of changes made or would be made
    """
    changes = []

    try:
        conn = sqlite3.connect("app/analytics_data_good.sqlite")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find messages with ManyChat contamination
        cursor.execute("""
            SELECT * FROM messages 
            WHERE ig_username = ? AND (text LIKE '%{{cuf_%' OR text LIKE '%Shannon:%')
            ORDER BY timestamp ASC
        """, (ig_username,))

        contaminated_messages = cursor.fetchall()

        for msg in contaminated_messages:
            original_text = msg['text']

            # Extract the actual user message (usually at the end after last "Lead :")
            cleaned_text = extract_user_message_from_manychat(original_text)

            if cleaned_text != original_text:
                changes.append(
                    f"Message ID {msg['id']}: '{original_text[:50]}...' → '{cleaned_text[:50]}...'")

                if not dry_run:
                    cursor.execute("""
                        UPDATE messages 
                        SET text = ? 
                        WHERE id = ?
                    """, (cleaned_text, msg['id']))

        if not dry_run and changes:
            conn.commit()

        conn.close()

    except Exception as e:
        logger.error(
            f"Error cleaning ManyChat messages for {ig_username}: {e}")
        changes.append(f"Error: {e}")

    return changes


def extract_user_message_from_manychat(contaminated_text: str) -> str:
    """
    Extract the actual user message from ManyChat conversation chain.

    Args:
        contaminated_text: The full ManyChat conversation chain

    Returns:
        Cleaned user message text
    """
    # Pattern: Look for "Lead :" followed by the actual message
    # This is usually at the end of the chain
    lead_pattern = r'Lead\s*:\s*([^+]+?)(?:\s*\+\s*Shannon:|$)'

    # Find all "Lead :" messages
    lead_matches = re.findall(lead_pattern, contaminated_text)

    if lead_matches:
        # Return the last (most recent) user message
        return lead_matches[-1].strip()

    # Fallback: If no "Lead :" pattern, try to extract from beginning
    # Sometimes the user message is at the start before the first Shannon response
    first_shannon = contaminated_text.find('Shannon:')
    if first_shannon > 0:
        potential_user_msg = contaminated_text[:first_shannon].strip()
        # Reasonable message length
        if potential_user_msg and len(potential_user_msg) < 500:
            return potential_user_msg

    # If all else fails, return the original (better to have something than nothing)
    return contaminated_text


def analyze_all_conversations() -> Dict[str, any]:
    """
    Analyze all conversations for timestamp and duplicate issues.

    Returns:
        Summary of issues found across all users
    """
    summary = {
        'total_users': 0,
        'users_with_issues': 0,
        'total_duplicates': 0,
        'total_timestamp_collisions': 0,
        'total_manychat_contamination': 0,
        'user_details': {}
    }

    try:
        conn = sqlite3.connect("app/analytics_data_good.sqlite")
        cursor = conn.cursor()

        # Get all unique usernames
        cursor.execute(
            "SELECT DISTINCT ig_username FROM messages WHERE ig_username IS NOT NULL")
        usernames = [row[0] for row in cursor.fetchall()]

        summary['total_users'] = len(usernames)

        for username in usernames:
            results = fix_conversation_timestamps(username, dry_run=True)

            if results['issues_found']:
                summary['users_with_issues'] += 1
                summary['user_details'][username] = results

            summary['total_duplicates'] += results['duplicates_found']
            summary['total_timestamp_collisions'] += results['timestamp_collisions']
            summary['total_manychat_contamination'] += results['manychat_contamination']

        conn.close()

    except Exception as e:
        logger.error(f"Error analyzing conversations: {e}")
        summary['error'] = str(e)

    return summary


def fix_specific_user_conversation(ig_username: str) -> Dict[str, any]:
    """
    Fix all issues for a specific user's conversation.

    Args:
        ig_username: Instagram username to fix

    Returns:
        Results of the fix operation
    """
    print(f"\n=== Fixing conversation for @{ig_username} ===")

    # First, analyze the issues
    analysis = fix_conversation_timestamps(ig_username, dry_run=True)

    print(f"Issues found:")
    for issue in analysis['issues_found']:
        print(f"  - {issue}")

    print(f"\nSummary:")
    print(f"  - Total messages: {analysis['total_messages']}")
    print(f"  - Duplicates: {analysis['duplicates_found']}")
    print(f"  - Timestamp collisions: {analysis['timestamp_collisions']}")
    print(f"  - ManyChat contamination: {analysis['manychat_contamination']}")

    if analysis['issues_found']:
        # Apply fixes
        print(f"\nApplying fixes...")

        # Fix timestamps and duplicates
        timestamp_fixes = fix_conversation_timestamps(
            ig_username, dry_run=False)

        # Clean ManyChat messages
        manychat_changes = clean_manychat_messages(ig_username, dry_run=False)

        print(f"\nChanges made:")
        for change in timestamp_fixes['changes_made']:
            print(f"  - {change}")
        for change in manychat_changes:
            print(f"  - {change}")

        return {
            'username': ig_username,
            'timestamp_fixes': timestamp_fixes,
            'manychat_changes': manychat_changes,
            'total_fixes': len(timestamp_fixes['changes_made']) + len(manychat_changes)
        }
    else:
        print("No issues found - conversation is clean!")
        return {'username': ig_username, 'total_fixes': 0}


if __name__ == "__main__":
    # Example usage
    print("Conversation Cleanup Utility")
    print("=============================")

    # For demo, let's fix a specific user from the provided conversation
    test_username = input(
        "Enter Instagram username to analyze and fix (or press Enter to skip): ").strip()

    if test_username:
        results = fix_specific_user_conversation(test_username)
        print(f"\nFixing completed for @{test_username}")
        print(f"Total fixes applied: {results['total_fixes']}")
