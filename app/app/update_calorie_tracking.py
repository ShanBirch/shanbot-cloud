import json
from datetime import datetime, timezone

# Path to the analytics data file
ANALYTICS_FILE = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.json"


def add_calorie_tracking():
    try:
        # Read the existing JSON file
        with open(ANALYTICS_FILE, 'r') as f:
            data = json.load(f)

        # Loop through all users in conversations
        if 'conversations' in data:
            for user_id, user_data in data['conversations'].items():
                if isinstance(user_data, dict) and 'metrics' in user_data:
                    metrics = user_data['metrics']
                    # Use existing targets if present, otherwise defaults
                    calorie_target = 2000
                    protein_target = 180
                    carbs_target = 250
                    fats_target = 65
                    if 'calorie_tracking' in metrics:
                        ct = metrics['calorie_tracking']
                        calorie_target = ct.get('daily_target', calorie_target)
                        protein_target = ct.get('macros', {}).get(
                            'protein', {}).get('daily_target', protein_target)
                        carbs_target = ct.get('macros', {}).get(
                            'carbs', {}).get('daily_target', carbs_target)
                        fats_target = ct.get('macros', {}).get(
                            'fats', {}).get('daily_target', fats_target)
                    # Reset calorie tracking
                    metrics['calorie_tracking'] = {
                        "daily_target": calorie_target,
                        "current_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "calories_consumed": 0,
                        "remaining_calories": calorie_target,
                        "macros": {
                            "protein": {
                                "daily_target": protein_target,
                                "consumed": 0,
                                "remaining": protein_target
                            },
                            "carbs": {
                                "daily_target": carbs_target,
                                "consumed": 0,
                                "remaining": carbs_target
                            },
                            "fats": {
                                "daily_target": fats_target,
                                "consumed": 0,
                                "remaining": fats_target
                            }
                        },
                        "meals_today": []
                    }
                    print(f"Reset calorie tracking for user: {user_id}")

        # Write the updated data back to the file
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print("Successfully updated analytics_data_good.json for all users")

    except Exception as e:
        print(f"Error updating file: {str(e)}")


if __name__ == "__main__":
    add_calorie_tracking()
