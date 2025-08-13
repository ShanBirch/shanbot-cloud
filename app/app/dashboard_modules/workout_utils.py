import sqlite3
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any

SQLITE_PATH = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\app\\analytics_data_good.sqlite"


def get_database_connection():
    """Get connection to SQLite database"""
    return sqlite3.connect(SQLITE_PATH)


def get_current_week_workouts(username: str) -> Dict[str, Any]:
    """
    Get workout sessions for the most recent week for a given username.
    Searches by both client_name_key and ig_username to catch all cases.
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    try:
        # Get current date and calculate week range
        today = datetime.now()
        # Get Monday of current week
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)

        # Format dates
        week_start_str = week_start.strftime('%Y-%m-%d')
        week_end_str = week_end.strftime('%Y-%m-%d')

        # Query for workouts - search by both client_name_key and ig_username
        cursor.execute("""
            SELECT session_id, workout_date, workout_name, exercises_json 
            FROM client_workout_sessions 
            WHERE (client_name_key = ? OR ig_username = ?)
            AND workout_date >= ? AND workout_date <= ?
            ORDER BY workout_date DESC
        """, (username, username, week_start_str, week_end_str))

        sessions = cursor.fetchall()

        workouts = []
        improvements = []

        for session in sessions:
            session_id, workout_date, workout_name, exercises_json = session

            try:
                exercises = json.loads(
                    exercises_json) if exercises_json else []
            except json.JSONDecodeError:
                exercises = []

            workout_data = {
                'session_id': session_id,
                'date': workout_date,
                'name': workout_name,
                'exercises': []
            }

            # Process exercises
            for exercise in exercises:
                if isinstance(exercise, dict) and exercise.get('sets'):
                    exercise_data = {
                        'name': exercise.get('name', ''),
                        'sets': len(exercise.get('sets', [])),
                        'total_reps': sum(s.get('reps', 0) for s in exercise.get('sets', [])),
                        'max_weight': max((s.get('weight', 0) for s in exercise.get('sets', [])), default=0)
                    }
                    workout_data['exercises'].append(exercise_data)

            workouts.append(workout_data)

        return {
            'total_sessions': len(workouts),
            'workouts': workouts,
            'improvements': improvements,
            'week_start': week_start_str,
            'week_end': week_end_str
        }

    except Exception as e:
        print(f"Error getting current week workouts: {e}")
        return {
            'total_sessions': 0,
            'workouts': [],
            'improvements': [],
            'week_start': None,
            'week_end': None
        }
    finally:
        conn.close()


def get_recent_workouts(username: str, days: int = 14) -> List[Dict[str, Any]]:
    """
    Get workout sessions for the last N days for a given username.
    Searches by both client_name_key and ig_username.
    """
    conn = get_database_connection()
    cursor = conn.cursor()

    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Query for workouts
        cursor.execute("""
            SELECT session_id, workout_date, workout_name, exercises_json 
            FROM client_workout_sessions 
            WHERE (client_name_key = ? OR ig_username = ?)
            AND workout_date >= ? AND workout_date <= ?
            ORDER BY workout_date DESC
        """, (username, username, start_date_str, end_date_str))

        sessions = cursor.fetchall()

        workouts = []

        for session in sessions:
            session_id, workout_date, workout_name, exercises_json = session

            try:
                exercises = json.loads(
                    exercises_json) if exercises_json else []
            except json.JSONDecodeError:
                exercises = []

            workout_data = {
                'session_id': session_id,
                'date': workout_date,
                'name': workout_name,
                'exercises': []
            }

            # Process exercises
            for exercise in exercises:
                if isinstance(exercise, dict) and exercise.get('sets'):
                    exercise_data = {
                        'name': exercise.get('name', ''),
                        'sets': len(exercise.get('sets', [])),
                        'total_reps': sum(s.get('reps', 0) for s in exercise.get('sets', [])),
                        'max_weight': max((s.get('weight', 0) for s in exercise.get('sets', [])), default=0)
                    }
                    workout_data['exercises'].append(exercise_data)

            workouts.append(workout_data)

        return workouts

    except Exception as e:
        print(f"Error getting recent workouts: {e}")
        return []
    finally:
        conn.close()


def format_workout_summary_for_prompt(workouts: Dict[str, Any]) -> str:
    """Format workout data for use in prompts"""
    if workouts['total_sessions'] == 0:
        return "No recent workout sessions recorded."

    summary = f"{workouts['total_sessions']} sessions in recent week:\n"

    for workout in workouts['workouts']:
        summary += f"- {workout['date']}: {workout['name']} "
        if workout['exercises']:
            exercise_names = [ex['name']
                              for ex in workout['exercises'][:3]]  # First 3 exercises
            summary += f"({', '.join(exercise_names)})\n"
        else:
            summary += "(no exercise data)\n"

    return summary


def format_workout_summary_for_dashboard(workouts: Dict[str, Any]) -> str:
    """Format workout data for dashboard display"""
    if workouts['total_sessions'] == 0:
        return "No recent workout sessions"

    total_exercises = sum(len(w['exercises']) for w in workouts['workouts'])
    return f"{workouts['total_sessions']} sessions, {total_exercises} exercises logged"
