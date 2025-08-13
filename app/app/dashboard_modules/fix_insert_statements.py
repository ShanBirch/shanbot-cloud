#!/usr/bin/env python3
"""Fix INSERT statements to include status field"""


def main():
    with open('response_review.py', 'r') as f:
        content = f.read()

    # Fix the first occurrence (schedule_auto_response_without_status_change)
    old_insert1 = """INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, original_response_time,
                user_response_time, calculated_delay_minutes, scheduled_send_time, user_notes, manual_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    new_insert1 = """INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, original_response_time,
                user_response_time, calculated_delay_minutes, scheduled_send_time, user_notes, manual_context, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    # Replace both occurrences
    content = content.replace(old_insert1, new_insert1)

    # Fix the second occurrence pattern (without original_response_time)
    old_insert2 = """INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, user_response_time,
                calculated_delay_minutes, scheduled_send_time, user_notes, manual_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    new_insert2 = """INSERT INTO scheduled_responses (
                review_id, user_ig_username, user_subscriber_id, response_text,
                incoming_message_text, incoming_message_timestamp, user_response_time,
                calculated_delay_minutes, scheduled_send_time, user_notes, manual_context, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    content = content.replace(old_insert2, new_insert2)

    # Now fix the VALUES to add 'scheduled' status
    # This is trickier, but we need to add 'scheduled' before the closing parenthesis of the VALUES

    # Pattern 1: for the longer INSERT (with original_response_time)
    old_values1 = """                manual_context
            ))"""
    new_values1 = """                manual_context,
                'scheduled'
            ))"""

    content = content.replace(old_values1, new_values1)

    # Write back
    with open('response_review.py', 'w') as f:
        f.write(content)

    print("✅ Fixed INSERT statements to include status field")
    print("✅ Updated VALUES clauses to set status = 'scheduled'")


if __name__ == "__main__":
    main()
