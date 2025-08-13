import json
import sqlite3
import os

# Path to your JSON file
JSON_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.json"
SQLITE_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"

# Load your JSON data
with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Remove existing SQLite file if you want a fresh migration (optional)
# if os.path.exists(SQLITE_PATH):
#     os.remove(SQLITE_PATH)

# Connect to SQLite (creates file if not exists)
conn = sqlite3.connect(SQLITE_PATH)
c = conn.cursor()

# Create Users table (ig_username as PRIMARY KEY)
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    ig_username TEXT PRIMARY KEY,
    subscriber_id TEXT,
    metrics_json TEXT,
    calorie_tracking_json TEXT,
    workout_program_json TEXT,
    meal_plan_json TEXT,
    client_analysis_json TEXT,
    is_onboarding INTEGER,
    is_in_checkin_flow_mon INTEGER,
    is_in_checkin_flow_wed INTEGER,
    client_status TEXT
    -- Add more columns as needed
)
''')

# Create Messages table (ig_username as foreign key)
c.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_username TEXT,
    timestamp TEXT,
    type TEXT,
    text TEXT,
    FOREIGN KEY(ig_username) REFERENCES users(ig_username)
)
''')

# Add new columns if they don't exist
cursor = conn.cursor()

# Function to check if column exists


def column_exists(table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(c[1] == column for c in cursor.fetchall())


new_columns = [
    ("is_in_ad_flow", "INTEGER DEFAULT 0"),
    ("ad_script_state", "TEXT"),
    ("ad_scenario", "INTEGER"),
    ("lead_source", "TEXT DEFAULT 'general'")
]

for column, col_type in new_columns:
    if not column_exists('users', column):
        cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {col_type}")
        print(f"Added column {column} to users table")
    else:
        print(f"Column {column} already exists")

conn.commit()
print("Added new columns for ad response flow if needed.")

# Insert users and messages


def safe_json(obj):
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return '{}'


for username, user_data in data.get('conversations', {}).items():
    if not isinstance(user_data, dict):
        print(f"Skipping {username}: not a dict (type={type(user_data)})")
        continue
    metrics = user_data.get('metrics', {})
    ig_username = metrics.get('ig_username', username)
    subscriber_id = metrics.get('subscriber_id', '')

    # Store complex fields as JSON strings
    metrics_json = safe_json(metrics)
    calorie_tracking_json = safe_json(metrics.get('calorie_tracking', {}))
    workout_program_json = safe_json(metrics.get('workout_program', {}))
    meal_plan_json = safe_json(metrics.get('meal_plan', {}))
    # Always fill client_analysis_json, even if empty
    client_analysis_json = safe_json(metrics.get('client_analysis', {}))

    # Extract new fields for direct columns
    is_onboarding = int(metrics.get('is_onboarding', False))
    is_in_checkin_flow_mon = int(metrics.get('is_in_checkin_flow_mon', False))
    is_in_checkin_flow_wed = int(metrics.get('is_in_checkin_flow_wed', False))
    client_status = metrics.get('client_status', 'lead')

    # Insert user with new columns
    c.execute('''
        INSERT OR IGNORE INTO users (
            ig_username, subscriber_id, metrics_json, calorie_tracking_json,
            workout_program_json, meal_plan_json, client_analysis_json,
            is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed, client_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ig_username, subscriber_id, metrics_json, calorie_tracking_json,
        workout_program_json, meal_plan_json, client_analysis_json,
        is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed, client_status
    ))
    conn.commit()

    # Insert messages (use ig_username as foreign key)
    for msg in metrics.get('conversation_history', []):
        if not msg or not isinstance(msg, dict):
            continue
        timestamp = msg.get('timestamp', '')
        msg_type = msg.get('type', '')
        text = msg.get('text', '')
        c.execute('''
            INSERT INTO messages (ig_username, timestamp, type, text)
            VALUES (?, ?, ?, ?)
        ''', (ig_username, timestamp, msg_type, text))
    conn.commit()

print("Migration complete! Database created at:", SQLITE_PATH)
conn.close()
