from typing import Dict, Any, List, Tuple, Optional
import streamlit as st
import json
import logging
import os
import datetime
import glob
import json
import sys
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import webhook_handlers
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import the SQLite save function
try:
    from dashboard_sqlite_utils import update_analytics_data
except ImportError:
    try:
        # Try from current directory
        current_dir = os.path.dirname(__file__)
        sys.path.insert(0, current_dir)
        from dashboard_sqlite_utils import update_analytics_data
    except ImportError:
        st.error("Could not import update_analytics_data function")
        update_analytics_data = None

try:
    from scheduled_followups import get_user_sheet_details as get_user
except ImportError:
    try:
        # Try from current directory
        current_dir = os.path.dirname(__file__)
        sys.path.insert(0, current_dir)
        from scheduled_followups import get_user_sheet_details as get_user
    except ImportError:
        st.warning("Could not import get_user_sheet_details function")
        get_user = None


# Directory containing the check-in review JSON files
CHECKIN_REVIEWS_DIR = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\output\checkin_reviews"


def find_latest_checkin_file(first_name: str, last_name: str, checkin_dir: str) -> Optional[str]:
    """Find the most recent check-in JSON file for a client."""
    if not first_name or not last_name or not os.path.exists(checkin_dir):
        return None

    # Construct the search pattern (case-insensitive, handles spaces/underscores)
    safe_name = f"{first_name}_{last_name}".replace(' ', '_').lower()
    pattern = os.path.join(
        checkin_dir, f"{safe_name}_*_fitness_wrapped_data.json")
    st.write(f"Searching for check-in file pattern: `{pattern}`")  # Debug

    matching_files = glob.glob(pattern)
    if not matching_files:
        # Try swapping first/last name order as a fallback
        safe_name_swapped = f"{last_name}_{first_name}".replace(
            ' ', '_').lower()
        pattern_swapped = os.path.join(
            checkin_dir, f"{safe_name_swapped}_*_fitness_wrapped_data.json")
        st.write(f"Trying swapped name pattern: `{pattern_swapped}`")  # Debug
        matching_files = glob.glob(pattern_swapped)
        if not matching_files:
            st.write(f"No files found matching pattern.")  # Debug
            return None  # No files found

    # Find the latest file based on the date in the filename (YYYY-MM-DD format)
    latest_file = None
    latest_date = None
    for f in matching_files:
        try:
            # Extract date string assuming format YYYY-MM-DD before _fitness_wrapped_data.json
            filename_base = os.path.basename(f).split(
                '_fitness_wrapped_data.json')[0]
            filename_parts = filename_base.split('_')
            # The date should be the last part of the filename before the extension part
            if len(filename_parts) > 0:
                date_str = filename_parts[-1]
                # Validate the format before parsing
                # Raises ValueError if format is wrong
                datetime.datetime.strptime(date_str, '%Y-%m-%d')
                file_date = datetime.datetime.fromisoformat(date_str).date()

                if latest_date is None or file_date > latest_date:
                    latest_date = file_date
                    latest_file = f
            else:
                st.warning(
                    f"Could not split filename to find date: {os.path.basename(f)}")
                continue

        except (ValueError, IndexError):
            # Handle files with unexpected naming conventions or invalid date format
            st.warning(
                f"Could not parse date from filename: {os.path.basename(f)}")
            continue  # Skip this file

    return latest_file


def load_json_data(file_path: str) -> Optional[Dict[str, Any]]:
    """Load data from a JSON file."""
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading JSON file {file_path}: {e}")
        return None


def get_response_category_color(num_responses: int) -> str:
    """Return color and emoji indicator based on number of responses"""
    if num_responses >= 20:
        return "🟢"  # Green circle for high responders
    elif num_responses >= 11:
        return "🟡"  # Yellow circle for medium responders
    elif num_responses >= 1:
        return "🟠"  # Orange circle for low responders
    else:
        return "🔴"  # Red circle for no response


def get_usernames(data: Dict[str, Any]) -> List[Tuple[str, str, int]]:
    """Extract unique usernames from analytics data with response categorization"""
    categorized_users = []
    if not isinstance(data, dict):
        st.error("Analytics data is not a dictionary. Cannot extract usernames.")
        return []

    # Define known top-level keys that are not individual user entries
    known_non_user_keys = ["conversations",
                           "action_items", "conversation_history"]

    # Iterate over all top-level items in the data
    for username, user_data in data.items():
        # Skip known non-user keys
        if username in known_non_user_keys:
            continue

        if not isinstance(user_data, dict):
            st.warning(
                f"Data for top-level entry '{username}' is not a dictionary (type: {type(user_data)}). Skipping this entry.")
            continue

        metrics = user_data.get('metrics', {})
        if not isinstance(metrics, dict):
            st.warning(
                f"Metrics for user '{username}' is not a dictionary (type: {type(metrics)}). Skipping this user.")
            continue

        num_responses = metrics.get('total_messages', 0)
        category_color = get_response_category_color(num_responses)
        categorized_users.append((username, category_color, num_responses))

    # If the 'conversations' key exists and contains user data, process it as well
    # This handles the case where some users might still be nested under 'conversations'
    # (like cocos_pt_studio in your example)
    nested_conversations = data.get('conversations')
    if isinstance(nested_conversations, dict):
        for username, user_data in nested_conversations.items():
            # Avoid double-counting if a username from here was already processed as a top-level key
            if username in [u[0] for u in categorized_users]:
                continue

            if not isinstance(user_data, dict):
                st.warning(
                    f"Data for nested user '{username}' under 'conversations' is not a dictionary (type: {type(user_data)}). Skipping.")
                continue
            metrics = user_data.get('metrics', {})
            if not isinstance(metrics, dict):
                st.warning(
                    f"Metrics for nested user '{username}' under 'conversations' is not a dictionary (type: {type(metrics)}). Skipping.")
                continue
            num_responses = metrics.get('total_messages', 0)
            category_color = get_response_category_color(num_responses)
            categorized_users.append((username, category_color, num_responses))

    try:
        # Sort by number of responses in descending order
        categorized_users.sort(key=lambda x: (-x[2]))
        return categorized_users
    except Exception as e:
        st.error(f"Error extracting usernames: {e}")
        return []


def get_user_topics(user_data: Dict[str, Any]) -> List[str]:
    """Get conversation topics from user's analytics data"""
    try:
        client_analysis = user_data.get(
            'metrics', {}).get('client_analysis', {})
        topics = client_analysis.get('conversation_topics', [])
        metrics = user_data.get('metrics', {})

        # Filter out empty or None topics
        filtered_topics = [
            topic for topic in topics if topic and not topic.startswith('**')]

        # Add Topic 5 if not already present
        topic_5 = "Topic 5 - Enquire about leads fitness journey - offer 1 month trial"
        if topic_5 not in filtered_topics:
            filtered_topics.append(topic_5)

        # Add appropriate trial week or paying client messages based on metrics
        current_time = datetime.datetime.now().time()
        morning_message = "Monday Morning: Goooooood Morning! Ready for the week?"
        evening_message = "Wednesday Night: Heya! Hows your week going?"

        if metrics.get('is_paying_client'):
            filtered_topics.extend([
                f"Paying Client - {morning_message}",
                f"Paying Client - {evening_message}"
            ])
        elif metrics.get('trial_week_4'):
            filtered_topics.extend([
                f"Trial Week 4 - {morning_message}",
                f"Trial Week 4 - {evening_message}"
            ])
        elif metrics.get('trial_week_3'):
            filtered_topics.extend([
                f"Trial Week 3 - {morning_message}",
                f"Trial Week 3 - {evening_message}"
            ])
        elif metrics.get('trial_week_2'):
            filtered_topics.extend([
                f"Trial Week 2 - {morning_message}",
                f"Trial Week 2 - {evening_message}"
            ])
        elif metrics.get('trial_week_1'):
            filtered_topics.extend([
                f"Trial Week 1 - {morning_message}",
                f"Trial Week 1 - {evening_message}"
            ])

        return filtered_topics
    except Exception:
        return ["Topic 5 - Enquire about leads fitness journey - offer 1 month trial"]


def display_user_profile(username: str, user_data: Dict[str, Any]):
    """Display user profile information"""
    try:
        # Handle case where user_data is None
        if user_data is None:
            st.error(f"No data available for user: {username}")
            return

        # Ensure user_data is a dictionary
        if not isinstance(user_data, dict):
            st.error(
                f"Invalid data format for user: {username} (type: {type(user_data)})")
            return

        # Get client analysis data
        metrics = user_data.get('metrics', {})
        client_analysis = metrics.get(
            'client_analysis', {}) if isinstance(metrics, dict) else {}
        journey_stage = metrics.get(
            'journey_stage', {}) if isinstance(metrics, dict) else {}

        # Get current stage from journey_stage
        current_stage = journey_stage.get('current_stage', 'Topic 1')

        # Get Instagram username from metrics
        ig_username = metrics.get('ig_username', '')

        # Get additional details from Google Sheet
        try:
            sheet_details = get_user(
                ig_username) if ig_username and get_user else {}
        except Exception as e:
            logger.warning(
                f"Could not fetch sheet details for {ig_username}: {e}")
            sheet_details = {}

        # Create tabs for different sections of the profile
        profile_tab, analysis_tab, conversation_tab, meal_plan_tab, workout_tab, checkin_tab, history_tab, onboarding_tab = st.tabs([
            "📋 Profile", "📊 Analysis", "💭 Conversation Topics", "🍽️ Meal Plan", "💪 Workout Program", "📝 Weekly Check-in", "📝 History", "📄 Onboarding Form"
        ])

        with profile_tab:
            # Display current stage prominently
            st.info(f"**Current Stage:** {current_stage}")

            # --- STAGE SWITCHING SECTION ---
            st.subheader("🔄 Manual Stage Management")

            # Determine current stage type for button styling
            is_lead = not journey_stage.get(
                'is_paying_client', False) and not journey_stage.get('trial_start_date')
            is_trial = bool(journey_stage.get('trial_start_date')
                            ) and not journey_stage.get('is_paying_client', False)
            is_paying = journey_stage.get('is_paying_client', False)

            # Stage switching buttons
            col1, col2, col3 = st.columns(3)

            with col1:
                # Lead button - show as pressed if currently lead
                is_lead = not is_trial and not is_paying
                lead_button_type = "primary" if is_lead else "secondary"
                if st.button("📋 Set as Lead", key=f"lead_{username}", type=lead_button_type):
                    if update_user_stage(ig_username, "Lead", user_data):
                        st.success(f"✅ {ig_username} set as Lead!")
                        st.info("📝 Stage switched to Topic 1, progress reset")
                        # Force a rerun to reflect changes
                        # Brief pause for the user to see the success message
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Failed to update stage")

            with col2:
                # Trial button - show as pressed if currently in trial
                trial_button_type = "primary" if is_trial else "secondary"
                if st.button("🆓 Set as 4 Week Trial", key=f"trial_{username}", type=trial_button_type):
                    if update_user_stage(ig_username, "4 Week Trial", user_data):
                        st.success(f"✅ {ig_username} set as 4 Week Trial!")
                        st.info("📅 Trial dates set, topics marked complete")
                        # Force a rerun to reflect changes
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Failed to update stage")

            with col3:
                # Paying client button - show as pressed if currently paying
                paying_button_type = "primary" if is_paying else "secondary"
                if st.button("💰 Set as Paying Client", key=f"paying_{username}", type=paying_button_type):
                    if update_user_stage(ig_username, "Paying Client", user_data):
                        st.success(f"✅ {ig_username} set as Paying Client!")
                        st.info("💳 Paying status activated, all topics complete")
                        # Force a rerun to reflect changes
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Failed to update stage")

            # Show current status indicators
            status_col1, status_col2, status_col3 = st.columns(3)
            with status_col1:
                if is_lead:
                    st.success("✅ Current: Lead")
                else:
                    st.info("○ Lead")
            with status_col2:
                if is_trial:
                    st.success("✅ Current: Trial")
                else:
                    st.info("○ Trial")
            with status_col3:
                if is_paying:
                    st.success("✅ Current: Paying")
                else:
                    st.info("○ Paying")

            st.divider()
            # --- END STAGE SWITCHING SECTION ---

            # --- CHECK-IN MANAGEMENT SECTION ---
            st.subheader("📞 Manual Check-in Triggers")
            st.caption(
                "Trigger Monday morning or Wednesday night check-ins for trial and paying clients")

            # Get current check-in status
            metrics = user_data.get('metrics', {})
            is_mon_checkin = metrics.get('is_in_checkin_flow_mon', False)
            is_wed_checkin = metrics.get('is_in_checkin_flow_wed', False)

            # Only show check-in buttons for trial or paying clients
            if is_trial or is_paying:
                checkin_col1, checkin_col2 = st.columns(2)

                with checkin_col1:
                    # Monday check-in button
                    mon_button_type = "primary" if is_mon_checkin else "secondary"
                    if st.button("🌅 Trigger Monday Check-in", key=f"mon_checkin_{username}", type=mon_button_type):
                        if trigger_check_in(ig_username, "monday", user_data, is_mon_checkin, is_wed_checkin):
                            st.success(
                                f"✅ Monday check-in toggled for {ig_username}!")
                            st.info(
                                "💬 Next message from client will use Monday check-in prompt")
                            st.rerun()
                        else:
                            st.error("❌ Failed to toggle Monday check-in")

                with checkin_col2:
                    # Wednesday check-in button
                    wed_button_type = "primary" if is_wed_checkin else "secondary"
                    if st.button("🌙 Trigger Wednesday Check-in", key=f"wed_checkin_{username}", type=wed_button_type):
                        if trigger_check_in(ig_username, "wednesday", user_data, is_mon_checkin, is_wed_checkin):
                            st.success(
                                f"✅ Wednesday check-in toggled for {ig_username}!")
                            st.info(
                                "💬 Next message from client will use Wednesday check-in prompt")
                            st.rerun()
                        else:
                            st.error("❌ Failed to toggle Wednesday check-in")

                # Show current check-in status
                status_checkin_col1, status_checkin_col2 = st.columns(2)
                with status_checkin_col1:
                    if is_mon_checkin:
                        st.success("✅ Monday Check-in Active")
                    else:
                        st.info("○ Monday Check-in Inactive")
                with status_checkin_col2:
                    if is_wed_checkin:
                        st.success("✅ Wednesday Check-in Active")
                    else:
                        st.info("○ Wednesday Check-in Inactive")
            else:
                st.info(
                    "📝 Check-in triggers are only available for trial and paying clients")

            st.divider()
            # --- END CHECK-IN MANAGEMENT SECTION ---

            # Display trial information if applicable
            if journey_stage.get('trial_start_date'):
                trial_start = datetime.datetime.fromisoformat(
                    journey_stage['trial_start_date'])
                trial_end = datetime.datetime.fromisoformat(
                    journey_stage['trial_end_date'])
                st.success(
                    f"**Trial Period:** {trial_start.strftime('%Y-%m-%d')} to {trial_end.strftime('%Y-%m-%d')}")

            # Create three columns for profile information
            col1, col2, col3 = st.columns(3)

            with col1:
                st.subheader("📱 Contact Info")
                if sheet_details.get('first_name') or sheet_details.get('last_name'):
                    full_name = f"{sheet_details.get('first_name', '')} {sheet_details.get('last_name', '')}".strip(
                    )
                    st.write(f"**Name:** {full_name}")
                if sheet_details.get('email'):
                    st.write(f"**Email:** {sheet_details.get('email')}")
                if sheet_details.get('phone'):
                    st.write(f"**Phone:** {sheet_details.get('phone')}")
                if ig_username:
                    st.write(f"**Instagram:** {ig_username}")

            with col2:
                st.subheader("💪 Physical Info")
                if sheet_details.get('sex'):
                    st.write(f"**Sex:** {sheet_details.get('sex')}")
                if sheet_details.get('dob'):
                    st.write(f"**DOB:** {sheet_details.get('dob')}")
                if sheet_details.get('weight'):
                    st.write(f"**Weight:** {sheet_details.get('weight')}")
                if sheet_details.get('height'):
                    st.write(f"**Height:** {sheet_details.get('height')}")

            with col3:
                st.subheader("🎯 Training Info")
                if sheet_details.get('gym_access'):
                    st.write(
                        f"**Gym Access:** {sheet_details.get('gym_access')}")
                if sheet_details.get('training_frequency'):
                    st.write(
                        f"**Training Frequency:** {sheet_details.get('training_frequency')}")
                if sheet_details.get('daily_calories'):
                    st.write(
                        f"**Daily Calories:** {sheet_details.get('daily_calories')}")
                if sheet_details.get('macro_split'):
                    st.write(
                        f"**Macro Split:** {sheet_details.get('macro_split')}")

                # Add weekly workout summary
                try:
                    from workout_utils import get_current_week_workouts, format_workout_summary_for_dashboard
                    weekly_workouts = get_current_week_workouts(username)
                    if weekly_workouts['total_sessions'] > 0:
                        workout_summary = format_workout_summary_for_dashboard(
                            weekly_workouts)
                        st.write("**Recent Week's Workouts:**")
                        st.info(workout_summary)
                    else:
                        st.write(
                            "**Recent Week's Workouts:** No sessions logged")
                except Exception as e:
                    st.write("**Recent Week's Workouts:** Data unavailable")

            # Create expandable sections for detailed information
            with st.expander("🎯 Goals and Requirements"):
                if sheet_details.get('fitness_goals'):
                    st.write("**Long Term Fitness Goals:**")
                    st.info(sheet_details.get('fitness_goals'))
                if sheet_details.get('specific_goal'):
                    st.write("**Specific Goal:**")
                    st.info(sheet_details.get('specific_goal'))
                if sheet_details.get('dietary_requirements'):
                    st.write("**Dietary Requirements:**")
                    st.info(sheet_details.get('dietary_requirements'))
                if sheet_details.get('excluded_foods'):
                    st.write("**Excluded Foods:**")
                    st.info(sheet_details.get('excluded_foods'))

            with st.expander("💪 Exercise Preferences"):
                if sheet_details.get('preferred_exercises'):
                    st.write("**Preferred Exercises:**")
                    st.info(sheet_details.get('preferred_exercises'))
                if sheet_details.get('excluded_exercises'):
                    st.write("**Exercises to Avoid:**")
                    st.info(sheet_details.get('excluded_exercises'))

            # Display Instagram-derived profile bio if available
            if client_analysis and 'profile_bio' in client_analysis:
                with st.expander("📸 Instagram Profile Analysis"):
                    bio = client_analysis['profile_bio']
                    if 'INTERESTS' in bio and bio['INTERESTS']:
                        st.write("**🎯 Key Interests:**")
                        for interest in bio['INTERESTS']:
                            st.write(f"- {interest}")
                    if 'PERSONALITY TRAITS' in bio and bio['PERSONALITY TRAITS']:
                        st.write("**👤 Personality Traits:**")
                        for trait in bio['PERSONALITY TRAITS']:
                            st.write(f"- {trait}")
                    if 'LIFESTYLE' in bio and bio['LIFESTYLE']:
                        st.write("**🌟 Lifestyle:**")
                        st.info(bio['LIFESTYLE'])

        with analysis_tab:
            st.subheader("📸 Instagram Analysis")
            insta_col1, insta_col2 = st.columns(2)

            with insta_col1:
                if 'posts_analyzed' in client_analysis:
                    st.metric("Posts Analyzed", client_analysis.get(
                        'posts_analyzed', 0))
                if 'interests' in client_analysis:
                    st.write("**Detected Interests:**")
                    interests = [i for i in client_analysis.get('interests', [])
                                 if i and not i.startswith('**')]
                    for interest in interests:
                        st.write(f"- {interest}")

            with insta_col2:
                if 'recent_activities' in client_analysis:
                    st.write("**Recent Activities:**")
                    activities = [a for a in client_analysis.get('recent_activities', [])
                                  if a and not a.startswith('**')]
                    for activity in activities:
                        st.write(f"- {activity}")

        with conversation_tab:
            st.subheader("🗣️ Conversation Topics")

            # Display current stage prominently at the top
            st.info(f"**Current Stage:** {current_stage}")

            # Get personalized topics from client analysis
            client_topics = client_analysis.get('conversation_topics', [])
            topic_progress = journey_stage.get('topic_progress', {})

            # Initial Topics (1-4) - Always show all topics
            st.subheader("Initial Engagement Topics")
            for i, topic in enumerate(client_topics[:4], 1):
                if current_stage == f"Topic {i}":
                    st.success(f"**Current Topic {i}:** {topic}")
                elif topic_progress.get(f'topic{i}_completed', False):
                    st.info(f"**✓ Topic {i} (Completed):** {topic}")
                else:
                    st.info(f"**Topic {i}:** {topic}")

            # Trial Offer (Topic 5) - Always show
            st.subheader("Trial Offer Stage")
            if current_stage == "Topic 5":
                st.success(
                    "**Current Stage - Topic 5:** Enquire about leads fitness journey - offer 1 month trial")
            elif topic_progress.get('trial_offer_made'):
                st.info("**✓ Topic 5 (Completed):** Trial offer made")
            else:
                st.info(
                    "**Topic 5:** Enquire about leads fitness journey - offer 1 month trial")

            # Trial Weeks - Always show all weeks
            st.subheader("Trial Period Topics")
            trial_weeks = {
                "Trial Week 1": [
                    "Monday Morning: Goooooood Morning! Ready for the week?",
                    "Wednesday Night: Heya! Hows your week going?"
                ],
                "Trial Week 2": [
                    "Monday Morning: Goooooood Morning! Ready for the week?",
                    "Wednesday Night: Heya! Hows your week going?"
                ],
                "Trial Week 3": [
                    "Monday Morning: Goooooood Morning! Ready for the week?",
                    "Wednesday Night: Heya! Hows your week going?"
                ],
                "Trial Week 4": [
                    "Monday Morning: Goooooood Morning! Ready for the week?",
                    "Wednesday Night: Heya! Hows your week going?"
                ]
            }

            for week, messages in trial_weeks.items():
                if week == current_stage:
                    st.success(f"**Current Stage - {week}:**")
                    for msg in messages:
                        st.success(f"- {msg}")
                else:
                    st.info(f"**{week}:**")
                    for msg in messages:
                        st.info(f"- {msg}")

            # Paying Client - Always show
            st.subheader("Paying Client Topics")
            paying_client_messages = [
                "Monday Morning: Goooooood Morning! Ready for the week?",
                "Wednesday Night: Heya! Hows your week going?"
            ]

            if current_stage == "Paying Client":
                st.success("**Current Stage - Paying Client:**")
                for msg in paying_client_messages:
                    st.success(f"- {msg}")
            else:
                st.info("**Paying Client Stage:**")
                for msg in paying_client_messages:
                    st.info(f"- {msg}")

        with meal_plan_tab:
            st.subheader("🍽️ Meal Plan")

            metrics = user_data.get("metrics", {})
            meal_plan_data = metrics.get("meal_plan")

            if meal_plan_data:
                try:
                    import os
                    import re

                    # Handle both dict and plain-text storage formats
                    if isinstance(meal_plan_data, dict):
                        meal_plan_text = meal_plan_data.get(
                            "meal_plan_text", "")
                        pdf_path = meal_plan_data.get("meal_plan_pdf_path")
                    else:
                        meal_plan_text = str(meal_plan_data)
                        pdf_path = None

                    # Optional PDF download button if we saved a file path
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as pdf_file:
                            st.download_button(
                                label="⬇️ Download Meal Plan PDF",
                                data=pdf_file.read(),
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                                key=f"download_{username}_meal_plan_pdf"
                            )

                    if meal_plan_text:
                        # Split by day headers for nicer navigation
                        day_sections = re.split(
                            r"(?=DAY \d+ MEAL PLAN)", meal_plan_text)
                        for section in day_sections:
                            if not section.strip():
                                continue
                            header_match = re.match(
                                r"(DAY \d+ MEAL PLAN)", section.strip())
                            if header_match:
                                with st.expander(header_match.group(1)):
                                    st.markdown(
                                        f"```text\n{section.strip()}\n```")
                            else:
                                # Fallback – show any leftover text
                                st.markdown(f"```text\n{section.strip()}\n```")
                    else:
                        st.warning("Meal plan data stored but no text found.")
                except Exception as meal_err:
                    st.error(f"Failed to display meal plan: {meal_err}")
            else:
                st.info("No meal plan stored for this user yet.")

        with workout_tab:
            st.subheader("💪 Workout Program")

            try:
                # Force reload the workout_utils module to clear any cache
                import importlib
                import sys
                if 'workout_utils' in sys.modules:
                    importlib.reload(sys.modules['workout_utils'])

                from workout_utils import get_current_week_workouts, get_recent_workouts, format_workout_summary_for_prompt

                # Determine the correct username for workout lookups
                # Use the username parameter (data key) instead of ig_username which can be empty
                # This is the key from analytics data (e.g., 'shane_minahan')
                workout_username = username

                # Debug: Show what username we're using
                st.write(
                    f"🔍 Debug: Looking up workouts for username: '{workout_username}' (ig_username: '{ig_username}')")

                # Test database connection first
                st.write("🔍 Debug: Testing workout_utils functions...")

                # Current week workouts
                weekly_workouts = get_current_week_workouts(workout_username)

                # Debug: Show raw result
                st.write(
                    f"🔍 Debug: Function returned {weekly_workouts['total_sessions']} sessions")

                # Additional debug: show the actual weekly_workouts dict structure
                st.write(
                    f"🔍 Debug: Weekly workouts structure: {weekly_workouts}")

                # Show week date range
                if weekly_workouts.get('week_start') and weekly_workouts.get('week_end'):
                    week_start = weekly_workouts['week_start']
                    week_end = weekly_workouts['week_end']
                    st.subheader(
                        f"📅 Most Recent Week's Sessions ({week_start} to {week_end})")
                else:
                    st.subheader("📅 Most Recent Week's Sessions")

                if weekly_workouts['total_sessions'] > 0:
                    st.success(
                        f"**{weekly_workouts['total_sessions']} sessions completed last week**")

                    # Show improvements first if any
                    if weekly_workouts.get('improvements'):
                        st.subheader("🎯 Progress This Week")
                        improvement_cols = st.columns(2)

                        for i, improvement in enumerate(weekly_workouts['improvements']):
                            col = improvement_cols[i % 2]
                            with col:
                                if improvement['type'] == 'weight':
                                    st.success(
                                        f"**{improvement['exercise']}**: Weight: {improvement['improvement']}")
                                elif improvement['type'] == 'reps':
                                    st.success(
                                        f"**{improvement['exercise']}**: Reps: {improvement['improvement']}")
                        st.write("---")

                    # Show each workout session
                    for i, workout in enumerate(weekly_workouts['workouts'], 1):
                        with st.expander(f"Session {i}: {workout['name']} ({workout['date']})"):
                            if workout['exercises']:
                                for exercise in workout['exercises']:
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.write(f"**{exercise['name']}**")
                                    with col2:
                                        st.write(f"{exercise['sets']} sets")
                                    with col3:
                                        st.write(
                                            f"{exercise['total_reps']} total reps")
                                    with col4:
                                        if exercise['max_weight'] > 0:
                                            st.write(
                                                f"Max: {exercise['max_weight']}kg")
                                        else:
                                            st.write("Bodyweight")
                            else:
                                st.info("No exercise data recorded")
                else:
                    st.info("No workout sessions logged last week")

                # Recent workouts (last 2 weeks)
                st.subheader("📊 Recent Activity (Last 2 Weeks)")
                recent_workouts = get_recent_workouts(
                    workout_username, days=14)

                # Debug recent workouts
                st.write(
                    f"🔍 Debug: get_recent_workouts returned {len(recent_workouts) if recent_workouts else 0} sessions")

                if recent_workouts:
                    st.write(
                        f"**{len(recent_workouts)} total sessions in last 2 weeks**")

                    # Show summary of recent exercises
                    all_exercises = {}
                    for workout in recent_workouts:
                        for exercise in workout['exercises']:
                            name = exercise['name']
                            if name not in all_exercises:
                                all_exercises[name] = {
                                    'sessions': 0, 'total_sets': 0, 'total_reps': 0, 'max_weight': 0}

                            all_exercises[name]['sessions'] += 1
                            all_exercises[name]['total_sets'] += exercise['sets']
                            all_exercises[name]['total_reps'] += exercise['total_reps']
                            all_exercises[name]['max_weight'] = max(
                                all_exercises[name]['max_weight'], exercise['max_weight'])

                    if all_exercises:
                        st.write("**Exercise Summary:**")
                        for exercise_name, stats in sorted(all_exercises.items(), key=lambda x: x[1]['sessions'], reverse=True):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.write(f"**{exercise_name}**")
                            with col2:
                                st.write(f"{stats['sessions']} sessions")
                            with col3:
                                st.write(f"{stats['total_sets']} total sets")
                            with col4:
                                if stats['max_weight'] > 0:
                                    st.write(f"Best: {stats['max_weight']}kg")
                                else:
                                    st.write("Bodyweight")
                else:
                    st.info("No recent workout data available")

            except Exception as e:
                st.error(f"Error loading workout data: {str(e)}")
                import traceback
                st.write("🔍 Debug: Full error traceback:")
                st.code(traceback.format_exc())
                st.info("Workout data integration in progress...")

        with checkin_tab:
            st.subheader("📝 Weekly Check-in Review")
            # --- START: Refined Check-in Data Loading (Prioritize Analysis Name) ---
            first_name = None
            last_name = None
            source_used = "None"

            # 1. Try getting name from client_analysis first
            person_name_analysis = client_analysis.get(
                "profile_bio", {}).get("PERSON NAME")
            if isinstance(person_name_analysis, str) and person_name_analysis.strip() and person_name_analysis.strip().lower() != 'unknown':
                person_name_analysis = person_name_analysis.strip()
                name_parts = person_name_analysis.split()
                if len(name_parts) >= 1:
                    first_name = name_parts[0]
                if len(name_parts) >= 2:
                    last_name = name_parts[-1]  # Assume last part is last name
                if first_name and last_name:
                    source_used = "client_analysis"
                else:
                    # Reset if we didn't get both parts
                    first_name = None
                    last_name = None

            # 2. If client_analysis didn't yield both names, try sheet_details
            if not (first_name and last_name) and sheet_details:
                sheet_first = sheet_details.get('first_name')
                sheet_last = sheet_details.get('last_name')
                if sheet_first and sheet_last:
                    first_name = sheet_first
                    last_name = sheet_last
                    source_used = "sheet_details"

            # --- Debugging --- #
            if first_name and last_name:
                st.write(
                    f"_Debug: Using Name: {first_name} {last_name} (Source: {source_used})_ ")
            else:
                st.write("_Debug: Failed to find usable first/last name._")
                st.write(f"_Debug: Analysis Name: {person_name_analysis}_")
                st.write(
                    f"_Debug: Sheet Details: {sheet_details.get('first_name')} {sheet_details.get('last_name')}_")
            # --- End Debugging ---

            if first_name and last_name:
                # Pass the first and last names to the reverted function
                latest_checkin_file = find_latest_checkin_file(
                    first_name, last_name, CHECKIN_REVIEWS_DIR)

                if latest_checkin_file:
                    # st.write(f"Latest Check-in File Found: `{os.path.basename(latest_checkin_file)}`") # Debug in find func
                    checkin_data = load_json_data(latest_checkin_file)

                    if checkin_data:
                        # Display the loaded check-in data
                        st.markdown(
                            f"#### Check-in for Week: **{checkin_data.get('date_range', 'N/A')}**")

                        st.divider()

                        # Key Metrics Columns
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Workouts", checkin_data.get(
                                'workouts_this_week', 'N/A'), help="Number of workouts completed this week.")
                            st.metric("Avg Calories", checkin_data.get(
                                'calories_consumed', 'N/A'), help="Average daily calorie intake.")
                        with col2:
                            st.metric("Avg Steps", checkin_data.get(
                                'step_count', 'N/A'), help="Average daily step count.")
                            st.metric("Avg Sleep", checkin_data.get(
                                'sleep_hours', 'N/A'), help="Average nightly sleep duration.")
                        with col3:
                            weight = checkin_data.get('current_weight')
                            # Safely handle weight conversion
                            if weight is not None and str(weight).replace('.', '').replace('-', '').isdigit():
                                try:
                                    weight_str = f"{int(float(weight))} kg"
                                except (ValueError, TypeError):
                                    weight_str = 'N/A'
                            else:
                                weight_str = 'N/A'
                            st.metric("Weight", weight_str,
                                      help="Most recent weight recorded.")

                            change = checkin_data.get('total_weight_change')
                            # Safely handle weight change conversion
                            if change is not None and str(change).replace('.', '').replace('-', '').isdigit():
                                try:
                                    change_val = float(change)
                                    change_str = f"{int(abs(change_val))} kg {'Loss' if change_val > 0 else 'Gain'}"
                                    delta_str = f"{int(change_val)} kg"
                                except (ValueError, TypeError):
                                    change_str = 'N/A'
                                    delta_str = None
                            else:
                                change_str = 'N/A'
                                delta_str = None
                            st.metric("Total Change", change_str, delta=delta_str,
                                      delta_color="inverse", help="Total weight change since starting.")

                        st.divider()

                        # Personalized Message
                        st.markdown("#### Personalized Feedback")
                        st.info(checkin_data.get('personalized_message',
                                'No personalized message available.'))

                        # Most Improved Exercise
                        improved_exercise = checkin_data.get(
                            'most_improved_exercise')
                        if improved_exercise:
                            st.markdown("#### Top Exercise Improvement")
                            st.success(
                                f"**{improved_exercise.get('name', 'N/A')}**: {improved_exercise.get('improvement', 0):.1f}% improvement!")
                            st.write(
                                f"Best Set: {improved_exercise.get('best_weight', 'N/A')} kg x {improved_exercise.get('best_reps', 'N/A')} reps")

                        st.divider()

                        # Full Data Expander
                        with st.expander("View Full Check-in JSON Data"):
                            st.json(checkin_data)
                    else:
                        st.error(
                            f"Could not load data from check-in file: {os.path.basename(latest_checkin_file)}")
                else:
                    st.info(
                        f"No recent weekly check-in file found matching name: {first_name} {last_name}")
            else:
                st.warning(
                    "Cannot retrieve check-in data. User's first and last name not found or incomplete in profile details.")
            # --- END: Refined Check-in Data Loading ---

        with history_tab:
            st.subheader("💬 Conversation History")

            # Safely get conversation history from multiple possible locations
            conversation_history = []

            # Try history first (main location from SQLite loader)
            if user_data.get('history') and isinstance(user_data['history'], list):
                conversation_history = user_data['history']
            # Try metrics.conversation_history (backup location)
            elif user_data.get('metrics', {}).get('conversation_history') and isinstance(user_data['metrics']['conversation_history'], list):
                conversation_history = user_data['metrics']['conversation_history']

            if conversation_history:
                # Show conversation summary
                user_msgs = sum(
                    1 for msg in conversation_history if msg.get('type') == 'user')
                ai_msgs = sum(
                    1 for msg in conversation_history if msg.get('type') == 'ai')
                other_msgs = len(conversation_history) - user_msgs - ai_msgs

                st.info(f"📊 **Conversation Summary**: {len(conversation_history)} total messages | " +
                        f"🗣️ {user_msgs} from user | 🤖 {ai_msgs} from AI" +
                        (f" | ❓ {other_msgs} other" if other_msgs > 0 else ""))
                for i, message in enumerate(conversation_history):
                    try:
                        # Handle both dict and string message formats
                        if isinstance(message, str):
                            st.markdown(f"**Message {i+1}:** {message}")
                            st.markdown("---")
                            continue

                        if not isinstance(message, dict):
                            st.markdown(
                                f"**Message {i+1} (Unknown format):** {str(message)}")
                            st.markdown("---")
                            continue

                        # Safe dict access with full timestamp formatting
                        timestamp = ''
                        if message.get('timestamp'):
                            try:
                                # Parse the full ISO timestamp and format it nicely
                                from datetime import datetime
                                timestamp_str = str(message['timestamp'])

                                # Handle different timestamp formats
                                if 'T' in timestamp_str:
                                    # ISO format: 2025-07-27T07:33:16.800175
                                    dt = datetime.fromisoformat(
                                        timestamp_str.split('+')[0].split('Z')[0])
                                    timestamp = dt.strftime(
                                        '%Y-%m-%d %H:%M:%S')
                                else:
                                    # Simple date format
                                    timestamp = timestamp_str
                            except Exception as e:
                                timestamp = str(message['timestamp'])[:19] if len(
                                    str(message['timestamp'])) > 19 else str(message['timestamp'])
                        else:
                            timestamp = 'Unknown'

                        message_type = message.get('type', 'unknown')
                        message_text = message.get('text', '')

                        with st.container():
                            if message_type == 'user':
                                st.markdown(f"🗣️ **User** ({timestamp}):")
                                st.info(message_text)
                            elif message_type == 'ai':
                                st.markdown(
                                    f"🤖 **Shannon (AI)** ({timestamp}):")
                                st.success(message_text)
                            else:
                                st.markdown(
                                    f"❓ **{message_type}** ({timestamp}):")
                                st.markdown(f">{message_text}")
                            st.markdown("---")
                    except Exception as e:
                        st.error(f"Error displaying message {i+1}: {e}")
                        st.markdown("---")
            else:
                st.write("No conversation history available.")

        # ----------------- ONBOARDING FORM TAB -----------------
        with onboarding_tab:
            st.subheader("📄 Coaching Onboarding Form")
            try:
                import sqlite3
                SQLITE_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
                conn = sqlite3.connect(SQLITE_PATH)
                c = conn.cursor()
                c.execute(
                    "SELECT onboarding_form_json FROM users WHERE ig_username = ?", (ig_username,))
                row = c.fetchone()
                conn.close()

                if row and row[0]:
                    try:
                        import json as _json
                        form_data = _json.loads(row[0])

                        # Quick summary
                        phys = form_data.get("physical_info", {})
                        diet = form_data.get("dietary_info", {})
                        train = form_data.get("training_info", {})

                        def _get(path, default=""):  # helper to fetch nested value
                            return path.get("value", default) if isinstance(path, dict) else default

                        st.write(
                            f"**Primary Goal:** {_get(phys.get('primary_fitness_goal'))}")
                        st.write(
                            f"**Current Weight (kg):** {_get(phys.get('current_weight_kg'))}")
                        st.write(
                            f"**Target Calories Estimate:** {diet.get('daily_calories', {}).get('value', 'N/A')}")
                        st.write(
                            f"**Training Days:** {_get(train.get('training_days'))}")

                        st.markdown("---")
                        st.caption("Full form data")
                        st.json(form_data)
                    except Exception as parse_err:
                        st.error(
                            f"Failed to parse onboarding form JSON: {parse_err}")
                else:
                    st.info("No onboarding form stored for this user yet.")
            except Exception as db_err:
                st.error(f"Database error retrieving form: {db_err}")
        # ------------- END ONBOARDING FORM TAB -------------

    except Exception as e:
        st.error(f"Error displaying user profile: {e}")


def display_user_profiles(analytics_data: Dict[str, Any]):
    """Display the user profiles page"""
    st.header("👥 User Profiles")

    # Get list of categorized usernames
    categorized_users = get_usernames(analytics_data)

    if categorized_users:
        # Create formatted options for the dropdown
        options = [f"{color} {username} ({responses} messages)"
                   for username, color, responses in categorized_users]

        # Create dropdown for username selection
        selected_option = st.selectbox(
            "Select a user to view their profile",
            options,
            index=None,
            placeholder="Choose a username..."
        )

        # Display user profile when selected
        if selected_option:
            # Extract the actual username from the formatted option string
            # Assuming the format is "emoji username (responses messages)"
            # A more robust way to get the username would be to store the raw usernames
            # alongside the formatted options if format changes.
            try:
                # Find the first space (after emoji) and the first opening parenthesis
                first_space_index = selected_option.find(' ')
                first_parenthesis_index = selected_option.find('(')
                if first_space_index != -1 and first_parenthesis_index != -1 and first_parenthesis_index > first_space_index:
                    selected_user = selected_option[first_space_index +
                                                    1:first_parenthesis_index].strip()
                else:  # Fallback if parsing fails, though less likely with current formatting
                    selected_user = selected_option.split(" ")[1]
            except IndexError:
                st.error(
                    f"Could not parse username from selection: {selected_option}")
                return

            user_data = None

            # Try to get user_data from top-level first
            if selected_user in analytics_data and isinstance(analytics_data[selected_user], dict):
                user_data = analytics_data[selected_user]
            # If not found at top-level, try under 'conversations'
            elif 'conversations' in analytics_data and isinstance(analytics_data['conversations'], dict) and \
                 selected_user in analytics_data['conversations'] and isinstance(analytics_data['conversations'][selected_user], dict):
                user_data = analytics_data['conversations'][selected_user]

            if user_data:
                display_user_profile(selected_user, user_data)
            else:
                st.error(f"No data found for user: {selected_user}")
                st.info(
                    "This user may not have been loaded from the database or may not have any conversation data.")
    else:
        st.warning(
            "No usernames found in the analytics data. Please check the data format or refresh the data.")


def update_user_stage(ig_username: str, new_stage: str, user_data: Dict[str, Any]) -> bool:
    """Update user's journey stage and save to SQLite"""
    try:
        metrics = user_data.get('metrics', {})
        journey_stage = metrics.get('journey_stage', {})

        # Ensure journey_stage is a dict
        if not isinstance(journey_stage, dict):
            journey_stage = {}

        current_time = datetime.datetime.now()

        # Update based on new stage
        if new_stage == "Lead":
            journey_stage['current_stage'] = 'Topic 1'
            journey_stage['is_paying_client'] = False
            journey_stage['trial_start_date'] = None
            journey_stage['trial_end_date'] = None
            # Reset topic progress for leads
            journey_stage['topic_progress'] = {}

        elif new_stage == "4 Week Trial":
            journey_stage['current_stage'] = 'Trial Week 1'
            journey_stage['is_paying_client'] = False
            journey_stage['trial_start_date'] = current_time.isoformat()
            journey_stage['trial_end_date'] = (
                current_time + datetime.timedelta(days=28)).isoformat()
            # Mark topics as completed to reach trial stage
            journey_stage['topic_progress'] = {
                'topic1_completed': True,
                'topic2_completed': True,
                'topic3_completed': True,
                'topic4_completed': True,
                'trial_offer_made': True
            }

        elif new_stage == "Paying Client":
            journey_stage['current_stage'] = 'Paying Client'
            journey_stage['is_paying_client'] = True
            journey_stage['trial_start_date'] = None
            journey_stage['trial_end_date'] = None
            # Mark all topics as completed
            journey_stage['topic_progress'] = {
                'topic1_completed': True,
                'topic2_completed': True,
                'topic3_completed': True,
                'topic4_completed': True,
                'trial_offer_made': True
            }

        # Update the metrics
        metrics['journey_stage'] = journey_stage
        metrics['last_updated'] = current_time.isoformat()

        # Save to SQLite using update_analytics_data with required parameters
        subscriber_id = metrics.get('subscriber_id', ig_username)
        first_name = metrics.get('first_name', '')
        last_name = metrics.get('last_name', '')

        # Add debugging
        logger.info(
            f"Attempting to update stage for {ig_username} to {new_stage}")
        logger.info(f"Subscriber ID: {subscriber_id}")
        logger.info(f"First Name: {first_name}")
        logger.info(f"Last Name: {last_name}")

        # Check if update_analytics_data is available
        if update_analytics_data is None:
            logger.error("update_analytics_data function is not available")
            st.error("Database function not available")
            return False

        # Test the function signature
        logger.info(f"update_analytics_data function: {update_analytics_data}")
        logger.info(
            f"Function signature: {update_analytics_data.__code__.co_varnames}")

        try:
            success = update_analytics_data(
                subscriber_id=subscriber_id,
                ig_username=ig_username,
                message_text=f"Stage updated to {new_stage} via dashboard",
                message_direction="system",
                timestamp=current_time.isoformat(),
                first_name=first_name,
                last_name=last_name,
                client_status=new_stage,
                journey_stage=json.dumps(journey_stage),
                is_onboarding=metrics.get('is_onboarding', False),
                is_in_checkin_flow_mon=metrics.get(
                    'is_in_checkin_flow_mon', False),
                is_in_checkin_flow_wed=metrics.get(
                    'is_in_checkin_flow_wed', False),
                client_analysis_json=json.dumps(
                    metrics.get('client_analysis', {})),
                offer_made=metrics.get('offer_made', False),
                is_in_ad_flow=metrics.get('is_in_ad_flow', False),
                ad_script_state=metrics.get('ad_script_state'),
                ad_scenario=metrics.get('ad_scenario'),
                lead_source=metrics.get('lead_source')
            )
            logger.info(f"update_analytics_data returned: {success}")
        except Exception as e:
            logger.error(f"Exception in update_analytics_data: {e}")
            st.error(f"Database error: {e}")
            return False

        if success:
            # Also update the session state to reflect changes immediately
            if 'analytics_data' in st.session_state:
                # Update the session state data
                if 'conversations' in st.session_state.analytics_data:
                    if ig_username in st.session_state.analytics_data['conversations']:
                        st.session_state.analytics_data['conversations'][ig_username]['metrics'] = metrics
                        logger.info(
                            f"Updated session state for {ig_username} with new stage: {new_stage}")

            # NEW: Remove from fresh vegan auto mode if they became trial/paying member
            if new_stage and ('trial' in new_stage.lower() or 'paying' in new_stage.lower()):
                try:
                    from conversation_strategy import check_and_cleanup_vegan_eligibility
                    check_and_cleanup_vegan_eligibility(ig_username)
                except ImportError:
                    logger.warning("Could not import vegan cleanup function")

            # NEW: Clean up from ad flow if they became a paying client
            if new_stage and 'paying' in new_stage.lower():
                try:
                    from paying_client_cleanup import cleanup_paying_client_from_ad_flow
                    cleanup_paying_client_from_ad_flow(ig_username)
                except ImportError:
                    logger.warning(
                        "Could not import paying client cleanup function")

            # NEW: Add notifications for important stage changes
            try:
                from notifications import add_trial_notification, add_sale_notification

                if new_stage and 'trial' in new_stage.lower():
                    add_trial_notification(ig_username, new_stage)
                    logger.info(f"Added trial notification for {ig_username}")
                elif new_stage and ('paying' in new_stage.lower() or 'client' in new_stage.lower()):
                    add_sale_notification(ig_username, new_stage)
                    logger.info(f"Added sale notification for {ig_username}")
            except ImportError as e:
                logger.warning(f"Could not import notification functions: {e}")

            st.success(f"Stage updated to '{new_stage}' for {ig_username}!")
            return True
        else:
            st.error(f"Failed to update stage for {ig_username}")
            return False

    except Exception as e:
        st.error(f"Error updating user stage: {e}")
        logger.error(f"Error updating user stage for {ig_username}: {e}")
        return False


def trigger_check_in(
    ig_username: str,
    checkin_type: str,
    user_data: Dict[str, Any],
    current_mon_checkin_status: bool = False,
    current_wed_checkin_status: bool = False
) -> bool:
    """
    Toggle a check-in flow for a user by setting the appropriate flag.

    Args:
        ig_username: The user's Instagram username
        checkin_type: Either "monday" or "wednesday"
        user_data: The user's data dictionary
        current_mon_checkin_status: The current status of the Monday check-in
        current_wed_checkin_status: The current status of the Wednesday check-in

    Returns:
        bool: True if successful, False otherwise
    """
    if not update_analytics_data:
        st.error(
            "Check-in functionality not available - update_analytics_data not imported")
        return False

    try:
        metrics = user_data.get('metrics', {})
        first_name = metrics.get('first_name', '')
        last_name = metrics.get('last_name', '')

        new_mon_status = metrics.get('is_in_checkin_flow_mon', False)
        new_wed_status = metrics.get('is_in_checkin_flow_wed', False)

        if checkin_type == "monday":
            new_mon_status = not current_mon_checkin_status
            if new_mon_status:  # if activating monday, ensure wednesday is off
                new_wed_status = False
        elif checkin_type == "wednesday":
            new_wed_status = not current_wed_checkin_status
            if new_wed_status:  # if activating wednesday, ensure monday is off
                new_mon_status = False
        else:
            st.error(f"Invalid check-in type: {checkin_type}")
            return False

        # Call update_analytics_data with the new states
        update_analytics_data(
            subscriber_id=metrics.get('subscriber_id', ''),
            ig_username=ig_username,
            message_text="",
            message_direction="system",
            timestamp=datetime.datetime.now().isoformat(),
            first_name=first_name,
            last_name=last_name,
            is_in_checkin_flow_mon=new_mon_status,
            is_in_checkin_flow_wed=new_wed_status
        )

        logger.info(
            f"Toggled {checkin_type} check-in for {ig_username} to MON:{new_mon_status}, WED:{new_wed_status}")

        # Update the metrics in user_data directly to reflect in UI before SQLite save and full refresh
        # This part is crucial for immediate UI feedback if update_analytics_data doesn't update the passed user_data dict by reference.
        metrics['is_in_checkin_flow_mon'] = new_mon_status
        metrics['is_in_checkin_flow_wed'] = new_wed_status
        # Ensure the user_data dictionary in the session state is updated if it's not the same object
        if 'analytics_data' in st.session_state and \
           'conversations' in st.session_state.analytics_data and \
           ig_username in st.session_state.analytics_data['conversations'] and \
           st.session_state.analytics_data['conversations'][ig_username].get('metrics') is not metrics:
            st.session_state.analytics_data['conversations'][ig_username][
                'metrics']['is_in_checkin_flow_mon'] = new_mon_status
            st.session_state.analytics_data['conversations'][ig_username][
                'metrics']['is_in_checkin_flow_wed'] = new_wed_status
            logger.info(
                f"Updated session state check-in flags for {ig_username}")

        return True

    except Exception as e:
        st.error(f"Error toggling {checkin_type} check-in: {e}")
        logger.error(
            f"Error toggling {checkin_type} check-in for {ig_username}: {e}", exc_info=True)
        return False
