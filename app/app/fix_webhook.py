import re
import os


def fix_manychat_webhook():
    file_path = os.path.join(os.getcwd(), 'manychat_webhook_fixed.py')

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the section in update_manychat_fields where field_values are created
    function_pattern = r'def update_manychat_fields\(subscriber_id: str, field_updates: Dict\[str, Any\]\) -> bool:'
    field_values_pattern = r'field_values = \[\{'
    none_check_pattern = r'if value is not None:'

    if function_pattern in content and none_check_pattern in content:
        # Replace the None check with a check for None or empty string
        modified_content = content.replace(
            none_check_pattern,
            'if value is not None and value != "":'
        )

        # Write the modified content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        print("Successfully updated the update_manychat_fields function to filter out empty strings.")
        return True
    else:
        print("Could not find the necessary patterns in the file.")
        return False


if __name__ == "__main__":
    fix_manychat_webhook()
