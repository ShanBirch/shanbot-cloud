#!/usr/bin/env python3
"""
Integration Script for Personalized Member Prompting
Integrates the personalized system into existing Shanbot member chat flow
"""

from scripts.personalized_member_prompting import PersonalizedMemberPromptEngine, MemberPersonality
import os
import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


class MemberPersonalityManager:
    """Manages member personality profiles and integrates with existing Shanbot system"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(project_root / "app" / "shanbot.db")
        self.engine = PersonalizedMemberPromptEngine()
        self.ensure_personality_table()

    def ensure_personality_table(self):
        """Create member personality table if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS member_personalities (
                    ig_username TEXT PRIMARY KEY,
                    communication_style TEXT,
                    interests TEXT,  -- JSON array
                    response_preferences TEXT,
                    celebration_style TEXT,
                    problem_solving_style TEXT,
                    specific_phrases TEXT,  -- JSON array
                    conversation_patterns TEXT,  -- JSON object
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    analysis_version INTEGER DEFAULT 1
                )
            ''')

            conn.commit()
            conn.close()
            print("✅ Member personality table created/verified")

        except Exception as e:
            print(f"❌ Error creating personality table: {e}")

    def analyze_and_store_member_personality(self, ig_username: str) -> Optional[MemberPersonality]:
        """Analyze member's conversation history and store personality profile"""
        try:
            # Get conversation history from existing Shanbot database
            conversation_history = self._get_member_conversation_history(
                ig_username)

            if not conversation_history or len(conversation_history) < 5:
                print(
                    f"⚠️ Not enough conversation history for {ig_username} ({len(conversation_history) if conversation_history else 0} messages)")
                return None

            # Analyze patterns
            personality = self.engine.analyze_member_patterns(
                ig_username, conversation_history)

            # Store in database
            self._store_personality_profile(personality)

            print(f"✅ Analyzed and stored personality for {ig_username}")
            print(f"   - Style: {personality.communication_style}")
            print(f"   - Interests: {', '.join(personality.interests)}")
            print(f"   - Celebration: {personality.celebration_style}")

            return personality

        except Exception as e:
            print(f"❌ Error analyzing {ig_username}: {e}")
            return None

    def _get_member_conversation_history(self, ig_username: str) -> List[Dict]:
        """Get conversation history from existing Shanbot tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Try to get from messages table first (preferred)
            cursor.execute('''
                SELECT timestamp, type, text, sender, message_type, message_text
                FROM messages 
                WHERE ig_username = ? 
                ORDER BY timestamp ASC
                LIMIT 200
            ''', (ig_username,))

            rows = cursor.fetchall()
            history = []

            for row in rows:
                timestamp, msg_type, text, sender, message_type, message_text = row

                # Normalize message type
                final_type = self._normalize_message_type(
                    msg_type or sender or message_type)
                final_text = text or message_text or ''

                if final_text.strip():
                    history.append({
                        'timestamp': timestamp,
                        'type': final_type,
                        'text': final_text.strip(),
                        'sender': final_type
                    })

            # If not enough messages, try learning feedback log
            if len(history) < 10:
                cursor.execute('''
                    SELECT original_prompt_text, edited_response_text
                    FROM learning_feedback_log
                    WHERE ig_username = ? AND conversation_type = 'member'
                    ORDER BY timestamp DESC
                    LIMIT 50
                ''', (ig_username,))

                for prompt, response in cursor.fetchall():
                    if prompt and prompt.strip():
                        history.append({
                            'timestamp': '',
                            'type': 'user',
                            'text': prompt.strip(),
                            'sender': 'user'
                        })
                    if response and response.strip():
                        history.append({
                            'timestamp': '',
                            'type': 'ai',
                            'text': response.strip(),
                            'sender': 'ai'
                        })

            conn.close()
            return history

        except Exception as e:
            print(
                f"❌ Error getting conversation history for {ig_username}: {e}")
            return []

    def _normalize_message_type(self, msg_type: str) -> str:
        """Normalize message type to 'user' or 'ai'"""
        if not msg_type:
            return 'unknown'

        msg_type_lower = msg_type.lower()

        if msg_type_lower in ['incoming', 'user', 'client', 'lead', 'human']:
            return 'user'
        elif msg_type_lower in ['outgoing', 'ai', 'bot', 'shanbot', 'shannon', 'assistant']:
            return 'ai'
        else:
            return msg_type_lower

    def _store_personality_profile(self, personality: MemberPersonality):
        """Store personality profile in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO member_personalities 
                (ig_username, communication_style, interests, response_preferences, 
                 celebration_style, problem_solving_style, specific_phrases, 
                 conversation_patterns, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                personality.ig_username,
                personality.communication_style,
                json.dumps(personality.interests),
                personality.response_preferences,
                personality.celebration_style,
                personality.problem_solving_style,
                json.dumps(personality.specific_phrases),
                json.dumps(personality.conversation_history_patterns)
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            print(
                f"❌ Error storing personality for {personality.ig_username}: {e}")

    def get_member_personality(self, ig_username: str) -> Optional[MemberPersonality]:
        """Retrieve stored personality profile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT communication_style, interests, response_preferences,
                       celebration_style, problem_solving_style, specific_phrases,
                       conversation_patterns
                FROM member_personalities 
                WHERE ig_username = ?
            ''', (ig_username,))

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return MemberPersonality(
                ig_username=ig_username,
                communication_style=row[0],
                interests=json.loads(row[1]) if row[1] else [],
                response_preferences=row[2],
                celebration_style=row[3],
                problem_solving_style=row[4],
                specific_phrases=json.loads(row[5]) if row[5] else [],
                conversation_history_patterns=json.loads(
                    row[6]) if row[6] else {}
            )

        except Exception as e:
            print(f"❌ Error retrieving personality for {ig_username}: {e}")
            return None

    def generate_personalized_member_prompt(self, ig_username: str, current_message: str,
                                            conversation_history: str, context: Dict) -> Tuple[str, bool]:
        """Generate personalized prompt for member chat"""
        try:
            # Get or create personality profile
            personality = self.get_member_personality(ig_username)

            if not personality:
                # Try to analyze from conversation history
                personality = self.analyze_and_store_member_personality(
                    ig_username)

            if personality:
                # Generate personalized prompt
                personalized_prompt = self.engine.generate_personalized_prompt(
                    ig_username=ig_username,
                    member_personality=personality,
                    current_message=current_message,
                    general_context=context
                )

                return personalized_prompt, True
            else:
                # Fall back to general member prompt
                return self._get_fallback_member_prompt(ig_username, current_message, conversation_history, context), False

        except Exception as e:
            print(
                f"❌ Error generating personalized prompt for {ig_username}: {e}")
            return self._get_fallback_member_prompt(ig_username, current_message, conversation_history, context), False

    def _get_fallback_member_prompt(self, ig_username: str, current_message: str,
                                    conversation_history: str, context: Dict) -> str:
        """Fallback to general member prompt if personalization fails"""
        # Import the existing member prompt template
        try:
            from app.prompts import MEMBER_CONVERSATION_PROMPT_TEMPLATE

            return MEMBER_CONVERSATION_PROMPT_TEMPLATE.format(
                current_melbourne_time_str=context.get(
                    'current_melbourne_time_str', ''),
                ig_username=ig_username,
                first_name=context.get('first_name', ig_username),
                fitness_goals=context.get('fitness_goals', ''),
                dietary_requirements=context.get('dietary_requirements', ''),
                current_program=context.get('current_program', ''),
                full_conversation=conversation_history,
                few_shot_examples=context.get('few_shot_examples', '')
            )

        except Exception:
            return f"You are Shannon responding to {ig_username}. Use your authentic Australian coaching style."


def create_sabrina_demo_profile():
    """Create Sabrina's profile based on conversation analysis"""
    from scripts.personalized_member_prompting import create_sabrina_personality

    manager = MemberPersonalityManager()
    sabrina_personality = create_sabrina_personality()

    # Store in database
    manager._store_personality_profile(sabrina_personality)
    print("✅ Created demo profile for Sabrina")

    return sabrina_personality


def test_personalized_prompt():
    """Test the personalized prompting system"""
    manager = MemberPersonalityManager()

    # Test with Sabrina
    test_message = "For the batch cooking, is this screenshot for 3 serves or 1?"
    test_context = {
        'current_melbourne_time_str': '2024-01-15 10:30 AM AEDT',
        'first_name': 'Sabrina',
        'fitness_goals': 'Get back to consistent strength training',
        'dietary_requirements': 'Vegan, gluten-free',
        'current_program': '28-day challenge',
        'few_shot_examples': ''
    }

    prompt, is_personalized = manager.generate_personalized_member_prompt(
        'sabrina', test_message, 'Previous conversation...', test_context
    )

    print(f"\n{'='*50}")
    print(f"PERSONALIZED PROMPT TEST")
    print(f"{'='*50}")
    print(f"User: sabrina")
    print(f"Message: {test_message}")
    print(f"Personalized: {'✅ YES' if is_personalized else '❌ NO (fallback)'}")
    print(f"\nGenerated Prompt:")
    print(f"{'-'*30}")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)


def update_member_chat_system():
    """Update the existing member chat system to use personalized prompting"""

    # This would integrate with webhook_handlers.py build_member_chat_prompt function
    integration_code = '''
# Add this to webhook_handlers.py build_member_chat_prompt function:

def build_member_chat_prompt(
    client_data: Dict[str, Any],
    current_message: str,
    conversation_history: str = "",
    current_stage: str = "Topic 1", 
    trial_status: str = "Initial Contact",
    full_name: Optional[str] = None,
    full_conversation_string: str = "",
    few_shot_examples: Optional[List[Dict[str, str]]] = None
) -> tuple[str, str]:
    
    # NEW: Try personalized prompting first
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        
        ig_username = client_data.get('ig_username', '')
        if ig_username:
            manager = MemberPersonalityManager()
            
            context = {
                'current_melbourne_time_str': get_melbourne_time_str(),
                'first_name': full_name or ig_username,
                'fitness_goals': client_data.get('fitness_goals', ''),
                'dietary_requirements': client_data.get('dietary_requirements', ''),
                'current_program': client_data.get('current_program', ''),
                'few_shot_examples': format_few_shot_examples(few_shot_examples)
            }
            
            personalized_prompt, success = manager.generate_personalized_member_prompt(
                ig_username, current_message, full_conversation_string, context
            )
            
            if success:
                logger.info(f"✅ Using personalized prompt for {ig_username}")
                return personalized_prompt, "personalized_member_chat"
    
    except Exception as e:
        logger.warning(f"⚠️ Personalized prompting failed for {ig_username}: {e}")
    
    # FALLBACK: Use existing member prompt logic
    # ... existing code continues ...
'''

    print("\n📋 INTEGRATION INSTRUCTIONS:")
    print("="*50)
    print("1. Add the personalized prompting system to your member chat flow")
    print("2. The system will automatically:")
    print("   - Try personalized prompting first")
    print("   - Fall back to general member prompt if needed")
    print("   - Learn and improve member profiles over time")
    print("\n💻 Code to add to webhook_handlers.py:")
    print(integration_code)


def main():
    """Main integration workflow"""
    print("🚀 INTEGRATING PERSONALIZED MEMBER PROMPTING")
    print("="*50)

    # 1. Create demo profile for Sabrina
    print("\n1. Creating Sabrina's demo profile...")
    sabrina_profile = create_sabrina_demo_profile()

    # 2. Test the system
    print("\n2. Testing personalized prompting...")
    test_personalized_prompt()

    # 3. Show integration instructions
    print("\n3. Integration instructions...")
    update_member_chat_system()

    print("\n🎉 PERSONALIZED MEMBER PROMPTING READY!")
    print("\n📋 Next Steps:")
    print("- Test with Sabrina's real conversations")
    print("- Add more member profiles as you get conversations")
    print("- Monitor response quality improvements")
    print("- The system learns automatically with each interaction")


if __name__ == "__main__":
    main()
