# New Leads Module

import streamlit as st
import sqlite3
import json
import os
import subprocess
import google.generativeai as genai

# --- Configuration ---
DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
PROJECT_ROOT = r"C:\Users\Shannon\OneDrive\Desktop\shanbot"
FIND_CLIENTS_SCRIPT = os.path.join(PROJECT_ROOT, "find_potential_clients.py")
FOLLOWUP_MANAGER_SCRIPT = os.path.join(PROJECT_ROOT, "followup_manager.py")
FOLLOWUP_QUEUE_FILE = os.path.join(PROJECT_ROOT, "followup_queue.json")

# Configure Gemini
try:
    GEMINI_API_KEY = st.secrets["general"]["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    GEMINI_API_KEY = "AIzaSyAH6467EocGBwuMi-oDLawrNyCKjPHHmN8"
    genai.configure(api_key=GEMINI_API_KEY)

# --- Helper Functions ---


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def fetch_new_leads():
    """Fetches all new leads from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, coaching_score, hashtag_found, analysis_data, created_at
            FROM new_leads
            ORDER BY created_at DESC
        """)
        leads = cursor.fetchall()
        conn.close()
        return leads
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            st.warning(
                "The 'new_leads' table does not exist. Run a search to create it.")
            return []
        st.error(f"Database error: {e}")
        return []


def categorize_leads(leads):
    """Categorizes leads into 'local' and 'online'."""
    local_leads = []
    online_leads = []
    for lead in leads:
        try:
            analysis_data = json.loads(lead[3]) if lead[3] else {}
            search_mode = analysis_data.get('analysis', {}).get(
                'search_mode', 'online')  # Default to online
            if search_mode == 'local':
                local_leads.append(lead)
            else:
                online_leads.append(lead)
        except (json.JSONDecodeError, KeyError):
            online_leads.append(lead)  # Add to online if parsing fails
    return local_leads, online_leads


def trigger_script(script_path, args, cwd):
    """Triggers a Python script in a new console window."""
    try:
        command = ["python", script_path] + args
        subprocess.Popen(
            command,
            cwd=cwd,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return True
    except Exception as e:
        st.error(f"Failed to start script: {e}")
        return False


def generate_initial_dm(lead_type, username):
    """Generates an initial DM for a new lead."""
    if not genai:
        return "Gemini not configured."

    prompt_template = {
        "local": f"You are Shannon, a friendly local fitness coach from Bayside, Melbourne. Write a very short, casual, and friendly opening DM to @{username}, who you noticed is also local. Your goal is just to say hi and make a connection, not to sell anything. Be chill and authentic. Mention something about being in the same area. Keep it under 20 words.",
        "online": f"You are Shannon, a friendly online vegan fitness coach. Write a very short, casual, and friendly opening DM to @{username}, who you noticed is also into the plant-based lifestyle. Your goal is just to say hi and connect over your shared interest, not to sell anything. Be chill and authentic. Keep it under 20 words."
    }

    prompt = prompt_template.get(lead_type, prompt_template['online'])

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating DM: {e}"


def queue_dms_and_run(leads, lead_type):
    """Generates DMs for a list of leads, saves them to the queue, and runs the followup manager."""
    with st.spinner(f"Generating DMs for {len(leads)} {lead_type} leads..."):
        message_queue = []
        for lead in leads:
            username = lead[0]
            message = generate_initial_dm(lead_type, username)
            message_queue.append({
                'username': username,
                'message': message,
                'topic': f'Initial DM - {lead_type}',
                # Placeholder
                'queued_time': st.session_state.get('start_time', '')
            })

        if not message_queue:
            st.warning("No DMs were generated.")
            return

    try:
        with open(FOLLOWUP_QUEUE_FILE, 'w') as f:
            json.dump({'messages': message_queue}, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save DM queue: {e}")
        return

    st.success(
        f"Generated and queued {len(message_queue)} DMs. Starting followup manager...")
    trigger_script(FOLLOWUP_MANAGER_SCRIPT, [], PROJECT_ROOT)


# --- UI Components ---

def display_lead_search_buttons():
    """Displays buttons to trigger lead generation scripts."""
    st.header("🔎 Find New Potential Clients")
    st.caption(
        "Click a button to start searching for new leads in the background.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👩‍👩‍👧‍👦 Find 100 Local Clients", use_container_width=True, type="primary"):
            if trigger_script(FIND_CLIENTS_SCRIPT, ["--search-mode", "local", "--num-clients", "100"], PROJECT_ROOT):
                st.success(
                    "Started searching for local clients! A new window will open with the progress.")
    with col2:
        if st.button("🌱 Find 100 Vegan/Online Clients", use_container_width=True, type="primary"):
            if trigger_script(FIND_CLIENTS_SCRIPT, ["--search-mode", "online", "--num-clients", "100"], PROJECT_ROOT):
                st.success(
                    "Started searching for online clients! A new window will open with the progress.")
    st.divider()


def display_leads_section(title, leads, lead_type):
    """Displays a section for a specific type of lead."""
    st.header(title)

    if not leads:
        st.info(f"No new {lead_type} leads found yet.")
        return

    if st.button(f"📲 DM All {len(leads)} New {lead_type.capitalize()} Leads", key=f"dm_{lead_type}", use_container_width=True):
        queue_dms_and_run(leads, lead_type)

    st.write(f"Found {len(leads)} new leads.")
    for lead in leads:
        username, score, hashtag, analysis_data_str, created_at = lead
        with st.expander(f"@{username} (Score: {score or 'N/A'})"):
            st.write(f"**Found via:** #{hashtag}")
            st.write(f"**Date Found:** {created_at}")
            st.link_button("Go to Instagram Profile",
                           f"https://instagram.com/{username}")

            try:
                analysis = json.loads(
                    analysis_data_str) if analysis_data_str else {}
                st.json(analysis, expanded=False)
            except json.JSONDecodeError:
                st.write("**Analysis Data:**")
                st.code(analysis_data_str)

# --- Main Function ---


def main():
    """Main function to render the New Leads dashboard."""
    st.title("🌟 New Leads Dashboard")

    display_lead_search_buttons()

    all_leads = fetch_new_leads()
    local_leads, online_leads = categorize_leads(all_leads)

    # Create tabs for each lead type
    tab1, tab2 = st.tabs(
        [f"📍 Local Leads ({len(local_leads)})", f"🌱 Online/Vegan Leads ({len(online_leads)})"])

    with tab1:
        display_leads_section("Local Leads", local_leads, "local")

    with tab2:
        display_leads_section("Online/Vegan Leads", online_leads, "online")


if __name__ == "__main__":
    main()
