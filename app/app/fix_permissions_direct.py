import os

# Path to the file
file_path = os.path.join(os.path.dirname(
    __file__), 'manychat_webhook_fixed.py')
print(f"Attempting to modify file at: {file_path}")

try:
    # Read the file line by line
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the variable initialization section
    for i, line in enumerate(lines):
        if "# --- Check for \"general chat\" permission field ---" in line:
            print(f"Found permissions check at line {i+1}")
            # Replace the line
            lines[i] = "    # --- Check for \"general chat\" and \"initial whats app check ins\" permission fields ---\n"
            # Add the new variable after general_chat_allowed
            if "general_chat_allowed = False" in lines[i+1]:
                lines.insert(
                    i+2, "    initial_whatsapp_checkins_allowed = False\n")
                print("Added initial_whatsapp_checkins_allowed variable")
                break

    # Find the first check (top-level fields)
    for i, line in enumerate(lines):
        if "if field_name.lower().strip() == \"general chat\":" in line and i > 330 and i < 350:
            print(f"Found first permission check at line {i+1}")
            # Find the end of this check block
            end_index = i + 3  # Assuming 3 lines for the if block
            # Add the elif check
            new_lines = [
                "            elif field_name.lower().strip() == \"initial whats app check ins\":\n",
                "                initial_whatsapp_checkins_allowed = (field_value.lower() == \"yes\" or field_value.lower() == \"true\")\n",
                "                logger.info(\"Found 'initial whats app check ins' permission set to YES/TRUE at top level.\")\n"
            ]
            for j, new_line in enumerate(new_lines):
                lines.insert(end_index + j, new_line)
            print("Added first check for initial whats app check ins")
            break

    # Find the second check (subscriber fields)
    for i, line in enumerate(lines):
        if "if field_name.lower().strip() == \"general chat\":" in line and i > 350:
            print(f"Found second permission check at line {i+1}")
            # Find the end of this check block
            end_index = i + 3  # Assuming 3 lines for the if block
            # Add the elif check
            new_lines = [
                "            elif field_name.lower().strip() == \"initial whats app check ins\":\n",
                "                initial_whatsapp_checkins_allowed = (field_value.lower() == \"yes\" or field_value.lower() == \"true\")\n",
                "                logger.info(\"Found 'initial whats app check ins' permission set to YES/TRUE under subscriber.\")\n"
            ]
            for j, new_line in enumerate(new_lines):
                lines.insert(end_index + j, new_line)
            print("Added second check for initial whats app check ins")
            break

    # Find the final permission check
    for i, line in enumerate(lines):
        if "# If general chat is not allowed, return early" in line:
            print(f"Found final permission check at line {i+1}")
            lines[i] = "    # Check if either general chat or initial whats app check ins is allowed\n"
            # Update the if condition
            if "if not general_chat_allowed:" in lines[i+1]:
                lines[i+1] = "    if not general_chat_allowed and not initial_whatsapp_checkins_allowed:\n"
                # Update the warning message
                warning_line = i+2
                if "logger.warning" in lines[warning_line]:
                    lines[warning_line] = "        logger.warning(\"Webhook request denied: Neither 'general chat' nor 'initial whats app check ins' permissions are set to YES/TRUE.\")\n"
                # Update the error message
                error_line = i+4
                if "content={\"success\": False, \"error\":" in lines[error_line]:
                    lines[error_line] = "            content={\"success\": False, \"error\": \"Permission denied: Neither 'general chat' nor 'initial whats app check ins' permissions are set to YES/TRUE.\"}\n"
                print("Updated permission check logic")
                break

    # Write the modified file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("Successfully updated the webhook permissions!")

except Exception as e:
    print(f"Error: {e}")
