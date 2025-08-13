import streamlit as st
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Notification storage file
NOTIFICATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "notifications.json")


class NotificationManager:
    """Manages dashboard notifications for important events"""

    def __init__(self):
        self.notifications_file = NOTIFICATIONS_FILE

    def add_notification(self, title: str, message: str, notification_type: str = "info", username: str = None):
        """
        Add a new notification

        Args:
            title: Notification title
            message: Notification message  
            notification_type: Type of notification (success, info, warning, error)
            username: Related username if applicable
        """
        try:
            notifications = self._load_notifications()

            notification = {
                "id": f"{datetime.now().timestamp()}_{len(notifications)}",
                "title": title,
                "message": message,
                "type": notification_type,
                "username": username,
                "timestamp": datetime.now().isoformat(),
                "read": False
            }

            notifications.append(notification)

            # Keep only last 100 notifications
            if len(notifications) > 100:
                notifications = notifications[-100:]

            self._save_notifications(notifications)
            logger.info(f"Added notification: {title} for {username}")
            return True

        except Exception as e:
            logger.error(f"Error adding notification: {e}", exc_info=True)
            return False

    def get_unread_notifications(self) -> List[Dict]:
        """Get all unread notifications"""
        try:
            notifications = self._load_notifications()
            return [n for n in notifications if not n.get('read', False)]
        except Exception as e:
            logger.error(f"Error getting unread notifications: {e}")
            return []

    def get_recent_notifications(self, hours: int = 24) -> List[Dict]:
        """Get notifications from the last N hours"""
        try:
            notifications = self._load_notifications()
            cutoff_time = datetime.now() - timedelta(hours=hours)

            recent = []
            for notification in notifications:
                try:
                    notif_time = datetime.fromisoformat(
                        notification['timestamp'])
                    if notif_time >= cutoff_time:
                        recent.append(notification)
                except (ValueError, KeyError):
                    continue

            return sorted(recent, key=lambda x: x['timestamp'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting recent notifications: {e}")
            return []

    def mark_as_read(self, notification_id: str):
        """Mark a notification as read"""
        try:
            notifications = self._load_notifications()
            for notification in notifications:
                if notification.get('id') == notification_id:
                    notification['read'] = True
                    break
            self._save_notifications(notifications)
            return True
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    def mark_all_as_read(self):
        """Mark all notifications as read"""
        try:
            notifications = self._load_notifications()
            for notification in notifications:
                notification['read'] = True
            self._save_notifications(notifications)
            return True
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return False

    def _load_notifications(self) -> List[Dict]:
        """Load notifications from file"""
        try:
            if os.path.exists(self.notifications_file):
                with open(self.notifications_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('notifications', [])
            return []
        except Exception as e:
            logger.error(f"Error loading notifications: {e}")
            return []

    def _save_notifications(self, notifications: List[Dict]):
        """Save notifications to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(
                self.notifications_file), exist_ok=True)

            data = {
                'notifications': notifications,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.notifications_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving notifications: {e}")


def display_notification_panel():
    """Display the notification panel in the dashboard"""

    # Custom CSS for notification styling
    st.markdown("""
    <style>
    .notification-banner {
        background: linear-gradient(90deg, #ff6b6b, #ffa500);
        color: white;
        padding: 8px 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(255,107,107,0.3);
    }
    
    .notification-pulse {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255,107,107,0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255,107,107,0); }
        100% { box-shadow: 0 0 0 0 rgba(255,107,107,0); }
    }
    
    .notification-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.375rem;
        padding: 0.75rem;
        margin: 0.5rem 0;
        color: #155724;
    }
    .notification-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.375rem;
        padding: 0.75rem;
        margin: 0.5rem 0;
        color: #856404;
    }
    </style>
    """, unsafe_allow_html=True)

    # Initialize notification manager
    notif_manager = NotificationManager()

    # Get recent notifications
    recent_notifications = notif_manager.get_recent_notifications(
        hours=72)  # Last 3 days
    unread_count = len(
        [n for n in recent_notifications if not n.get('read', False)])

    # Create notification area at top of page
    if unread_count > 0 or st.session_state.get('show_notifications', False):
        with st.container():
            col1, col2, col3 = st.columns([6, 2, 2])

            with col1:
                if unread_count > 0:
                    st.markdown(f"""
                    <div class="notification-banner notification-pulse">
                        🔔 {unread_count} new notification{'s' if unread_count != 1 else ''} - Check important updates!
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("🔔 Notifications")

            with col2:
                if st.button("📋 View All", key="view_notifications", type="primary"):
                    st.session_state.show_notifications = True

            with col3:
                if unread_count > 0:
                    if st.button("✅ Mark Read", key="mark_read_top", type="secondary"):
                        notif_manager.mark_all_as_read()
                        st.rerun()

            # Show recent notifications if requested
            if st.session_state.get('show_notifications', False):
                st.divider()

                # Close button
                if st.button("❌ Close Notifications", key="close_notifications"):
                    st.session_state.show_notifications = False
                    st.rerun()

                if recent_notifications:
                    for i, notification in enumerate(recent_notifications[:10]):
                        is_unread = not notification.get('read', False)
                        notif_type = notification.get('type', 'info')

                        # Use container for all notifications and apply custom styling
                        with st.container():
                            # Apply custom styling based on type and read status
                            if is_unread:
                                if notif_type == 'success':
                                    st.markdown(f"""
                                    <div class="notification-success">
                                        <strong>✅ {notification['title']}</strong> (NEW)
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif notif_type == 'warning':
                                    st.markdown(f"""
                                    <div class="notification-warning">
                                        <strong>⚠️ {notification['title']}</strong> (NEW)
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif notif_type == 'error':
                                    st.error(
                                        f"❌ **{notification['title']}** (NEW)")
                                else:
                                    st.info(
                                        f"ℹ️ **{notification['title']}** (NEW)")
                            else:
                                st.write(f"**{notification['title']}**")

                            # Format timestamp
                            try:
                                notif_time = datetime.fromisoformat(
                                    notification['timestamp'])
                                time_ago = datetime.now() - notif_time
                                if time_ago.days > 0:
                                    time_str = f"{time_ago.days}d ago"
                                elif time_ago.seconds > 3600:
                                    time_str = f"{time_ago.seconds // 3600}h ago"
                                else:
                                    time_str = f"{time_ago.seconds // 60}m ago"
                            except:
                                time_str = "Recently"

                            # Display notification content
                            col_content, col_action = st.columns([4, 1])

                            with col_content:
                                st.write(notification['message'])
                                st.caption(
                                    f"👤 {notification.get('username', 'System')} • {time_str}")

                            with col_action:
                                if is_unread:
                                    if st.button("✓", key=f"read_{i}", help="Mark as read", type="primary"):
                                        notif_manager.mark_as_read(
                                            notification['id'])
                                        st.rerun()

                            st.divider()
                else:
                    st.info("🎉 No recent notifications")

                st.divider()


def add_email_collected_notification(username: str, email: str):
    """Add blue notification when challenger provides email address"""
    notif_manager = NotificationManager()
    return notif_manager.add_notification(
        title="📧 Email Collected!",
        message=f"@{username} provided email: {email} - Ready for July 28th challenge!",
        notification_type="info",  # Blue styling
        username=username
    )


def add_challenge_notification(username: str, challenge_details: str = "28-Day Transformation Challenge"):
    """Add notification when a challenge is offered"""
    notif_manager = NotificationManager()
    return notif_manager.add_notification(
        title="🎯 Challenge Offered!",
        message=f"Offered {challenge_details} to @{username}",
        notification_type="warning",
        username=username
    )


def add_trial_notification(username: str, trial_type: str = "28-Day Trial"):
    """Add notification when someone becomes a trial member"""
    notif_manager = NotificationManager()
    return notif_manager.add_notification(
        title="🆓 New Trial Member!",
        message=f"@{username} signed up for {trial_type}",
        notification_type="success",
        username=username
    )


def add_sale_notification(username: str, sale_details: str = "Paying Client"):
    """Add notification when someone becomes a paying client"""
    notif_manager = NotificationManager()
    return notif_manager.add_notification(
        title="💰 New Sale!",
        message=f"@{username} became a {sale_details}",
        notification_type="success",
        username=username
    )


def check_ai_response_for_challenge_offer(ai_response_text: str, username: str):
    """Check if an AI response contains a challenge offer (with URL) and create notification"""
    if not ai_response_text or not username:
        return False

    # Check for the presence of the actual offer URL
    if 'cocospersonaltraining.com' not in ai_response_text.lower():
        return False  # No URL means no actual offer was made

    message_lower = ai_response_text.lower()

    # Look for challenge-related keywords, as the URL alone might not distinguish the offer type
    challenge_indicators = [
        "28 day", "28-day", "28day",
        "challenge", "transformation",
        "free trial", "trial program",
        "program", "coaching"
    ]

    challenge_mentioned = any(
        indicator in message_lower for indicator in challenge_indicators)

    if challenge_mentioned:
        # Determine challenge type based on content if the URL is present
        if "28" in message_lower:
            challenge_type = "28-Day Transformation Challenge"
        elif "trial" in message_lower:
            challenge_type = "Free Trial Program"
        else:
            challenge_type = "Coaching Program"

        return add_challenge_notification(username, challenge_type)

    return False


def create_demo_notifications():
    """Create some demo notifications for testing"""
    notif_manager = NotificationManager()

    # Add realistic demo notifications
    demo_notifications = [
        {
            "title": "🎯 Challenge Offered!",
            "message": "Offered 28-Day Transformation Challenge to @sarah_fitness_journey",
            "type": "warning",
            "username": "sarah_fitness_journey"
        },
        {
            "title": "🆓 New Trial Member!",
            "message": "@mike_strongman signed up for Trial Week 1",
            "type": "success",
            "username": "mike_strongman"
        },
        {
            "title": "💰 New Sale!",
            "message": "@jessica_plantbased became a Paying Client",
            "type": "success",
            "username": "jessica_plantbased"
        },
        {
            "title": "🎯 Challenge Offered!",
            "message": "Offered Free Trial Program to @alex_veganfitness",
            "type": "warning",
            "username": "alex_veganfitness"
        }
    ]

    for notif in demo_notifications:
        notif_manager.add_notification(
            title=notif["title"],
            message=notif["message"],
            notification_type=notif["type"],
            username=notif["username"]
        )

    return len(demo_notifications)
