#!/usr/bin/env python
# Fix indentation in analytics_dashboard.py

# Open the file and read all lines
with open('analytics_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Replace line 134 (index 133) with the properly indented version
lines[133] = '                        driver = followup_manager.get_driver()\n'

# Write the fixed content back to the file
with open('analytics_dashboard.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed indentation in line 134!")
