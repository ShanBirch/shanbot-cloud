import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import re
from typing import Dict, List, Tuple, Optional

# Database path
DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def get_ads_analytics_data(days: int = 7) -> Dict:
    """Get ads analytics data for the specified time period."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get FIRST messages that trigger the paid_plant_based_challenge tag
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT m.ig_username, MIN(m.timestamp) as first_message_time
                FROM messages m
                JOIN users u ON m.ig_username = u.ig_username
                WHERE m.timestamp >= ? AND m.timestamp <= ?
                AND u.lead_source = 'paid_plant_based_challenge'
                AND m.sender = 'user'  -- Only count user messages, not AI responses
                GROUP BY m.ig_username
            ) first_messages
        """, (start_date.isoformat(), end_date.isoformat()))
        messages_result = cursor.fetchone()
        messages_received = messages_result[0] if messages_result else 0

        # Get Calendly links sent
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE text LIKE '%calendly.com/shannonrhysbirch/15min%'
            AND timestamp >= ? AND timestamp <= ?
        """, (start_date.isoformat(), end_date.isoformat()))
        links_result = cursor.fetchone()
        links_sent = links_result[0] if links_result else 0

        # Get booking confirmations from Calendly integration
        cursor.execute("""
            SELECT COUNT(*) FROM calendly_bookings 
            WHERE created_at >= ? AND created_at <= ?
        """, (start_date.isoformat(), end_date.isoformat()))
        calls_result = cursor.fetchone()
        calls_booked = calls_result[0] if calls_result else 0

        # Get manual entries from ads_analytics table
        cursor.execute("""
            SELECT 
                COALESCE(SUM(paying_clients_count), 0) as paying_clients,
                COALESCE(SUM(revenue_amount), 0) as revenue
            FROM ads_analytics 
            WHERE date >= ? AND date <= ?
        """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        manual_data = cursor.fetchone()
        paying_clients = manual_data[0] if manual_data else 0
        revenue = manual_data[1] if manual_data else 0.0

        # Get weekly ad spend
        cursor.execute("""
            SELECT setting_value FROM ads_settings 
            WHERE setting_name = 'weekly_ad_spend'
        """)
        weekly_ad_spend_result = cursor.fetchone()
        weekly_ad_spend = weekly_ad_spend_result[0] if weekly_ad_spend_result else 0.0

        conn.close()

        return {
            'messages_received': messages_received,
            'links_sent': links_sent,
            'calls_booked': calls_booked,
            'paying_clients': paying_clients,
            'revenue': revenue,
            'weekly_ad_spend': weekly_ad_spend,
            'roi_percentage': ((revenue - weekly_ad_spend) / weekly_ad_spend * 100) if weekly_ad_spend > 0 else 0
        }
    except Exception as e:
        st.error(f"Error getting ads analytics data: {e}")
        # Return default values if there's an error
        return {
            'messages_received': 0,
            'links_sent': 0,
            'calls_booked': 0,
            'paying_clients': 0,
            'revenue': 0.0,
            'weekly_ad_spend': 0.0,
            'roi_percentage': 0.0
        }


def update_weekly_ad_spend(new_spend: float) -> bool:
    """Update the weekly ad spend setting."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE ads_settings 
            SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE setting_name = 'weekly_ad_spend'
        """, (new_spend,))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating ad spend: {e}")
        return False


def get_all_leads() -> List[Dict]:
    """Get all leads from the database for selection."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all users with their conversation history
        cursor.execute("""
            SELECT DISTINCT u.ig_username, u.first_name, u.last_name, u.bio,
                   COUNT(m.id) as message_count,
                   MAX(m.timestamp) as last_message_date
            FROM users u
            LEFT JOIN messages m ON u.ig_username = m.ig_username
            WHERE u.ig_username IS NOT NULL AND u.ig_username != ''
            GROUP BY u.ig_username
            ORDER BY last_message_date DESC
        """)

        leads = []
        for row in cursor.fetchall():
            ig_username, first_name, last_name, bio, message_count, last_message_date = row
            display_name = f"@{ig_username}"
            if first_name:
                display_name = f"{first_name} (@{ig_username})"

            leads.append({
                'ig_username': ig_username,
                'display_name': display_name,
                'first_name': first_name,
                'last_name': last_name,
                'bio': bio,
                'message_count': message_count,
                'last_message_date': last_message_date
            })

        conn.close()
        return leads
    except Exception as e:
        st.error(f"Error getting leads: {e}")
        return []


def add_manual_entry(date: str, paying_clients: int, revenue: float, notes: str = "", selected_leads: List[str] = None) -> bool:
    """Add a manual entry to the ads analytics table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create paying_clients table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paying_clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT,
                ig_username TEXT,
                revenue_amount REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ig_username) REFERENCES users (ig_username)
            )
        """)

        # Insert the main analytics entry
        cursor.execute("""
            INSERT INTO ads_analytics (date, paying_clients_count, revenue_amount, notes)
            VALUES (?, ?, ?, ?)
        """, (date, paying_clients, revenue, notes))

        # Insert individual paying client records if leads were selected
        if selected_leads:
            for ig_username in selected_leads:
                cursor.execute("""
                    INSERT INTO paying_clients (entry_date, ig_username, revenue_amount, notes)
                    VALUES (?, ?, ?, ?)
                """, (date, ig_username, revenue / paying_clients if paying_clients > 0 else 0, notes))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error adding manual entry: {e}")
        return False


def get_ads_history(days: int = 30) -> pd.DataFrame:
    """Get ads analytics history for charts."""
    conn = get_db_connection()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    query = """
        SELECT 
            date,
            paying_clients_count,
            revenue_amount,
            weekly_ad_spend,
            notes
        FROM ads_analytics 
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    """

    df = pd.read_sql_query(query, conn, params=(
        start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    conn.close()

    return df


def get_paying_clients_history(days: int = 30) -> pd.DataFrame:
    """Get paying clients history with lead details."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        query = """
            SELECT 
                pc.entry_date,
                pc.ig_username,
                pc.revenue_amount,
                pc.notes,
                u.first_name,
                u.last_name,
                u.bio
            FROM paying_clients pc
            LEFT JOIN users u ON pc.ig_username = u.ig_username
            WHERE pc.entry_date >= ? AND pc.entry_date <= ?
            ORDER BY pc.entry_date DESC, pc.ig_username
        """

        df = pd.read_sql_query(query, conn, params=(
            start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        conn.close()

        return df
    except Exception as e:
        st.error(f"Error getting paying clients history: {e}")
        return pd.DataFrame()


def display_ads_analytics():
    """Display the main ads analytics dashboard."""
    st.title("📊 Ads Analytics Dashboard")

    # Time period selector
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        time_period = st.selectbox(
            "Time Period",
            ["Daily", "Weekly", "Monthly"],
            index=1  # Default to Weekly
        )

    with col2:
        days_map = {"Daily": 1, "Weekly": 7, "Monthly": 30}
        days = days_map[time_period]

    # Get analytics data
    data = get_ads_analytics_data(days)

    # Display statistics cards
    st.subheader("📈 Key Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Messages Received",
            value=data['messages_received'],
            delta=None
        )

    with col2:
        st.metric(
            label="Links Sent",
            value=data['links_sent'],
            delta=None
        )

    with col3:
        st.metric(
            label="Calls Booked",
            value=data['calls_booked'],
            delta=None
        )

    with col4:
        st.metric(
            label="Paying Clients",
            value=data['paying_clients'],
            delta=None
        )

    # Revenue and ROI section
    st.subheader("💰 Revenue & ROI")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Revenue",
            value=f"${data['revenue']:.2f}",
            delta=None
        )

    with col2:
        st.metric(
            label="Weekly Ad Spend",
            value=f"${data['weekly_ad_spend']:.2f}",
            delta=None
        )

    with col3:
        roi_color = "normal" if data['roi_percentage'] >= 0 else "inverse"
        st.metric(
            label="ROI %",
            value=f"{data['roi_percentage']:.1f}%",
            delta=None
        )

    # Manual entry section
    st.subheader("📝 Manual Entry")

    with st.expander("Add Manual Entry", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            entry_date = st.date_input("Date", value=datetime.now())
            revenue = st.number_input(
                "Revenue ($)", min_value=0.0, value=0.0, step=0.01)

        with col2:
            notes = st.text_input("Notes (optional)")

        # Lead selection section
        st.subheader("👥 Select Paying Clients")

        # Get all leads from database
        leads = get_all_leads()

        if leads:
            st.write(f"Found {len(leads)} leads in your database")

            # Create a multiselect for lead selection
            lead_options = {lead['display_name']                            : lead['ig_username'] for lead in leads}
            selected_lead_names = st.multiselect(
                "Select which leads became paying clients:",
                options=list(lead_options.keys()),
                help="Select the leads who converted to paying clients. The paying clients count will be automatically set based on your selection."
            )

            # Calculate paying clients count from selection
            paying_clients = len(selected_lead_names)
            selected_lead_usernames = [lead_options[name]
                                       for name in selected_lead_names]

            # Display selected leads
            if selected_lead_names:
                st.write(f"**Selected {paying_clients} paying client(s):**")
                for name in selected_lead_names:
                    st.write(f"• {name}")
        else:
            st.warning(
                "No leads found in database. You can still add manual entries.")
            paying_clients = st.number_input(
                "Paying Clients", min_value=0, value=0)
            selected_lead_usernames = []

        if st.button("Add Entry"):
            if add_manual_entry(entry_date.strftime('%Y-%m-%d'), paying_clients, revenue, notes, selected_lead_usernames):
                st.success("Entry added successfully!")
                st.rerun()

    # Weekly ad spend editor
    st.subheader("⚙️ Settings")

    with st.expander("Edit Weekly Ad Spend", expanded=False):
        current_spend = data['weekly_ad_spend']
        new_spend = st.number_input(
            "Weekly Ad Spend ($)",
            min_value=0.0,
            value=float(current_spend),
            step=0.01
        )

        if st.button("Update Ad Spend"):
            if update_weekly_ad_spend(new_spend):
                st.success("Ad spend updated successfully!")
                st.rerun()

    # Charts section
    st.subheader("📊 Historical Data")

    try:
        history_df = get_ads_history(30)  # Last 30 days

        if not history_df.empty:
            # Revenue chart
            st.line_chart(history_df.set_index('date')['revenue_amount'])
            st.caption("Revenue over time")

            # Paying clients chart
            st.line_chart(history_df.set_index('date')['paying_clients_count'])
            st.caption("Paying clients over time")

            # Display recent entries
            st.subheader("📋 Recent Entries")
            st.dataframe(history_df.head(10))
        else:
            st.info(
                "No historical data available yet. Add some manual entries to see charts!")

    except Exception as e:
        st.error(f"Error loading charts: {e}")

    # Recent bookings section
    st.subheader("📅 Recent Bookings")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT invitee_name, invitee_email, booking_time, created_at
            FROM calendly_bookings 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        bookings = cursor.fetchall()
        conn.close()

        if bookings:
            booking_data = []
            for booking in bookings:
                booking_data.append({
                    'Name': booking[0] if booking[0] != 'Unknown' else 'N/A',
                    'Email': booking[1] if booking[1] else 'N/A',
                    'Booking Time': booking[2][:19] if booking[2] else 'N/A',
                    'Detected': booking[3][:19] if booking[3] else 'N/A'
                })

            import pandas as pd
            bookings_df = pd.DataFrame(booking_data)
            st.dataframe(bookings_df)
        else:
            st.info("No recent bookings found")

    except Exception as e:
        st.error(f"Error loading bookings: {e}")

    # Paying Clients History
    st.subheader("💰 Paying Clients History")

    try:
        paying_clients_df = get_paying_clients_history(30)

        if not paying_clients_df.empty:
            # Display the paying clients table
            st.dataframe(
                paying_clients_df,
                column_config={
                    "entry_date": "Date",
                    "ig_username": "Instagram Username",
                    "revenue_amount": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                    "first_name": "First Name",
                    "last_name": "Last Name",
                    "bio": "Bio"
                },
                hide_index=True
            )

            # Summary stats
            total_revenue = paying_clients_df['revenue_amount'].sum()
            total_clients = len(paying_clients_df)
            st.write(
                f"**Total Revenue from Paying Clients: ${total_revenue:.2f}**")
            st.write(f"**Total Paying Clients: {total_clients}**")
        else:
            st.info(
                "No paying clients history found. Add some manual entries to see this data!")

    except Exception as e:
        st.error(f"Error loading paying clients history: {e}")

    # Export functionality
    st.subheader("📤 Export Data")

    if st.button("Export to CSV"):
        try:
            history_df = get_ads_history(365)  # Last year
            csv = history_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"ads_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        except Exception as e:
            st.error(f"Error exporting data: {e}")


if __name__ == "__main__":
    display_ads_analytics()
