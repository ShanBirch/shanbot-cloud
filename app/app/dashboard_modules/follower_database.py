import streamlit as st
import sys
import os
import json
import datetime
import pandas as pd
from pathlib import Path

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the SQLite client analysis functions
try:
    from identify_potential_clients_sqlite import (
        get_all_followers_from_database,
        import_followers_from_file,
        add_follower_to_database,
        analyze_all_followers_for_coaching_sqlite,
        get_high_potential_clients_sqlite
    )
except ImportError:
    st.error("Could not import SQLite client analysis functions. Make sure identify_potential_clients_sqlite.py is in the correct location.")


def display_follower_database_tab(analytics_data_dict):
    """Display the Follower Database tab in the dashboard"""

    st.header("👥 Instagram Follower Database")
    st.markdown(
        "*Manage your complete Instagram follower database with analysis tracking and bulk operations.*")

    # Action buttons row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Refresh Database", help="Reload follower data from database"):
            st.rerun()

    with col2:
        if st.button("📥 Import Followers", help="Import followers from Instagram_followers.txt"):
            with st.spinner("Importing followers from file..."):
                try:
                    file_path = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\Instagram_followers.txt"
                    success = import_followers_from_file(file_path)
                    if success:
                        st.success(
                            "✅ Followers imported successfully! Refresh to see updates.")
                    else:
                        st.error(
                            "❌ Failed to import followers. Check the file path and format.")
                except Exception as e:
                    st.error(f"Error importing followers: {e}")

    with col3:
        if st.button("🧠 Run Analysis", help="Analyze followers for coaching potential"):
            with st.spinner("Running coaching potential analysis..."):
                try:
                    success = analyze_all_followers_for_coaching_sqlite()
                    if success:
                        st.success(
                            "✅ Analysis complete! Refresh to see updated scores.")
                    else:
                        st.error(
                            "❌ Analysis failed. Check the logs for details.")
                except Exception as e:
                    st.error(f"Error running analysis: {e}")

    with col4:
        export_data = st.button("📊 Export Database",
                                help="Export follower database to CSV")

    st.markdown("---")

    # Get follower data
    try:
        followers = get_all_followers_from_database()
    except Exception as e:
        st.error(f"Error loading follower database: {e}")
        followers = []

    if not followers:
        st.info(
            "No followers found in database. Use 'Import Followers' to add your Instagram followers.")
        return

    # Database statistics
    display_database_statistics(followers)

    # Filters section
    st.subheader("🔍 Filters & Search")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        # Search by username
        search_username = st.text_input(
            "Search Username",
            placeholder="Enter username to search...",
            help="Search for specific Instagram usernames"
        )

    with filter_col2:
        # Filter by analysis status
        analysis_filter = st.selectbox(
            "Analysis Status",
            ["All", "Has Instagram Analysis", "Has Coaching Analysis",
                "No Analysis", "High Potential (65+)"],
            help="Filter by analysis completion status"
        )

    with filter_col3:
        # Filter by client status
        status_filter = st.selectbox(
            "Client Status",
            ["All", "follower", "lead", "trial", "client", "unknown"],
            help="Filter by client status"
        )

    # Apply filters
    filtered_followers = apply_filters(
        followers, search_username, analysis_filter, status_filter)

    # Sort options
    sort_col1, sort_col2 = st.columns(2)

    with sort_col1:
        sort_by = st.selectbox(
            "Sort By",
            ["Coaching Score (High to Low)", "Coaching Score (Low to High)",
             "Username A-Z", "Username Z-A", "Last Interaction", "Join Date"],
            help="Choose how to sort the results"
        )

    with sort_col2:
        show_per_page = st.selectbox(
            "Show Per Page",
            [25, 50, 100, 200, "All"],
            index=1,
            help="Number of followers to display per page"
        )

    # Apply sorting
    sorted_followers = apply_sorting(filtered_followers, sort_by)

    # Pagination
    if show_per_page != "All":
        total_pages = (len(sorted_followers) +
                       show_per_page - 1) // show_per_page
        if total_pages > 1:
            page = st.selectbox(
                f"Page (1-{total_pages})", range(1, total_pages + 1))
            start_idx = (page - 1) * show_per_page
            end_idx = start_idx + show_per_page
            paginated_followers = sorted_followers[start_idx:end_idx]
        else:
            paginated_followers = sorted_followers
    else:
        paginated_followers = sorted_followers

    # Display results summary
    st.subheader(
        f"📋 Followers ({len(paginated_followers)} of {len(sorted_followers)} shown)")

    # Export functionality
    if export_data:
        export_follower_database(sorted_followers)

    # Bulk actions
    display_bulk_actions(paginated_followers)

    # Display follower table
    display_follower_table(paginated_followers)


def display_database_statistics(followers):
    """Display statistics about the follower database"""

    st.subheader("📊 Database Statistics")

    # Calculate statistics
    total_followers = len(followers)
    has_instagram_analysis = len(
        [f for f in followers if f['has_instagram_analysis']])
    has_coaching_analysis = len(
        [f for f in followers if f['has_coaching_analysis']])
    high_potential = len([f for f in followers if f['coaching_score'] >= 65])
    excellent_prospects = len(
        [f for f in followers if f['coaching_score'] >= 80])

    # Status breakdown
    status_counts = {}
    for follower in followers:
        status = follower['client_status']
        status_counts[status] = status_counts.get(status, 0) + 1

    # Display metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Followers", total_followers)

    with col2:
        st.metric("Instagram Analysis",
                  f"{has_instagram_analysis}/{total_followers}")

    with col3:
        st.metric("Coaching Analysis",
                  f"{has_coaching_analysis}/{total_followers}")

    with col4:
        st.metric("High Potential (65+)", high_potential)

    with col5:
        st.metric("Excellent Prospects (80+)", excellent_prospects)

    # Progress bars
    if total_followers > 0:
        instagram_progress = has_instagram_analysis / total_followers
        coaching_progress = has_coaching_analysis / total_followers

        st.write("**Analysis Progress:**")
        st.progress(instagram_progress,
                    text=f"Instagram Analysis: {instagram_progress:.1%}")
        st.progress(coaching_progress,
                    text=f"Coaching Analysis: {coaching_progress:.1%}")

    # Status breakdown chart
    if status_counts:
        st.write("**Client Status Breakdown:**")
        st.bar_chart(status_counts)

    st.markdown("---")


def apply_filters(followers, search_username, analysis_filter, status_filter):
    """Apply filters to the follower list"""

    filtered = followers.copy()

    # Search filter
    if search_username:
        filtered = [f for f in filtered if search_username.lower()
                    in f['ig_username'].lower()]

    # Analysis status filter
    if analysis_filter == "Has Instagram Analysis":
        filtered = [f for f in filtered if f['has_instagram_analysis']]
    elif analysis_filter == "Has Coaching Analysis":
        filtered = [f for f in filtered if f['has_coaching_analysis']]
    elif analysis_filter == "No Analysis":
        filtered = [f for f in filtered if not f['has_instagram_analysis']
                    and not f['has_coaching_analysis']]
    elif analysis_filter == "High Potential (65+)":
        filtered = [f for f in filtered if f['coaching_score'] >= 65]

    # Status filter
    if status_filter != "All":
        filtered = [f for f in filtered if f['client_status'] == status_filter]

    return filtered


def apply_sorting(followers, sort_by):
    """Apply sorting to the follower list"""

    if sort_by == "Coaching Score (High to Low)":
        return sorted(followers, key=lambda x: x['coaching_score'], reverse=True)
    elif sort_by == "Coaching Score (Low to High)":
        return sorted(followers, key=lambda x: x['coaching_score'])
    elif sort_by == "Username A-Z":
        return sorted(followers, key=lambda x: x['ig_username'].lower())
    elif sort_by == "Username Z-A":
        return sorted(followers, key=lambda x: x['ig_username'].lower(), reverse=True)
    elif sort_by == "Last Interaction":
        return sorted(followers, key=lambda x: x['last_interaction'] or '', reverse=True)
    elif sort_by == "Join Date":
        return sorted(followers, key=lambda x: x['joined_date'] or '', reverse=True)
    else:
        return followers


def display_bulk_actions(followers):
    """Display bulk action options"""

    st.subheader("⚡ Bulk Actions")

    bulk_col1, bulk_col2, bulk_col3 = st.columns(3)

    with bulk_col1:
        if st.button("📊 Analyze Selected for Instagram", help="Run Instagram analysis on followers without it"):
            unanalyzed = [
                f for f in followers if not f['has_instagram_analysis']]
            if unanalyzed:
                st.info(
                    f"Found {len(unanalyzed)} followers without Instagram analysis. Use the main analyze_followers.py script to analyze them.")
            else:
                st.success(
                    "All displayed followers already have Instagram analysis!")

    with bulk_col2:
        if st.button("🧠 Analyze Selected for Coaching", help="Run coaching analysis on followers with Instagram data"):
            ready_for_coaching = [
                f for f in followers if f['has_instagram_analysis'] and not f['has_coaching_analysis']]
            if ready_for_coaching:
                st.info(
                    f"Found {len(ready_for_coaching)} followers ready for coaching analysis. Use 'Run Analysis' button above.")
            else:
                st.success(
                    "All eligible followers already have coaching analysis!")

    with bulk_col3:
        if st.button("📋 Export Selected", help="Export the currently filtered followers"):
            if followers:
                export_follower_database(followers)
            else:
                st.warning("No followers to export!")


def display_follower_table(followers):
    """Display the follower table with detailed information"""

    if not followers:
        st.info("No followers match the current filters.")
        return

    # Create DataFrame for display
    display_data = []
    for follower in followers:
        row = {
            'Username': f"@{follower['ig_username']}",
            'Name': f"{follower['first_name']} {follower['last_name']}".strip() or "—",
            'Status': follower['client_status'].title(),
            'Messages': follower['total_messages'],
            'IG Analysis': "✅" if follower['has_instagram_analysis'] else "❌",
            'Coaching Analysis': "✅" if follower['has_coaching_analysis'] else "❌",
            'Coaching Score': follower['coaching_score'] if follower['coaching_score'] > 0 else "—",
            'Last Interaction': format_date(follower['last_interaction']),
            'Joined': format_date(follower['joined_date'])
        }
        display_data.append(row)

    # Display as DataFrame
    df = pd.DataFrame(display_data)

    # Style the DataFrame
    def style_score(val):
        if val == "—":
            return ""
        score = int(val)
        if score >= 80:
            return "background-color: #d4edda; color: #155724"  # Green
        elif score >= 65:
            return "background-color: #fff3cd; color: #856404"  # Yellow
        elif score >= 50:
            return "background-color: #cce5ff; color: #004085"  # Blue
        else:
            return "background-color: #f8d7da; color: #721c24"  # Red

    def style_analysis(val):
        if val == "✅":
            return "color: green"
        else:
            return "color: red"

    # Apply styling
    styled_df = df.style.applymap(style_score, subset=['Coaching Score'])
    styled_df = styled_df.applymap(style_analysis, subset=[
                                   'IG Analysis', 'Coaching Analysis'])

    st.dataframe(styled_df, use_container_width=True, height=600)

    # Individual follower details
    st.subheader("🔍 Follower Details")

    # Select follower for detailed view
    usernames = [f['ig_username'] for f in followers]
    selected_username = st.selectbox(
        "Select follower for detailed view:",
        [""] + usernames,
        help="Choose a follower to see detailed information"
    )

    if selected_username:
        selected_follower = next(
            (f for f in followers if f['ig_username'] == selected_username), None)
        if selected_follower:
            display_follower_details(selected_follower)


def display_follower_details(follower):
    """Display detailed information for a selected follower"""

    with st.expander(f"📋 Details for @{follower['ig_username']}", expanded=True):

        # Basic info
        detail_col1, detail_col2, detail_col3 = st.columns(3)

        with detail_col1:
            st.write("**Basic Information:**")
            st.write(f"Username: @{follower['ig_username']}")
            st.write(f"Name: {follower['first_name']} {follower['last_name']}".strip(
            ) or "Not provided")
            st.write(f"Status: {follower['client_status'].title()}")

        with detail_col2:
            st.write("**Activity:**")
            st.write(f"Total Messages: {follower['total_messages']}")
            st.write(
                f"Last Interaction: {format_date(follower['last_interaction'])}")
            st.write(f"Joined: {format_date(follower['joined_date'])}")

        with detail_col3:
            st.write("**Analysis Status:**")
            st.write(
                f"Instagram Analysis: {'✅ Complete' if follower['has_instagram_analysis'] else '❌ Pending'}")
            st.write(
                f"Coaching Analysis: {'✅ Complete' if follower['has_coaching_analysis'] else '❌ Pending'}")
            if follower['coaching_score'] > 0:
                st.write(f"Coaching Score: {follower['coaching_score']}/100")

        # Action buttons for individual follower
        action_col1, action_col2, action_col3 = st.columns(3)

        with action_col1:
            if st.button(f"🔗 View Instagram", key=f"view_{follower['ig_username']}"):
                instagram_url = f"https://instagram.com/{follower['ig_username']}"
                st.markdown(f"[Open Instagram Profile]({instagram_url})")

        with action_col2:
            if st.button(f"📋 Copy Username", key=f"copy_{follower['ig_username']}"):
                st.code(f"@{follower['ig_username']}")
                st.success("Username ready to copy!")

        with action_col3:
            if follower['has_coaching_analysis'] and follower['coaching_score'] >= 50:
                if st.button(f"🌟 View as Prospect", key=f"prospect_{follower['ig_username']}"):
                    st.info(
                        "Switch to 'High-Potential Clients' tab to see full coaching analysis!")


def format_date(date_string):
    """Format date string for display"""
    if not date_string:
        return "—"

    try:
        # Try to parse ISO format
        date_obj = datetime.datetime.fromisoformat(date_string.split('+')[0])
        return date_obj.strftime("%Y-%m-%d")
    except:
        return date_string


def export_follower_database(followers):
    """Export follower database to CSV"""
    try:
        # Prepare data for export
        export_data = []
        for follower in followers:
            row = {
                'ig_username': follower['ig_username'],
                'first_name': follower['first_name'],
                'last_name': follower['last_name'],
                'client_status': follower['client_status'],
                'total_messages': follower['total_messages'],
                'has_instagram_analysis': follower['has_instagram_analysis'],
                'has_coaching_analysis': follower['has_coaching_analysis'],
                'coaching_score': follower['coaching_score'],
                'last_interaction': follower['last_interaction'],
                'joined_date': follower['joined_date']
            }
            export_data.append(row)

        # Create DataFrame and CSV
        df = pd.DataFrame(export_data)
        csv = df.to_csv(index=False)

        # Provide download button
        st.download_button(
            label="📥 Download Follower Database CSV",
            data=csv,
            file_name=f"follower_database_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        st.success(f"✅ CSV prepared with {len(followers)} followers!")

    except Exception as e:
        st.error(f"Error exporting follower database: {e}")


def add_manual_follower():
    """Add a follower manually to the database"""

    st.subheader("➕ Add Follower Manually")

    with st.form("add_follower_form"):
        col1, col2 = st.columns(2)

        with col1:
            username = st.text_input(
                "Instagram Username", placeholder="username (without @)")
            first_name = st.text_input("First Name (optional)")

        with col2:
            last_name = st.text_input("Last Name (optional)")
            status = st.selectbox(
                "Status", ["follower", "lead", "trial", "client"])

        submitted = st.form_submit_button("Add Follower")

        if submitted:
            if username:
                follower_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'client_status': status
                }

                try:
                    success = add_follower_to_database(username, follower_data)
                    if success:
                        st.success(f"✅ Added @{username} to the database!")
                        st.rerun()
                    else:
                        st.error(
                            "❌ Failed to add follower. They may already exist.")
                except Exception as e:
                    st.error(f"Error adding follower: {e}")
            else:
                st.error("Please enter a username.")

# Add this to the main display function


def display_follower_database_tab_with_manual_add(analytics_data_dict):
    """Enhanced version with manual add functionality"""

    # Main database display
    display_follower_database_tab(analytics_data_dict)

    # Manual add section
    st.markdown("---")
    add_manual_follower()
