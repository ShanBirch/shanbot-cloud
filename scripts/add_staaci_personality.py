#!/usr/bin/env python3
"""
Add StaaCi's Personality Profile
Based on her extensive conversation with Shannon
"""

from scripts.integrate_personalized_prompting import MemberPersonalityManager
from scripts.personalized_member_prompting import MemberPersonality
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


def create_staaci_personality() -> MemberPersonality:
    """Create StaaCi's personality profile based on conversation analysis"""

    # Analyze her conversation patterns
    communication_patterns = {
        'message_length': 'medium_to_long',  # Loves detailed storytelling
        'sharing_style': 'very_open',        # Shares personal life freely
        'humor_style': 'self_deprecating',   # "I suck with technology"
        'energy_level': 'relaxed_casual',    # 420 references, casual vibe
        'response_timing': 'variable',       # Sometimes quick, sometimes delayed
        'emoji_usage': 'frequent',           # Lots of emojis and hearts
        'question_asking': 'moderate',       # Asks about Shannon's life too
        'vulnerability_level': 'high'        # Shares dad's cancer, work stress
    }

    # Extract specific interests from conversation
    interests = [
        'animals_pets',         # 4 dogs, 4 cats, geckos, wildlife
        'gardening',           # Growing pumpkins, watermelons
        'cooking',             # Loves cooking, creative with meals
        'ceramics',            # Does pottery/ceramics
        'cannabis_culture',    # 420 references, vaping, smoking
        'family_caregiving',   # Cares for parents, sister
        'fitness_beginner',    # New to fitness journey
        'outdoor_activities',  # Long walks with Radar
        'motorsports',         # Mentioned motor sports
        'twirl_dance',         # Currently does twirl dance
        'kickboxing_interest',  # Considering kickboxing
        'technology_struggles'  # Self-admits tech difficulties
    ]

    # Her specific phrases and language patterns
    specific_phrases = [
        "boi",                 # "Morning boi"
        "❤️",                  # Uses heart emoji frequently
        "haha",                # Frequent laughter
        "lol",                 # Casual text speak
        "😅😊🤩🥰",           # Specific emoji combinations
        "v nice",              # Shorthand expressions
        "fk yeah",             # Casual swearing
        "absolute fuck",       # Strong descriptive language
        "we good",             # Reassuring phrases
        "all good",            # Easy-going responses
        "that's ok",           # Understanding/forgiving
        "hahaha",              # Extended laughter
        "😜😘",               # Playful emoji combinations
    ]

    return MemberPersonality(
        ig_username="staaci",
        communication_style="storyteller_casual",  # Long, detailed, personal messages
        interests=interests,
        response_preferences="personal_connection_first",  # Values relationship building
        celebration_style="encouraging_playful",  # "Hell yeah", "fk yeah", encouraging
        problem_solving_style="supportive_flexible",  # Understanding, adaptable
        specific_phrases=specific_phrases,
        conversation_history_patterns=communication_patterns
    )


def analyze_staaci_vs_sabrina():
    """Compare StaaCi and Sabrina to show personalization differences"""

    staaci = create_staaci_personality()

    # Import Sabrina for comparison
    from scripts.personalized_member_prompting import create_sabrina_personality
    sabrina = create_sabrina_personality()

    print("🔍 MEMBER PERSONALITY COMPARISON")
    print("="*50)

    print(f"\n📊 COMMUNICATION STYLES:")
    print(f"StaaCi: {staaci.communication_style}")
    print(f"Sabrina: {sabrina.communication_style}")

    print(f"\n🎉 CELEBRATION STYLES:")
    print(f"StaaCi: {staaci.celebration_style}")
    print(f"Sabrina: {sabrina.celebration_style}")

    print(f"\n🤝 PROBLEM SOLVING:")
    print(f"StaaCi: {staaci.problem_solving_style}")
    print(f"Sabrina: {sabrina.problem_solving_style}")

    print(f"\n📝 RESPONSE PREFERENCES:")
    print(f"StaaCi: {staaci.response_preferences}")
    print(f"Sabrina: {sabrina.response_preferences}")

    print(f"\n🎯 KEY INTERESTS:")
    print(f"StaaCi: {', '.join(staaci.interests[:5])}...")
    print(f"Sabrina: {', '.join(sabrina.interests[:5])}...")

    return staaci, sabrina


def add_staaci_to_database():
    """Add StaaCi's profile to the member personalities database"""

    manager = MemberPersonalityManager()
    staaci_personality = create_staaci_personality()

    # Store in database
    manager._store_personality_profile(staaci_personality)
    print("✅ Added StaaCi's personality profile to database")

    return staaci_personality


def test_staaci_personalized_responses():
    """Test how StaaCi's personalized responses would differ from generic"""

    manager = MemberPersonalityManager()

    test_scenarios = [
        {
            'message': 'Had a rough day, dad\'s radiotherapy was tough and I\'m feeling tired',
            'expected_personalized': 'Empathetic response acknowledging family situation, gentle encouragement',
            'context': 'Personal sharing about difficult family situation'
        },
        {
            'message': 'Yo smashed it! Just finished my workout and made that tofu meal again',
            'expected_personalized': 'Enthusiastic celebration matching her energy, reference to the meal she loves',
            'context': 'Achievement sharing with casual language'
        },
        {
            'message': 'Is it bad to have a bread roll? I couldn\'t resist, it smelled so good',
            'expected_personalized': 'Understanding response about cravings, focus on moderation not restriction',
            'context': 'Food confession/guilt'
        },
        {
            'message': 'My dogs are being crazy today, 10km walk and they still have energy!',
            'expected_personalized': 'Playful response about her dogs, acknowledge her active lifestyle',
            'context': 'Pet/lifestyle sharing'
        }
    ]

    print(f"\n{'='*60}")
    print(f"STAACI PERSONALIZED RESPONSE PREVIEW")
    print(f"{'='*60}")

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. SCENARIO: {scenario['context']}")
        print(f"Message: \"{scenario['message']}\"")
        print(f"Expected Style: {scenario['expected_personalized']}")
        print(f"Generic would be: More formal, less personal connection")
        print("-" * 50)


def main():
    """Main function to add StaaCi and demonstrate personalization"""

    print("🚀 ADDING STAACI TO PERSONALIZED MEMBER SYSTEM")
    print("="*50)

    # 1. Analyze differences
    print("\n1. Analyzing StaaCi vs Sabrina...")
    staaci, sabrina = analyze_staaci_vs_sabrina()

    # 2. Add to database
    print("\n2. Adding StaaCi to database...")
    add_staaci_to_database()

    # 3. Test personalized responses
    print("\n3. Testing personalized response scenarios...")
    test_staaci_personalized_responses()

    print(f"\n🎉 STAACI PERSONALITY PROFILE CREATED!")
    print(f"\n📋 What This Enables:")
    print(f"- Shannon will match StaaCi's casual, storytelling style")
    print(f"- References to her dogs, garden, family situation when appropriate")
    print(f"- Supportive responses that acknowledge her openness")
    print(f"- Celebration style that matches her energy ('fk yeah!')")
    print(f"- Understanding of her 420 culture and lifestyle")

    print(f"\n📊 Now You Have:")
    print(f"- Sabrina: Technical/Direct style")
    print(f"- StaaCi: Storyteller/Casual style")
    print(f"- System that adapts to each member automatically")


if __name__ == "__main__":
    main()
