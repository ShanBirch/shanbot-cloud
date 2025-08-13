import requests
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calendly_integration")

# Calendly Configuration
CALENDLY_TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzUzNjc0NjM3LCJqdGkiOiJmNzgxODUzZS02YmViLTRkZTktOWU3Ni04NmFjZmE5ZTliNDYiLCJ1c2VyX3V1aWQiOiJlZWRjYTczNS04OGU1LTQzMzQtYWQ2NS01MTBiZGIyNjAzNDQifQ.MLdafPLied0cMGQnGls6XtyxtQtE3FheG2j5EyC164p2uPocZ5hriWyVFHfGtu9C6Q6_90yRVN4HGCnOP59twA"
CALENDLY_BASE_URL = "https://api.calendly.com"
DB_PATH = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\app\analytics_data_good.sqlite"

# Headers for Calendly API
headers = {
    "Authorization": f"Bearer {CALENDLY_TOKEN}",
    "Content-Type": "application/json"
}


class CalendlyIntegration:
    """Handles Calendly API integration for booking detection."""

    def __init__(self):
        self.user_uuid = None
        self.event_type_uri = None
        self.last_known_booking_id = None
        self._initialize_calendly_data()

    def _initialize_calendly_data(self):
        """Initialize Calendly user and event data."""
        try:
            # Get user info
            response = requests.get(
                f"{CALENDLY_BASE_URL}/users/me", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                user_uri = user_data.get('resource', {}).get('uri', '')
                self.user_uuid = user_uri.split('/')[-1] if user_uri else None
                logger.info(f"Calendly user UUID: {self.user_uuid}")

                # Get event types to find "Coco's Insight Call"
                if self.user_uuid:
                    response = requests.get(f"{CALENDLY_BASE_URL}/event_types", headers=headers, params={
                        "user": f"https://api.calendly.com/users/{self.user_uuid}"
                    })
                    if response.status_code == 200:
                        event_types = response.json()
                        for event in event_types.get('collection', []):
                            if "Coco's Insight Call" in event.get('name', ''):
                                self.event_type_uri = event.get('uri')
                                logger.info(
                                    f"Found event type: {event.get('name')} ({self.event_type_uri})")
                                break

                # Get last known booking ID from database
                self._load_last_known_booking()

        except Exception as e:
            logger.error(f"Error initializing Calendly data: {e}")

    def _load_last_known_booking(self):
        """Load the last known booking ID from database."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendly_bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id TEXT UNIQUE,
                    invitee_name TEXT,
                    invitee_email TEXT,
                    booking_time TEXT,
                    event_type TEXT,
                    ig_username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add ig_username column if it doesn't exist (for existing databases)
            try:
                cursor.execute(
                    "ALTER TABLE calendly_bookings ADD COLUMN ig_username TEXT")
                logger.info(
                    "Added ig_username column to calendly_bookings table")
            except sqlite3.OperationalError:
                # Column already exists
                pass

            # Get the most recent booking ID
            cursor.execute("""
                SELECT booking_id FROM calendly_bookings 
                ORDER BY created_at DESC LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                self.last_known_booking_id = result[0]
                logger.info(
                    f"Last known booking ID: {self.last_known_booking_id}")

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error loading last known booking: {e}")

    def check_for_new_bookings(self) -> List[Dict]:
        """Check for new bookings and return list of new bookings."""
        if not self.user_uuid:
            logger.error("User UUID not available")
            return []

        try:
            # Get recent scheduled events
            response = requests.get(f"{CALENDLY_BASE_URL}/scheduled_events", headers=headers, params={
                "user": f"https://api.calendly.com/users/{self.user_uuid}",
                "count": 50  # Get last 50 events
            })

            if response.status_code != 200:
                logger.error(
                    f"Error getting scheduled events: {response.text}")
                return []

            events = response.json()
            new_bookings = []

            for event in events.get('collection', []):
                booking_id = event.get('uri', '').split('/')[-1]
                invitee = event.get('invitee', {})

                # Check if this is a new booking
                if booking_id != self.last_known_booking_id:
                    # Get invitee details including form responses
                    invitee_uri = invitee.get('uri', '')
                    ig_username = self._get_instagram_username_from_invitee(
                        invitee_uri)

                    booking_data = {
                        'booking_id': booking_id,
                        'invitee_name': invitee.get('name', 'Unknown'),
                        'invitee_email': invitee.get('email', ''),
                        'booking_time': event.get('start_time', ''),
                        'event_type': event.get('event_type', ''),
                        'event_uri': event.get('uri', ''),
                        'invitee_uri': invitee_uri,
                        'ig_username': ig_username
                    }

                    # Only count as new if it's recent (within last 24 hours)
                    booking_datetime = datetime.fromisoformat(
                        booking_data['booking_time'].replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)

                    if (now - booking_datetime).days <= 1:  # Within last 24 hours
                        new_bookings.append(booking_data)
                        logger.info(
                            f"New booking detected: {booking_data['invitee_name']} (@{ig_username if ig_username else 'no_username'})")

            return new_bookings

        except Exception as e:
            logger.error(f"Error checking for new bookings: {e}")
            return []

    def _get_instagram_username_from_invitee(self, invitee_uri: str) -> Optional[str]:
        """Extract Instagram username from invitee form responses."""
        if not invitee_uri:
            return None

        try:
            # Get invitee details including form responses
            response = requests.get(invitee_uri, headers=headers)

            if response.status_code != 200:
                logger.error(f"Error getting invitee details: {response.text}")
                return None

            invitee_data = response.json()
            answers = invitee_data.get('resource', {}).get('answers', [])

            # Look for Instagram username in form answers
            for answer in answers:
                question = answer.get('question', '')
                response_text = answer.get('answer', '')

                # Check if this is the Instagram username question
                if 'instagram' in question.lower() or 'facebook' in question.lower() or 'username' in question.lower():
                    # Clean the username (remove @ if present)
                    username = response_text.strip()
                    if username.startswith('@'):
                        username = username[1:]

                    logger.info(
                        f"Found Instagram username in booking: {username}")
                    return username

            logger.warning(
                f"No Instagram username found in booking form responses")
            return None

        except Exception as e:
            logger.error(f"Error extracting Instagram username: {e}")
            return None

    def save_booking_to_database(self, booking_data: Dict) -> bool:
        """Save booking data to database."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Check if booking already exists
            cursor.execute("""
                SELECT booking_id FROM calendly_bookings 
                WHERE booking_id = ?
            """, (booking_data['booking_id'],))

            if cursor.fetchone():
                logger.info(
                    f"Booking {booking_data['booking_id']} already exists in database, skipping")
                conn.close()
                return True  # Return True since this is expected behavior

            # Insert new booking
            cursor.execute("""
                INSERT INTO calendly_bookings 
                (booking_id, invitee_name, invitee_email, booking_time, event_type, ig_username)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                booking_data['booking_id'],
                booking_data['invitee_name'],
                booking_data['invitee_email'],
                booking_data['booking_time'],
                booking_data['event_type'],
                # Use the Instagram username from the form
                booking_data.get('ig_username')
            ))

            conn.commit()
            conn.close()

            # Update last known booking ID
            self.last_known_booking_id = booking_data['booking_id']

            logger.info(
                f"Saved booking to database: {booking_data['invitee_name']}")
            return True

        except Exception as e:
            logger.error(f"Error saving booking to database: {e}")
            return False

    def update_analytics_for_booking(self, booking_data: Dict) -> bool:
        """Update analytics data when a new booking is detected."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Use the Instagram username directly from the booking data
            ig_username = booking_data.get('ig_username')

            if ig_username:
                logger.info(
                    f"Booking linked to Instagram user: @{ig_username}")
            else:
                logger.warning(
                    f"No Instagram username found for booking: {booking_data['invitee_name']}")
                ig_username = f"booking_{booking_data['booking_id']}"

            # Add a message to the messages table indicating booking confirmation
            booking_message = f"🎉 Booking confirmed! {booking_data['invitee_name']} has scheduled a call for {booking_data['booking_time']}"

            cursor.execute("""
                INSERT INTO messages (ig_username, subscriber_id, message, sender, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                ig_username,
                booking_data['booking_id'],
                booking_message,
                'system',
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            logger.info(
                f"Updated analytics for booking: {booking_data['invitee_name']} -> @{ig_username}")
            return True

        except Exception as e:
            logger.error(f"Error updating analytics for booking: {e}")
            return False

    def process_new_bookings(self) -> int:
        """Main method to check for and process new bookings."""
        new_bookings = self.check_for_new_bookings()
        processed_count = 0

        for booking in new_bookings:
            # Save to database
            if self.save_booking_to_database(booking):
                # Update analytics
                if self.update_analytics_for_booking(booking):
                    # Mark booking as completed if we have an Instagram username
                    if booking.get('ig_username'):
                        self.mark_booking_completed(booking['ig_username'])

                    processed_count += 1
                    logger.info(
                        f"Successfully processed booking for: {booking['invitee_name']}")

        if processed_count > 0:
            logger.info(f"Processed {processed_count} new booking(s)")

        return processed_count

    def link_booking_to_instagram(self, booking_id: str, ig_username: str) -> bool:
        """Manually link a booking to an Instagram username."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Update the booking record with Instagram username
            cursor.execute("""
                UPDATE calendly_bookings 
                SET ig_username = ? 
                WHERE booking_id = ?
            """, (ig_username, booking_id))

            if cursor.rowcount > 0:
                # Add a system message to the conversation
                booking_message = f"🔗 Booking linked to Instagram conversation for {ig_username}"

                cursor.execute("""
                    INSERT INTO messages (ig_username, subscriber_id, message, sender, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ig_username,
                    booking_id,
                    booking_message,
                    'system',
                    datetime.now().isoformat()
                ))

                conn.commit()
                conn.close()
                logger.info(
                    f"Successfully linked booking {booking_id} to Instagram user {ig_username}")
                return True
            else:
                logger.warning(f"Booking {booking_id} not found for linking")
                return False

        except Exception as e:
            logger.error(f"Error linking booking to Instagram: {e}")
            return False

    def get_unlinked_bookings(self) -> List[Dict]:
        """Get all bookings that haven't been linked to Instagram conversations."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT booking_id, invitee_name, invitee_email, booking_time, event_type
                FROM calendly_bookings 
                WHERE ig_username IS NULL OR ig_username = ''
                ORDER BY created_at DESC
            """)

            bookings = []
            for row in cursor.fetchall():
                bookings.append({
                    'booking_id': row[0],
                    'invitee_name': row[1],
                    'invitee_email': row[2],
                    'booking_time': row[3],
                    'event_type': row[4]
                })

            conn.close()
            return bookings

        except Exception as e:
            logger.error(f"Error getting unlinked bookings: {e}")
            return []

    def track_calendar_link_sent(self, ig_username: str, subscriber_id: str = None) -> bool:
        """Track when a calendar link is sent to a user."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_link_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ig_username TEXT,
                    subscriber_id TEXT,
                    link_sent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    booking_status TEXT DEFAULT 'pending',
                    booking_timestamp TIMESTAMP NULL,
                    follow_up_sent_count INTEGER DEFAULT 0,
                    last_follow_up_timestamp TIMESTAMP NULL
                )
            """)

            # Check if we already have a record for this user
            cursor.execute("""
                SELECT id FROM calendar_link_tracking 
                WHERE ig_username = ? AND booking_status = 'pending'
                ORDER BY link_sent_timestamp DESC LIMIT 1
            """, (ig_username,))

            existing = cursor.fetchone()

            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE calendar_link_tracking 
                    SET link_sent_timestamp = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (existing[0],))
                logger.info(
                    f"Updated calendar link tracking for @{ig_username}")
            else:
                # Create new record
                cursor.execute("""
                    INSERT INTO calendar_link_tracking 
                    (ig_username, subscriber_id, link_sent_timestamp)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (ig_username, subscriber_id))
                logger.info(f"Tracked calendar link sent to @{ig_username}")

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Error tracking calendar link: {e}")
            return False

    def mark_booking_completed(self, ig_username: str) -> bool:
        """Mark that a user has completed their booking."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Update the most recent pending record for this user
            cursor.execute("""
                UPDATE calendar_link_tracking 
                SET booking_status = 'completed', booking_timestamp = CURRENT_TIMESTAMP
                WHERE ig_username = ? AND booking_status = 'pending'
                ORDER BY link_sent_timestamp DESC LIMIT 1
            """, (ig_username,))

            if cursor.rowcount > 0:
                logger.info(f"Marked booking as completed for @{ig_username}")
                conn.commit()
                conn.close()
                return True
            else:
                logger.warning(
                    f"No pending calendar link found for @{ig_username}")
                conn.close()
                return False

        except Exception as e:
            logger.error(f"Error marking booking completed: {e}")
            return False

    def get_users_needing_follow_up(self, days_since_link: int = 7) -> List[Dict]:
        """Get users who received a calendar link but haven't booked yet."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ig_username, subscriber_id, link_sent_timestamp, follow_up_sent_count
                FROM calendar_link_tracking 
                WHERE booking_status = 'pending' 
                AND link_sent_timestamp <= datetime('now', '-{} days')
                AND (last_follow_up_timestamp IS NULL OR last_follow_up_timestamp <= datetime('now', '-7 days'))
                ORDER BY link_sent_timestamp ASC
            """.format(days_since_link))

            users = []
            for row in cursor.fetchall():
                users.append({
                    'ig_username': row[0],
                    'subscriber_id': row[1],
                    'link_sent_timestamp': row[2],
                    'follow_up_sent_count': row[3]
                })

            conn.close()
            logger.info(f"Found {len(users)} users needing follow-up")
            return users

        except Exception as e:
            logger.error(f"Error getting users needing follow-up: {e}")
            return []


def run_booking_check():
    """Run a single booking check."""
    integration = CalendlyIntegration()
    return integration.process_new_bookings()


if __name__ == "__main__":
    # Test the integration
    print("=== Testing Calendly Integration ===")
    count = run_booking_check()
    print(f"Processed {count} new booking(s)")
