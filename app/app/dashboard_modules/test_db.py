import sqlite3
from datetime import datetime

# Test database connection and scheduled responses
db_path = r'C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("🔍 Checking scheduled responses database...")

# Check scheduled responses table
cursor.execute('SELECT COUNT(*) FROM scheduled_responses')
total_count = cursor.fetchone()[0]
print(f'Total scheduled responses: {total_count}')

# Check statuses
cursor.execute(
    'SELECT status, COUNT(*) FROM scheduled_responses GROUP BY status')
status_counts = cursor.fetchall()
print('Status breakdown:')
for status, count in status_counts:
    print(f'  {status or "NULL"}: {count}')

# Check for overdue responses
current_time = datetime.now().isoformat()
cursor.execute('SELECT schedule_id, user_ig_username, scheduled_send_time, status FROM scheduled_responses WHERE status = "scheduled" AND scheduled_send_time <= ?', (current_time,))
due_responses = cursor.fetchall()
print(f'\nResponses due for sending: {len(due_responses)}')

for resp in due_responses:
    print(f'  ID {resp[0]}: @{resp[1]} at {resp[2]} (status: {resp[3]})')

# Update any NULL status to scheduled
cursor.execute(
    'UPDATE scheduled_responses SET status = "scheduled" WHERE status IS NULL')
updated = cursor.rowcount
if updated > 0:
    print(f'\n✅ Updated {updated} responses from NULL to scheduled')
    conn.commit()

conn.close()
print("\n✅ Database check complete!")
