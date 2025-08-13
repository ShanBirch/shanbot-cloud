import os
import re

# Path to the analytics_dashboard.py file
file_path = 'analytics_dashboard.py'

# Read the file
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Print current line numbers for reference
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'get_driver' in line:
        print(f"Found 'get_driver' at line {i+1}: '{line}'")
        # Also print the 3 lines before and after for context
        start = max(0, i-3)
        end = min(len(lines), i+4)
        print(f"Context (lines {start+1}-{end}):")
        for j in range(start, end):
            print(f"{j+1}: '{lines[j]}'")
        print()

# Fix all instances of the problematic line
# We'll ensure it has exactly 24 spaces of indentation
fixed_content = re.sub(
    r'^\s*driver = followup_manager\.get_driver\(\)',
    '                        driver = followup_manager.get_driver()',
    content,
    flags=re.MULTILINE
)

# Write the fixed content back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("Fixed all instances of 'driver = followup_manager.get_driver()'")
