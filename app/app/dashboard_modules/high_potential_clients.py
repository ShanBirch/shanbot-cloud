import streamlit as st
import sys
import os
import json
import datetime
from pathlib import Path

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the client analysis functions
try:
    from identify_potential_clients_sqlite import (
        get_high_potential_clients_sqlite as get_high_potential_clients,
        get_coaching_potential_category,
        generate_coaching_outreach_message,
        analyze_all_followers_for_coaching_sqlite as analyze_all_followers_for_coaching
    )
except ImportError:
    st.error("Could not import client analysis functions. Make sure identify_potential_clients.py is in the correct location.")


def display_high_potential_clients_tab(analytics_data_dict):
    """Display the High-Potential Clients tab in the dashboard"""

    st.header("🌱 High-Potential Vegetarian/Vegan Fitness Clients")
    st.markdown("*Identify and engage with followers who are most likely to be interested in your vegetarian fitness coaching program.*")

    # Action buttons row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Refresh Analysis", help="Reload high-potential clients data"):
            st.rerun()

    with col2:
        if st.button("🧠 Run New Analysis", help="Analyze followers for coaching potential"):
            with st.spinner("Analyzing followers for coaching potential..."):
                try:
                    success = analyze_all_followers_for_coaching()
                    if success:
                        st.success(
                            "✅ Analysis complete! Refresh to see updated results.")
                    else:
                        st.error(
                            "❌ Analysis failed. Check the logs for details.")
                except Exception as e:
                    st.error(f"Error running analysis: {e}")

    with col3:
        export_data = st.button(
            "📊 Export Data", help="Export high-potential clients to CSV")

    with col4:
        show_stats = st.button("📈 Show Statistics",
                               help="Display analysis statistics")

    st.markdown("---")

    # Filters section
    st.subheader("🔍 Filters")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        min_score = st.slider(
            "Minimum Coaching Score",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
            help="Filter clients by their coaching potential score"
        )

    with filter_col2:
        category_filter = st.selectbox(
            "Category Filter",
            ["All Categories", "🌟 Excellent Prospect", "🔥 High Potential",
                "⭐ Good Potential", "💡 Some Potential"],
            help="Filter by coaching potential category"
        )

    with filter_col3:
        sort_by = st.selectbox(
            "Sort By",
            ["Score (High to Low)", "Score (Low to High)",
             "Username A-Z", "Username Z-A", "Recent Activity"],
            help="Choose how to sort the results"
        )

    # Get high-potential clients
    try:
        high_potential_clients = get_high_potential_clients(
            min_score=min_score)

        # Apply category filter
        if category_filter != "All Categories":
            high_potential_clients = [
                client for client in high_potential_clients
                if client['category'] == category_filter
            ]

        # Apply sorting
        if sort_by == "Score (High to Low)":
            high_potential_clients.sort(key=lambda x: x['score'], reverse=True)
        elif sort_by == "Score (Low to High)":
            high_potential_clients.sort(key=lambda x: x['score'])
        elif sort_by == "Username A-Z":
            high_potential_clients.sort(key=lambda x: x['username'].lower())
        elif sort_by == "Username Z-A":
            high_potential_clients.sort(
                key=lambda x: x['username'].lower(), reverse=True)
        elif sort_by == "Recent Activity":
            high_potential_clients.sort(
                key=lambda x: x.get('last_interaction', ''),
                reverse=True
            )

    except Exception as e:
        st.error(f"Error loading high-potential clients: {e}")
        high_potential_clients = []

    # Display statistics
    if show_stats and high_potential_clients:
        display_client_statistics(high_potential_clients)

    # Display results summary
    st.subheader(f"📋 Results ({len(high_potential_clients)} clients)")

    if not high_potential_clients:
        st.info("No high-potential clients found with the current filters. Try lowering the minimum score or running a new analysis.")
        return

    # Export functionality
    if export_data:
        export_clients_to_csv(high_potential_clients)

    # Display clients
    for i, client in enumerate(high_potential_clients):
        display_client_card(client, i)


def display_client_statistics(clients):
    """Display statistics about the high-potential clients"""

    st.subheader("📊 Analysis Statistics")

    # Calculate statistics
    total_clients = len(clients)
    avg_score = sum(client['score'] for client in clients) / \
        total_clients if total_clients > 0 else 0

    # Category breakdown
    category_counts = {}
    for client in clients:
        category = client['category']
        category_counts[category] = category_counts.get(category, 0) + 1

    # Score distribution
    score_ranges = {
        "80-100": len([c for c in clients if c['score'] >= 80]),
        "65-79": len([c for c in clients if 65 <= c['score'] < 80]),
        "50-64": len([c for c in clients if 50 <= c['score'] < 65]),
        "35-49": len([c for c in clients if 35 <= c['score'] < 50]),
        "0-34": len([c for c in clients if c['score'] < 35])
    }

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Clients", total_clients)

    with col2:
        st.metric("Average Score", f"{avg_score:.1f}")

    with col3:
        excellent_count = category_counts.get("🌟 Excellent Prospect", 0)
        st.metric("Excellent Prospects", excellent_count)

    with col4:
        high_count = category_counts.get("🔥 High Potential", 0)
        st.metric("High Potential", high_count)

    # Category breakdown chart
    st.subheader("Category Breakdown")
    if category_counts:
        st.bar_chart(category_counts)

    # Score distribution
    st.subheader("Score Distribution")
    if score_ranges:
        st.bar_chart(score_ranges)

    st.markdown("---")


def display_client_card(client, index):
    """Display an individual client card with all relevant information"""

    # Create expandable card
    with st.expander(
        f"{client['category']} | @{client['username']} | Score: {client['score']}/100",
        expanded=False
    ):

        # Basic info row
        info_col1, info_col2, info_col3 = st.columns(3)

        with info_col1:
            st.write(f"**Username:** @{client['username']}")
            st.write(
                f"**IG Username:** @{client.get('ig_username', client['username'])}")

        with info_col2:
            st.write(f"**Score:** {client['score']}/100")
            st.write(f"**Category:** {client['category']}")

        with info_col3:
            last_interaction = client.get('last_interaction')
            if last_interaction:
                try:
                    date_obj = datetime.datetime.fromisoformat(
                        last_interaction.split('+')[0])
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                    st.write(f"**Last Interaction:** {formatted_date}")
                except:
                    st.write(f"**Last Interaction:** {last_interaction}")
            else:
                st.write("**Last Interaction:** Not available")

        # Coaching analysis details
        coaching_analysis = client.get('coaching_analysis', {})

        if coaching_analysis:
            st.subheader("🧠 Coaching Analysis")

            # Analysis details in tabs
            analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs(
                ["🌱 Vegan/Vegetarian", "💪 Fitness", "📊 Full Analysis"])

            with analysis_tab1:
                vegan_indicators = coaching_analysis.get(
                    'vegetarian_vegan_indicators', 'No specific indicators found')
                st.write("**Vegetarian/Vegan Indicators:**")
                st.write(vegan_indicators)

            with analysis_tab2:
                fitness_indicators = coaching_analysis.get(
                    'fitness_health_indicators', 'No specific indicators found')
                st.write("**Fitness/Health Indicators:**")
                st.write(fitness_indicators)

            with analysis_tab3:
                st.write("**Lifestyle Alignment:**")
                st.write(coaching_analysis.get(
                    'lifestyle_alignment', 'Not available'))

                st.write("**Engagement Potential:**")
                st.write(coaching_analysis.get(
                    'engagement_potential', 'Not available'))

                st.write("**Demographic Fit:**")
                st.write(coaching_analysis.get(
                    'demographic_fit', 'Not available'))

                st.write("**Reasoning:**")
                st.write(coaching_analysis.get('reasoning', 'Not available'))

        # Profile information
        st.subheader("👤 Profile Information")

        profile_col1, profile_col2 = st.columns(2)

        with profile_col1:
            interests = client.get('interests', [])
            if interests:
                st.write("**Interests:**")
                for interest in interests[:5]:  # Show top 5
                    st.write(f"• {interest}")
                if len(interests) > 5:
                    st.write(f"... and {len(interests) - 5} more")
            else:
                st.write("**Interests:** Not available")

        with profile_col2:
            activities = client.get('recent_activities', [])
            if activities:
                st.write("**Recent Activities:**")
                for activity in activities[:5]:  # Show top 5
                    st.write(f"• {activity}")
                if len(activities) > 5:
                    st.write(f"... and {len(activities) - 5} more")
            else:
                st.write("**Recent Activities:** Not available")

        # Conversation starters
        conversation_starters = coaching_analysis.get(
            'conversation_starters', [])
        if conversation_starters:
            st.subheader("💬 Conversation Starters")
            for i, starter in enumerate(conversation_starters, 1):
                st.write(f"{i}. {starter}")

        # Action buttons
        st.subheader("🎯 Actions")

        action_col1, action_col2, action_col3 = st.columns(3)

        with action_col1:
            if st.button(f"📱 Generate Outreach Message", key=f"outreach_{index}"):
                with st.spinner("Generating personalized message..."):
                    try:
                        message = generate_coaching_outreach_message(client)
                        st.success("✅ Message generated!")
                        st.text_area(
                            "Personalized Outreach Message:",
                            value=message,
                            height=150,
                            key=f"message_{index}"
                        )
                    except Exception as e:
                        st.error(f"Error generating message: {e}")

        with action_col2:
            if st.button(f"📋 Copy Username", key=f"copy_{index}"):
                st.code(f"@{client['username']}")
                st.success("Username ready to copy!")

        with action_col3:
            if st.button(f"🔗 View Instagram", key=f"instagram_{index}"):
                instagram_url = f"https://instagram.com/{client['username']}"
                st.markdown(f"[Open Instagram Profile]({instagram_url})")

        st.markdown("---")


def export_clients_to_csv(clients):
    """Export high-potential clients data to CSV"""
    try:
        import pandas as pd

        # Prepare data for export
        export_data = []
        for client in clients:
            coaching_analysis = client.get('coaching_analysis', {})

            row = {
                'Username': client['username'],
                'IG_Username': client.get('ig_username', client['username']),
                'Score': client['score'],
                'Category': client['category'],
                'Last_Interaction': client.get('last_interaction', ''),
                'Interests': ', '.join(client.get('interests', [])),
                'Recent_Activities': ', '.join(client.get('recent_activities', [])),
                'Vegan_Vegetarian_Indicators': coaching_analysis.get('vegetarian_vegan_indicators', ''),
                'Fitness_Health_Indicators': coaching_analysis.get('fitness_health_indicators', ''),
                'Lifestyle_Alignment': coaching_analysis.get('lifestyle_alignment', ''),
                'Engagement_Potential': coaching_analysis.get('engagement_potential', ''),
                'Demographic_Fit': coaching_analysis.get('demographic_fit', ''),
                'Reasoning': coaching_analysis.get('reasoning', ''),
                'Conversation_Starters': ' | '.join(coaching_analysis.get('conversation_starters', []))
            }
            export_data.append(row)

        # Create DataFrame and CSV
        df = pd.DataFrame(export_data)
        csv = df.to_csv(index=False)

        # Provide download button
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"high_potential_clients_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        st.success(f"✅ CSV prepared with {len(clients)} clients!")

    except ImportError:
        st.error(
            "pandas is required for CSV export. Please install it: pip install pandas")
    except Exception as e:
        st.error(f"Error exporting to CSV: {e}")


def get_client_summary_stats(analytics_data_dict):
    """Get summary statistics for the high-potential clients overview"""
    try:
        all_clients = get_high_potential_clients(
            min_score=0)  # Get all analyzed clients

        stats = {
            'total_analyzed': len(all_clients),
            'excellent_prospects': len([c for c in all_clients if c['score'] >= 80]),
            'high_potential': len([c for c in all_clients if 65 <= c['score'] < 80]),
            'good_potential': len([c for c in all_clients if 50 <= c['score'] < 65]),
            'avg_score': sum(c['score'] for c in all_clients) / len(all_clients) if all_clients else 0
        }

        return stats

    except Exception as e:
        return {
            'total_analyzed': 0,
            'excellent_prospects': 0,
            'high_potential': 0,
            'good_potential': 0,
            'avg_score': 0
        }
