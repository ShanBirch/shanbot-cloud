import streamlit as st
import sqlite3
import os
import subprocess
import json
from datetime import datetime, timedelta

# --- Constants ---
DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"
RESULTS_FILE = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\followback_results.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DUAL_MODE_SCRIPT_PATH = os.path.join(
    os.path.dirname(SCRIPT_DIR), '..', 'dual_mode_smart_finder.py')
SINGLE_MODE_SCRIPT_PATH = os.path.join(
    os.path.dirname(SCRIPT_DIR), '..', 'smart_lead_finder.py')

# --- Database Functions ---


def get_db_connection():
    """Establish connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def get_pending_check_count():
    """Get the number of users pending a follow-back check (comprehensive mode - last 7 days, excluding today)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Count users from last 7 days who need checking (matches script logic)
        # EXCLUDE today's follows to give people time to follow back
        cursor.execute("""
            SELECT COUNT(*) FROM processing_queue
            WHERE (follow_back_status IS NULL OR follow_back_status = 'pending')
            AND (dm_status IS NULL OR dm_status != 'sent')
            AND followed_at >= DATE('now', '-7 days')
            AND followed_at < DATE('now', 'start of day')
        """)
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0  # Return 0 on error
    finally:
        if conn:
            conn.close()


def get_ready_to_process_count():
    """Get the number of users who followed back and are ready for DM."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM processing_queue
            WHERE follow_back_status = 'yes' AND dm_status IS NULL
        """)
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        if conn:
            conn.close()


def get_active_prospects_count():
    """Get the number of users who have been sent a DM and we are awaiting a reply."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM processing_queue
            WHERE dm_status = 'sent' AND follow_back_status = 'yes'
        """)
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        if conn:
            conn.close()


def get_todays_actions():
    """Get today's outreach actions: Online Follows (OF) and DMs Sent (OD)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')

        # Today's Online Follows
        cursor.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE DATE(followed_at) = ?", (today,))
        online_follows = cursor.fetchone()[0]

        # Today's DMs Sent
        cursor.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE DATE(followed_at) = ? AND dm_status = 'sent'", (today,))
        dms_sent = cursor.fetchone()[0]

        return online_follows, dms_sent
    except Exception:
        return 0, 0
    finally:
        if conn:
            conn.close()


def get_users_ready_for_analysis():
    """Get the number of users ready for follow-back analysis (from last 7 days, excluding today)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Count ALL unchecked users from the last 7 days (excluding today)
        # Match the same logic as the updated script
        cursor.execute("""
            SELECT COUNT(*) FROM processing_queue 
            WHERE (follow_back_status IS NULL OR follow_back_status = 'pending')
            AND (dm_status IS NULL OR dm_status != 'sent')
            AND followed_at >= DATE('now', '-7 days')
            AND followed_at < DATE('now', 'start of day')
        """)

        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        if conn:
            conn.close()


def get_weekly_lead_stats():
    """Get lead generation statistics for the past 7 days."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        weekly_stats = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i+1)).strftime('%Y-%m-%d')

            # Get basic stats for this date
            cursor.execute(
                "SELECT COUNT(*) FROM processing_queue WHERE DATE(followed_at) = ?", (date,))
            followed = cursor.fetchone()[0]

            # FIXED: Count people who were followed on this date AND have since followed back
            # This accounts for the delay between following and follow-back checking
            cursor.execute("""
                SELECT COUNT(*) FROM processing_queue 
                WHERE DATE(followed_at) = ? 
                AND follow_back_status = 'yes'
            """, (date,))
            followed_back = cursor.fetchone()[0]

            weekly_stats.append({
                'date': date,
                'followed': followed,
                'followed_back': followed_back,
                'follow_back_rate': (followed_back / followed * 100) if followed > 0 else 0
            })

        return weekly_stats
    except Exception as e:
        print(f"Error getting weekly stats: {e}")
        return []
    finally:
        if conn:
            conn.close()


def display_weekly_stats():
    """Display 7-day lead generation trend analysis."""
    # Header with refresh button
    col_header, col_refresh = st.columns([4, 1])
    with col_header:
        st.subheader("📈 7-Day Lead Generation Trend")
    with col_refresh:
        if st.button("🔄 Refresh Stats", key="refresh_weekly_stats"):
            st.rerun()

    weekly_stats = get_weekly_lead_stats()
    if not weekly_stats:
        st.info("📭 No lead generation activity recorded for the past 7 days.")
        return

    # Calculate totals
    total_followed = sum(s['followed'] for s in weekly_stats)
    total_followed_back = sum(s['followed_back'] for s in weekly_stats)
    avg_follow_back_rate = (total_followed_back /
                            total_followed * 100) if total_followed > 0 else 0

    if total_followed == 0:
        st.info("📭 No lead generation activity recorded for the past 7 days.")
        return

    # Weekly summary metrics in 3 columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "👥 TOTAL FOLLOWED (7 days)",
            total_followed,
            help="Total number of people followed across both accounts in the past 7 days"
        )

    with col2:
        st.metric(
            "✅ TOTAL FOLLOWED BACK",
            total_followed_back,
            delta=f"{avg_follow_back_rate:.1f}%",
            help="Number of people who followed back after we followed them"
        )

    with col3:
        # Get yesterday's stats for trend indicator
        yesterday_stats = weekly_stats[0] if weekly_stats else {
            'follow_back_rate': 0}
        trend_indicator = f"Yesterday: {yesterday_stats['follow_back_rate']:.1f}%" if yesterday_stats[
            'follow_back_rate'] > 0 else "No activity yesterday"

        st.metric(
            "📈 AVG FOLLOW BACK RATE",
            f"{avg_follow_back_rate:.1f}%",
            delta=trend_indicator,
            help="Average follow-back rate over the past 7 days"
        )

    st.divider()

    # Daily breakdown table
    st.subheader("📊 Daily Breakdown")

    import pandas as pd
    df = pd.DataFrame(weekly_stats)
    df['Date'] = pd.to_datetime(df['date']).dt.strftime(
        '%a %m/%d')  # Include day of week
    df = df[['Date', 'followed', 'followed_back', 'follow_back_rate']]
    df.columns = ['Date', 'Followed', 'Followed Back', 'Follow Back Rate (%)']
    df['Follow Back Rate (%)'] = df['Follow Back Rate (%)'].round(1)

    # Reverse order so most recent is at top
    df = df.iloc[::-1].reset_index(drop=True)

    st.dataframe(df, hide_index=True, use_container_width=True)

    # Performance insights
    st.divider()
    st.subheader("💡 Performance Insights")

    perf_col1, perf_col2, perf_col3 = st.columns(3)

    with perf_col1:
        if avg_follow_back_rate >= 20:
            st.success(
                f"🎯 Excellent 7-day average: {avg_follow_back_rate:.1f}%")
        elif avg_follow_back_rate >= 15:
            st.info(f"📊 Good 7-day average: {avg_follow_back_rate:.1f}%")
        else:
            st.warning(f"📉 Low 7-day average: {avg_follow_back_rate:.1f}%")

    with perf_col2:
        # Find best performing day
        best_day = max(weekly_stats, key=lambda x: x['follow_back_rate'])
        if best_day['follow_back_rate'] > 0:
            best_date = pd.to_datetime(best_day['date']).strftime('%A')
            st.success(
                f"🌟 Best day: {best_date} ({best_day['follow_back_rate']:.1f}%)")
        else:
            st.info("🌟 Best day: No data yet")

    with perf_col3:
        # Calculate daily average
        daily_average = total_followed / 7
        if daily_average >= 20:
            st.success(f"🚀 Strong daily average: {daily_average:.0f} follows")
        elif daily_average >= 10:
            st.info(f"📈 Good daily average: {daily_average:.0f} follows")
        else:
            st.warning(f"⚠️ Low daily average: {daily_average:.0f} follows")

# --- Follow-back Results Functions ---


def get_followback_results():
    """Load recent follow-back check results from JSON file."""
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
            return results
        return []
    except Exception as e:
        print(f"Error loading results: {e}")
        return []


def display_followback_results():
    """Display recent follow-back check results."""
    results = get_followback_results()

    if not results:
        st.info(
            "📋 No follow-back check results yet. Results will appear here after running the check scripts.")
        return

    st.subheader("📊 Recent Follow-Back Check Results")
    st.caption("Latest results from your follow-back analysis scripts")

    # Display latest result prominently
    latest = results[0]

    # Time formatting
    try:
        result_time = datetime.fromisoformat(latest['timestamp'].split('+')[0])
        time_ago = datetime.now() - result_time
        if time_ago.days > 0:
            time_str = f"{time_ago.days} day{'s' if time_ago.days > 1 else ''} ago"
        elif time_ago.seconds > 3600:
            time_str = f"{time_ago.seconds // 3600} hour{'s' if time_ago.seconds // 3600 > 1 else ''} ago"
        else:
            time_str = f"{time_ago.seconds // 60} minute{'s' if time_ago.seconds // 60 > 1 else ''} ago"
    except:
        time_str = "Recently"

    # Latest result card
    account_emoji = "🏠" if latest['account_mode'] == 'local' else "🌱"
    account_name = "@cocos_pt_studio" if latest['account_mode'] == 'local' else "@cocos_connected"

    # Show analysis type
    analysis_description = latest.get(
        'analysis_description', f"Analysis date: {latest.get('analysis_date', 'Unknown')}")
    analysis_mode = latest.get('analysis_mode', 'unknown')

    if 'comprehensive' in analysis_mode:
        mode_emoji = "🔄"
        mode_text = "Comprehensive Check"
    else:
        mode_emoji = "📅"
        mode_text = "Date-Specific Check"

    st.success(
        f"**🆕 Latest Check: {account_emoji} {account_name}** - {mode_emoji} {mode_text} ({time_str})")
    st.caption(f"📊 {analysis_description}")

    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Dynamic help text based on analysis mode
        if 'comprehensive' in analysis_mode:
            help_text = "Total unchecked people processed from the last 7 days"
        else:
            help_text = "Total people followed on the analyzed date"

        st.metric(
            "👥 Checked",
            latest['total_followed_on_date'],
            help=help_text
        )

    with col2:
        st.metric(
            "✅ Followed Back",
            latest['followed_back_count'],
            delta=f"{latest['follow_back_percentage']:.1f}%"
        )

    with col3:
        st.metric(
            "❌ Unfollowed",
            latest['unfollowed_count'],
            help="People who didn't follow back and were unfollowed"
        )

    with col4:
        st.metric(
            "💬 DMs Sent",
            latest['dms_sent_count'],
            help="Personalized DMs sent to new followers"
        )

    # Show usernames if any
    if latest.get('followed_back_usernames') or latest.get('unfollowed_usernames'):
        with st.expander("👀 View Details", expanded=False):
            if latest.get('followed_back_usernames'):
                st.write(
                    f"**✅ New Followers ({len(latest['followed_back_usernames'])} people):**")
                for username in latest['followed_back_usernames'][:10]:  # Show max 10
                    st.caption(f"• @{username}")
                if len(latest['followed_back_usernames']) > 10:
                    st.caption(
                        f"... and {len(latest['followed_back_usernames']) - 10} more")

            if latest.get('unfollowed_usernames'):
                st.write(
                    f"**❌ Unfollowed ({len(latest['unfollowed_usernames'])} people):**")
                for username in latest['unfollowed_usernames'][:5]:  # Show max 5
                    st.caption(f"• @{username}")
                if len(latest['unfollowed_usernames']) > 5:
                    st.caption(
                        f"... and {len(latest['unfollowed_usernames']) - 5} more")

    # Show history of previous runs
    if len(results) > 1:
        with st.expander(f"📜 Previous Results ({len(results)-1} runs)", expanded=False):
            # Show up to 5 previous results
            for i, result in enumerate(results[1:6]):
                try:
                    prev_time = datetime.fromisoformat(
                        result['timestamp'].split('+')[0])
                    prev_date = prev_time.strftime('%Y-%m-%d %H:%M')
                except:
                    prev_date = "Unknown time"

                prev_emoji = "🏠" if result['account_mode'] == 'local' else "🌱"
                prev_account = "@cocos_pt_studio" if result['account_mode'] == 'local' else "@cocos_connected"

                # Show analysis type for previous results too
                prev_analysis_mode = result.get('analysis_mode', 'unknown')
                if 'comprehensive' in prev_analysis_mode:
                    mode_indicator = "🔄"
                else:
                    mode_indicator = "📅"

                st.write(
                    f"**{prev_emoji} {prev_account}** {mode_indicator} - {prev_date}")
                st.caption(
                    f"   📊 {result['total_followed_on_date']} checked • {result['followed_back_count']} followed back • {result['unfollowed_count']} unfollowed • {result['dms_sent_count']} DMs sent")
                if i < len(results[1:6]) - 1:
                    st.write("---")

# --- UI Functions ---


def display_metrics(online_count, local_count):
    """Display the main metrics row."""
    pending_check = get_pending_check_count()
    ready_to_process = get_ready_to_process_count()
    active_prospects = get_active_prospects_count()
    online_follows, dms_sent = get_todays_actions()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pending Check", pending_check,
                  help="Users from the last 7 days awaiting follow-back check (comprehensive mode, excluding today).")
    with col2:
        st.metric("Ready to Process", ready_to_process,
                  help="Users who followed back, ready for an initial DM.")
    with col3:
        st.metric("Active Prospects", active_prospects,
                  help="Users who have been DMed and are in active conversation.")
    with col4:
        st.metric("Today's Actions", f"{online_follows}F + {dms_sent}D",
                  help="Follows (F) and DMs (D) sent today.")


def trigger_script(script_path, *args):
    """Triggers a given Python script in a new console."""
    try:
        command = ["python", script_path, *args]
        st.info(f"🚀 Running command: {' '.join(command)}")
        subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
        st.success(
            f"✅ Script '{os.path.basename(script_path)}' started successfully in a new window!")
    except FileNotFoundError:
        st.error(f"❌ Script not found at: {script_path}")
    except Exception as e:
        st.error(f"❌ Failed to start script: {e}")


def main(online_count=0, local_count=0):
    """Main function to display the Lead Generation dashboard."""
    st.title("🎯 Lead Generation Hub")
    st.caption("Manage and monitor your daily lead generation activities.")

    # --- 7-Day Lead Generation Statistics ---
    display_weekly_stats()
    st.divider()

    # --- Today's Current Metrics ---
    st.subheader("📈 Today's Progress")
    display_metrics(online_count, local_count)
    st.divider()

    # --- Daily Actions ---
    st.header("Daily Actions")
    evening_col, morning_col = st.columns(2)

    with evening_col:
        st.subheader("🔍 Evening Routine")
        DAILY_LIMIT = 75
        online_remaining = max(0, DAILY_LIMIT - online_count)
        local_remaining = max(0, DAILY_LIMIT - local_count)

        # Status bar for today's follows
        st.info(
            f"🌱 Online: {online_count}/{DAILY_LIMIT} | 🏠 Local: {local_count}/{DAILY_LIMIT}")

        st.write("**Choose your lead generation mode:**")

        # LOCAL MODE BUTTON - cocos_pt_studio account
        col_local, col_online = st.columns(2)

        with col_local:
            st.write("**🏠 LOCAL MODE**")
            st.caption("Account: @cocos_pt_studio")
            st.caption("Target: Bayside gym clients")
            if st.button(
                f"🏠 Find Local Leads\n({local_remaining} remaining)",
                type="primary",
                disabled=(local_remaining <= 0),
                use_container_width=True,
                key="local_button"
            ):
                st.info("🚀 Starting LOCAL lead generation...")
                st.info("📱 Account: @cocos_pt_studio")
                st.info("🎯 Target: Bayside Melbourne gym clients")
                trigger_script(SINGLE_MODE_SCRIPT_PATH, "--mode", "local")

        with col_online:
            st.write("**🌱 ONLINE MODE**")
            st.caption("Account: @cocos_connected")
            st.caption("Target: Vegan/plant-based clients")
            if st.button(
                f"🌱 Find Vegan Leads\n({online_remaining} remaining)",
                type="secondary",
                disabled=(online_remaining <= 0),
                use_container_width=True,
                key="online_button"
            ):
                st.info("🚀 Starting ONLINE lead generation...")
                st.info("📱 Account: @cocos_connected")
                st.info("🎯 Target: Vegan/plant-based clients")
                trigger_script(SINGLE_MODE_SCRIPT_PATH, "--mode", "online")

    with morning_col:
        st.subheader("☀️ Follow-Back Processor")
        st.caption(
            "🔄 Comprehensive mode: Checks ALL unchecked users from the last 7 days (excluding today to give people time to follow back)")

        pending_count = get_pending_check_count()
        ready_count = get_ready_to_process_count()
        ready_for_analysis = get_users_ready_for_analysis()

        # Status bar for analysis queue (similar to evening routine format)
        st.info(
            f"🔍 Ready for Analysis (7 days): {ready_for_analysis} | ✅ Processed: {ready_count}")

        # Follow-back processor buttons for each account
        st.write("**Process Follow-Backs & Send DMs:**")

        col_check_local, col_check_online = st.columns(2)

        with col_check_local:
            if st.button(
                "🏠 Check Local\n(@cocos_pt_studio)",
                type="primary",
                use_container_width=True,
                key="check_local"
            ):
                st.info("🔍 Checking follow-backs for @cocos_pt_studio...")
                st.info(
                    "🔄 COMPREHENSIVE MODE: Checking ALL unchecked users from the last 7 days (excluding today)")
                st.info("🔄 Will unfollow those who didn't follow back")
                st.info("📊 Will analyze Instagram profiles for bio information")
                st.info("💬 Will send personalized DMs to those who followed back")
                trigger_script(
                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot\check_daily_follow_backs.py", "--account", "local", "--analyze-profiles")

        with col_check_online:
            if st.button(
                "🌱 Check Online\n(@cocos_connected)",
                type="secondary",
                use_container_width=True,
                key="check_online"
            ):
                st.info("🔍 Checking follow-backs for @cocos_connected...")
                st.info(
                    "🔄 COMPREHENSIVE MODE: Checking ALL unchecked users from the last 7 days (excluding today)")
                st.info("🔄 Will unfollow those who didn't follow back")
                st.info("📊 Will analyze Instagram profiles for bio information")
                st.info("💬 Will send personalized DMs to those who followed back")
                trigger_script(
                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot\check_daily_follow_backs.py", "--account", "online", "--analyze-profiles")

        st.divider()

        # Status info
        if pending_count > 0:
            st.info(
                f"📊 {pending_count} users pending follow-back check (from all dates)")
        else:
            st.success("✅ All recent follows have been checked!")

        if ready_count > 0:
            st.success(
                f"🎉 {ready_count} leads followed you back and are ready for outreach!")
        else:
            st.info("📭 No new follow-backs to process")

    st.divider()

    # Display follow-back check results
    display_followback_results()


if __name__ == "__main__":
    # This allows the file to be run standalone for testing if needed
    # In the main dashboard, the main() function is called with counts
    main()
