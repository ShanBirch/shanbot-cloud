import sqlite3
import json
from datetime import datetime


def create_user_record():
    """Create the missing user record for interstellarwitch"""
    try:
        conn = sqlite3.connect('analytics_data_good.sqlite')
        cursor = conn.cursor()

        # Basic user data we can infer from messages
        user_data = {
            'ig_username': 'interstellarwitch',
            'subscriber_id': None,  # We don't have this yet
            'metrics_json': None,
            'calorie_tracking_json': None,
            'workout_program_json': None,
            'meal_plan_json': None,
            'client_analysis_json': json.dumps({
                'vegan_since': '15 years',
                'pet_cat': 'Apollo',
                'recovery_status': 'injured from walking large dog',
                'timezone_info': '8:30pm mentioned',
                'interests': ['sex_and_the_city', 'vegan_lifestyle']
            }),
            'is_onboarding': 0,
            'is_in_checkin_flow_mon': 0,
            'is_in_checkin_flow_wed': 0,
            'client_status': 'Lead',
            'bio': '15yrs vegan, has cat named Apollo, recently injured from dog walking incident',
            'first_name': None,
            'last_name': None
        }

        # Insert the user record
        insert_query = """
        INSERT INTO users (
            ig_username, subscriber_id, metrics_json, calorie_tracking_json,
            workout_program_json, meal_plan_json, client_analysis_json,
            is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
            client_status, bio, first_name, last_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor.execute(insert_query, (
            user_data['ig_username'],
            user_data['subscriber_id'],
            user_data['metrics_json'],
            user_data['calorie_tracking_json'],
            user_data['workout_program_json'],
            user_data['meal_plan_json'],
            user_data['client_analysis_json'],
            user_data['is_onboarding'],
            user_data['is_in_checkin_flow_mon'],
            user_data['is_in_checkin_flow_wed'],
            user_data['client_status'],
            user_data['bio'],
            user_data['first_name'],
            user_data['last_name']
        ))

        conn.commit()
        print("✅ Successfully created user record for interstellarwitch")

        # Verify the record was created
        cursor.execute("SELECT * FROM users WHERE ig_username = ?",
                       ('interstellarwitch',))
        result = cursor.fetchone()
        if result:
            print(
                f"✅ User record verified: {result[0]} (status: {result[10]})")
        else:
            print("❌ Failed to verify user record creation")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error creating user record: {e}")
        return False


def trigger_instagram_analysis():
    """Trigger Instagram analysis for interstellarwitch"""
    try:
        import subprocess
        import tempfile
        import os

        print("🔄 Triggering Instagram analysis for interstellarwitch...")

        # Create temporary file with username
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write('interstellarwitch')
            temp_file_path = temp_file.name

        # Path to analyzer script
        analyzer_script_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\anaylize_followers.py"

        if not os.path.exists(analyzer_script_path):
            print(f"❌ Analyzer script not found at {analyzer_script_path}")
            return False

        # Run the analyzer
        cmd = [
            "python", analyzer_script_path,
            "--followers-list", temp_file_path,
            "--force"
        ]

        print(f"🎯 Running: {' '.join(cmd)}")

        # Run in background
        process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(analyzer_script_path),
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                subprocess, 'CREATE_NEW_CONSOLE') else 0
        )

        print("✅ Instagram analysis started in new window")

        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass

        return True

    except Exception as e:
        print(f"❌ Error triggering Instagram analysis: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Fixing interstellarwitch user record...")

    # Step 1: Create the user record
    if create_user_record():
        print("\n🔄 User record created successfully, now triggering Instagram analysis...")

        # Step 2: Trigger Instagram analysis
        if trigger_instagram_analysis():
            print("\n✅ All done! interstellarwitch should now appear in your dashboard.")
            print(
                "📊 The Instagram analysis will populate her full bio data in the background.")
        else:
            print(
                "\n⚠️ User record created but Instagram analysis failed. You can trigger it manually.")
    else:
        print("\n❌ Failed to create user record. Please check the error above.")
