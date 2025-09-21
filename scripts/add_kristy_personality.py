#!/usr/bin/env python3
"""
Add Kristy's Personality Profile
Based on her extensive conversation with Shannon
"""

from scripts.integrate_personalized_prompting import MemberPersonalityManager
from scripts.personalized_member_prompting import MemberPersonality
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


def create_kristy_personality() -> MemberPersonality:
    """Create Kristy's personality profile based on conversation analysis"""

    # Analyze her conversation patterns
    communication_patterns = {
        'message_length': 'short_to_medium',    # Concise but expressive
        'sharing_style': 'selectively_open',    # Shares personal stuff but measured
        # "I'm a lazy little bitch", "I'm mentally insane"
        'humor_style': 'self_deprecating_witty',
        'energy_level': 'variable_moody',       # Can be anxious, excited, or down
        'response_timing': 'consistent',        # Regular engagement
        'emoji_usage': 'frequent_hearts',       # Lots of ❤️ emojis
        'question_asking': 'low',               # Rarely asks questions
        'vulnerability_level': 'medium'         # Shares struggles but not everything
    }

    # Extract specific interests from conversation
    interests = [
        'weight_loss_journey',    # Ozempic, 23kg lost, weight tracking
        'mental_health',          # Anxiety, EMDR therapy, Valium mentions
        'fitness_strength',       # Deadlifts, muscle maintenance, gym
        'podcasts_learning',      # Lex Fridman, neuroscience content
        'food_cooking',           # Pizza, cooking, food tracking
        'dog_lover',              # Heated throw rug with dog
        'philosophy_discussions',  # Free will, consciousness, deep topics
        'music_nostalgia',        # Specific bands, nostalgic music
        'travel_reluctant',       # Doesn't like leaving home, pillow packing
        'substances_alcohol',     # Booze hound, drinking mentions
        'work_stability',         # Steady job, good income
        'friendship_loyalty'      # Values close relationships, supportive
    ]

    # Her specific phrases and language patterns
    specific_phrases = [
        "❤️",                    # Most frequent emoji
        "hahaha",                # Extended laughter
        "lol",                   # Casual humor
        "fk yeah",               # Enthusiasm
        "yep",                   # Agreement/confirmation
        "nah",                   # Casual disagreement
        "I'm a lazy little bitch",  # Self-deprecating humor
        "cbf",                   # Can't be fucked (Australian slang)
        "st",                    # Shortened swearing
        "cos",                   # Because (casual spelling)
        "ya",                    # You (casual)
        "omg",                   # Excitement/surprise
        "urgh",                  # Frustration
        "bahahaha",              # Distinctive laugh
        "yeooooww",              # Celebration
        "perfecto",              # Satisfaction
        "nice",                  # Approval
        "fair",                  # Understanding/agreement
    ]

    return MemberPersonality(
        ig_username="kristy",
        communication_style="witty_pragmatic",         # Smart, funny, practical
        interests=interests,
        response_preferences="acknowledgment_first",    # Wants to be heard/understood
        # "yeooooww" but often self-deprecating
        celebration_style="understated_sarcastic",
        problem_solving_style="practical_realistic",   # Logical, solutions-focused
        specific_phrases=specific_phrases,
        conversation_history_patterns=communication_patterns
    )


def analyze_kristy_personality():
    """Analyze Kristy's unique communication traits"""

    print("🔍 KRISTY'S PERSONALITY ANALYSIS")
    print("="*50)

    traits = {
        "Communication Style": "Witty & Pragmatic - Smart humor with practical focus",
        "Emotional Range": "Variable - Can be anxious, excited, down, but always authentic",
        "Humor Style": "Self-deprecating wit - 'I'm a lazy little bitch', 'mentally insane'",
        "Sharing Pattern": "Selective openness - Shares struggles but keeps boundaries",
        "Response Style": "Concise but warm - Gets to the point with heart emojis",
        "Celebration": "Understated sarcasm - 'yeooooww' mixed with self-roasting",
        "Problem Solving": "Practical realist - Faces issues head-on, no sugar-coating",
        "Relationship Style": "Loyal supporter - Calls out Shannon but cares deeply"
    }

    for aspect, description in traits.items():
        print(f"📊 {aspect}: {description}")

    print(f"\n🎯 KEY KRISTY PATTERNS:")
    print(f"- Balances deep discussions with practical concerns")
    print(f"- Uses humor to deflect vulnerability ('I'm no business man')")
    print(f"- Supportive but won't enable ('msg her tomorrow when you're not high')")
    print(f"- Values learning but stays grounded ('I'll remain blissfully ignorant')")
    print(f"- Protective of boundaries ('I'll literally never speak to you again')")


def compare_all_three_members():
    """Compare Kristy with Sabrina and StaaCi"""

    kristy = create_kristy_personality()

    from scripts.personalized_member_prompting import create_sabrina_personality
    from scripts.add_staaci_personality import create_staaci_personality

    sabrina = create_sabrina_personality()
    staaci = create_staaci_personality()

    print(f"\n🔍 THREE-WAY MEMBER COMPARISON")
    print("="*60)

    comparison = {
        "Communication Style": {
            "Sabrina": sabrina.communication_style,
            "StaaCi": staaci.communication_style,
            "Kristy": kristy.communication_style
        },
        "Response Preferences": {
            "Sabrina": sabrina.response_preferences,
            "StaaCi": staaci.response_preferences,
            "Kristy": kristy.response_preferences
        },
        "Celebration Style": {
            "Sabrina": sabrina.celebration_style,
            "StaaCi": staaci.celebration_style,
            "Kristy": kristy.celebration_style
        },
        "Problem Solving": {
            "Sabrina": sabrina.problem_solving_style,
            "StaaCi": staaci.problem_solving_style,
            "Kristy": kristy.problem_solving_style
        }
    }

    for aspect, members in comparison.items():
        print(f"\n📊 {aspect}:")
        for member, style in members.items():
            print(f"   {member}: {style}")

    print(f"\n🎯 SHANNON'S RESPONSE ADAPTATIONS:")
    print(f"Sabrina → Technical/Direct: 'That's 1 tbsp, here's the exact macro breakdown'")
    print(f"StaaCi → Casual/Storytelling: 'Fk yeah boi! That meal's growing on ya hey? Love it!'")
    print(f"Kristy → Witty/Pragmatic: 'Fair play! That's solid progress. What's next?'")


def add_kristy_to_database():
    """Add Kristy's profile to the member personalities database"""

    manager = MemberPersonalityManager()
    kristy_personality = create_kristy_personality()

    # Store in database
    manager._store_personality_profile(kristy_personality)
    print("✅ Added Kristy's personality profile to database")

    return kristy_personality


def test_kristy_personalized_scenarios():
    """Test Kristy's personalized response scenarios"""

    test_scenarios = [
        {
            'message': 'I\'m anxious as st today, can\'t get out of bed',
            'expected_personalized': 'Empathetic but practical response, acknowledge the feeling without enabling',
            'context': 'Mental health struggle sharing'
        },
        {
            'message': 'yeooooww 89.9kg! First time in these numbers in my adult life',
            'expected_personalized': 'Enthusiastic celebration matching her energy but not over-the-top',
            'context': 'Major weight loss milestone achievement'
        },
        {
            'message': 'Cos I\'m a lazy little bitch - haven\'t trained in 3 weeks',
            'expected_personalized': 'Playful response that matches her humor without judgment',
            'context': 'Self-deprecating admission of missed workouts'
        },
        {
            'message': 'What\'s more helpful for weight loss - you or ozempic?',
            'expected_personalized': 'Honest, practical response that acknowledges her direct question style',
            'context': 'Direct comparison question'
        },
        {
            'message': 'cbf so bad, I literally don\'t want to adult anymore',
            'expected_personalized': 'Understanding response with gentle motivation, respects her mood',
            'context': 'Low energy/motivation day'
        }
    ]

    print(f"\n{'='*60}")
    print(f"KRISTY PERSONALIZED RESPONSE SCENARIOS")
    print(f"{'='*60}")

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. SCENARIO: {scenario['context']}")
        print(f"Message: \"{scenario['message']}\"")
        print(f"Expected Style: {scenario['expected_personalized']}")
        print(f"Generic would be: Standard motivational response without personality awareness")
        print("-" * 50)


def main():
    """Main function to add Kristy and demonstrate her unique personality"""

    print("🚀 ADDING KRISTY TO PERSONALIZED MEMBER SYSTEM")
    print("="*50)

    # 1. Analyze Kristy's personality
    print("\n1. Analyzing Kristy's personality...")
    analyze_kristy_personality()

    # 2. Compare with other members
    print("\n2. Comparing with Sabrina and StaaCi...")
    compare_all_three_members()

    # 3. Add to database
    print("\n3. Adding Kristy to database...")
    add_kristy_to_database()

    # 4. Test scenarios
    print("\n4. Testing personalized response scenarios...")
    test_kristy_personalized_scenarios()

    print(f"\n🎉 KRISTY PERSONALITY PROFILE CREATED!")
    print(f"\n📋 What This Enables:")
    print(f"- Shannon will match Kristy's witty, pragmatic communication style")
    print(f"- Responses will acknowledge her direct questions without overwhelming detail")
    print(f"- Celebration style matches her understated but genuine enthusiasm")
    print(f"- Problem-solving approach respects her practical, realistic mindset")
    print(f"- Humor level matches her self-deprecating but caring personality")

    print(f"\n📊 Now You Have THREE Distinct Member Personalities:")
    print(f"- Sabrina: Technical/Direct (wants specific answers)")
    print(f"- StaaCi: Storyteller/Casual (loves personal connection)")
    print(f"- Kristy: Witty/Pragmatic (appreciates smart humor + practical advice)")
    print(f"- System automatically adapts to each member's unique style!")


if __name__ == "__main__":
    main()
