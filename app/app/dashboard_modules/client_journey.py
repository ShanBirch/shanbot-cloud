import streamlit as st
from typing import Dict, Any


def get_stage_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate metrics for each stage of the client journey"""
    try:
        conversations = data.get('conversations', {})
        metrics = {
            'total_users': len(conversations),
            'engaged_users': 0,
            'analyzed_profiles': 0,
            'total_messages': 0,
            'response_rate': 0,
            'avg_messages': 0
        }

        analyzed_users = 0
        total_analyzed_posts = 0

        for username, user_data in conversations.items():
            user_metrics = user_data.get('metrics', {})
            client_analysis = user_metrics.get('client_analysis', {})

            if client_analysis and client_analysis.get('posts_analyzed', 0) > 0:
                analyzed_users += 1
                total_analyzed_posts += client_analysis.get(
                    'posts_analyzed', 0)

            if user_metrics.get('user_messages', 0) > 0:
                metrics['engaged_users'] += 1
                metrics['total_messages'] += user_metrics.get(
                    'total_messages', 0)

        if metrics['engaged_users'] > 0:
            metrics['avg_messages'] = metrics['total_messages'] / \
                metrics['engaged_users']
            metrics['response_rate'] = (
                metrics['engaged_users'] / metrics['total_users']) * 100

        metrics['analyzed_profiles'] = analyzed_users
        metrics['avg_posts_per_profile'] = total_analyzed_posts / \
            analyzed_users if analyzed_users > 0 else 0

        return metrics
    except Exception as e:
        st.error(f"Error calculating stage metrics: {e}")
        return metrics


def get_users_in_stage(analytics_data: Dict[str, Any], stage: str) -> int:
    """Count how many users are in a specific stage"""
    count = 0
    # To avoid double counting if user exists at top-level and under 'conversations'
    processed_usernames = set()

    if not isinstance(analytics_data, dict):
        st.error("Analytics data is not a dictionary. Cannot process stages.")
        return 0

    # Define known top-level keys that are not individual user entries
    known_non_user_keys = ["conversations",
                           "action_items", "conversation_history"]

    # Helper function to process a user entry
    def _process_user_for_stage(username, user_data_item, current_stage):
        nonlocal count  # Allow modification of count from outer scope
        if not isinstance(user_data_item, dict):
            # Specifically avoid warning for 'conversation_history' if it's a list, as it's a known non-user data structure
            if username == "conversation_history" and isinstance(user_data_item, list):
                return False  # Silently skip for stage counting
            st.warning(
                f"User data for '{username}' is not a dictionary (type: {type(user_data_item)}). Skipping for stage counting.")
            return False  # Indicates failure to process

        metrics = user_data_item.get('metrics', {})
        if not isinstance(metrics, dict):
            st.warning(
                f"Metrics for user '{username}' is not a dictionary (type: {type(metrics)}). Skipping for stage counting.")
            return False  # Indicates failure to process

        if current_stage == "Topic 5" and metrics.get('trial_offer_made'):
            count += 1
        elif current_stage == "Topic 4" and metrics.get('topic4_completed'):
            count += 1
        elif current_stage == "Topic 3" and metrics.get('topic3_completed'):
            count += 1
        elif current_stage == "Topic 2" and metrics.get('topic2_completed'):
            count += 1
        elif current_stage == "Topic 1" and not any([
            metrics.get('topic2_completed'),
            metrics.get('topic3_completed'),
            metrics.get('topic4_completed'),
            metrics.get('trial_offer_made')
        ]):
            count += 1
        return True  # Indicates successful processing

    # Iterate over all top-level items in the analytics_data
    for username, user_data in analytics_data.items():
        if username in known_non_user_keys:
            continue
        if username not in processed_usernames:
            if _process_user_for_stage(username, user_data, stage):
                processed_usernames.add(username)

    # Iterate over items under the 'conversations' key, if it exists
    nested_conversations = analytics_data.get('conversations')
    if isinstance(nested_conversations, dict):
        for username, user_data in nested_conversations.items():
            if username not in processed_usernames:  # Avoid double counting
                if _process_user_for_stage(username, user_data, stage):
                    processed_usernames.add(username)
    return count


def display_stage_metrics(stage: str, analytics_data: Dict[str, Any]):
    """Display consistent metrics for each stage"""
    users_in_stage = get_users_in_stage(analytics_data, stage)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Users in Stage", users_in_stage)
        st.metric("Engagement Rate", "0%")  # Placeholder for now
    with col2:
        st.metric("Average Response Time", "0 mins")  # Placeholder for now
        st.metric("Conversion Rate", "0%")  # Placeholder for now


def display_client_journey(analytics_data: Dict[str, Any]):
    """Display the client journey page with multiple tabs"""
    st.header("🚂 Client Journey")

    # Create tabs for different journey stages
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Topic 1", "Topic 2", "Topic 3", "Topic 4",
        "Topic 5 (Health/Fitness + Trial Offer)",
        "Trial Period Week 1-3",
        "Trial Period Week 4 Offer",
        "Paying Client"
    ])

    with tab1:
        st.subheader("Topic 1")
        display_stage_metrics("Topic 1", analytics_data)

    with tab2:
        st.subheader("Topic 2")
        display_stage_metrics("Topic 2", analytics_data)

    with tab3:
        st.subheader("Topic 3")
        display_stage_metrics("Topic 3", analytics_data)

    with tab4:
        st.subheader("Topic 4")
        display_stage_metrics("Topic 4", analytics_data)

    with tab5:
        st.subheader("Topic 5 (Health/Fitness + Trial Offer)")
        display_stage_metrics("Topic 5", analytics_data)

    with tab6:
        st.subheader("Trial Period Week 1-3")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Active Trials", "0")
            st.metric("Week 1 Completion", "0%")
        with col2:
            st.metric("Week 2 Completion", "0%")
            st.metric("Engagement Rate", "0%")
        with col3:
            st.metric("Week 3 Completion", "0%")
            st.metric("Satisfaction Rate", "0%")

    with tab7:
        st.subheader("Trial Period Week 4 Offer")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Users in Stage", "0")
            st.metric("Offers Made", "0")
        with col2:
            st.metric("Conversion Rate", "0%")
            st.metric("Offers Accepted", "0")

    with tab8:
        st.subheader("Paying Clients")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Paying Clients", "0")
            st.metric("Monthly Revenue", "$0")
        with col2:
            st.metric("Average Client Value", "$0")
            st.metric("Retention Rate", "0%")
        with col3:
            st.metric("Client Satisfaction", "0%")
            st.metric("Referral Rate", "0%")
