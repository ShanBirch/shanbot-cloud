#!/usr/bin/env python3
"""
Add Shane's Personality Profile
Based on his extensive conversation with Shannon
"""

from scripts.integrate_personalized_prompting import MemberPersonalityManager
from scripts.personalized_member_prompting import MemberPersonality
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


def create_shane_personality() -> MemberPersonality:
    """Create Shane's personality profile based on conversation analysis"""

    # Analyze his conversation patterns
    communication_patterns = {
        'message_length': 'short_structured',    # Brief but complete responses
        'sharing_style': 'progress_focused',     # Shares achievements and challenges
        'humor_style': 'gentle_self_aware',      # "lol", self-deprecating but mild
        'energy_level': 'steady_consistent',     # Reliable, consistent engagement
        'response_timing': 'responsive',         # Usually replies promptly
        'emoji_usage': 'minimal_hearts',         # Occasional ❤️, not excessive
        'question_asking': 'practical',          # Asks specific, actionable questions
        'vulnerability_level': 'moderate'        # Shares struggles but stays positive
    }

    # Extract specific interests from conversation
    interests = [
        'fitness_progression',     # Loves seeing improvement, tracking progress
        'meal_prep_variety',       # Wants to expand food options, meal planning
        'work_life_balance',       # Shift work, Spanish bosses, corporate demands
        'family_man',              # Kids sport, family eating clean together
        'goal_oriented',           # Specific weight targets, training consistency
        'outdoor_activities',      # 100km bike ride, physical challenges
        'macro_tracking',          # Detailed food logging, calorie awareness
        'strength_training',       # Gym consistency, form improvement
        'practical_solutions',     # Home gym alternatives, busy schedule
        'progress_photos',         # Visual tracking, belt measurements
        'routine_structure',       # Needs consistency, struggles with roster changes
        'achievement_focused'      # Celebrates milestones, pushes personal limits
    ]

    # His specific phrases and language patterns
    specific_phrases = [
        "mate",                    # Frequent use of "mate"
        "Hey mate",                # Standard greeting
        "sounds good",             # Agreement/enthusiasm
        "sweet",                   # Approval/satisfaction
        "lol",                     # Light humor
        "❤️",                      # Occasional heart emoji
        "keen",                    # Enthusiasm/motivation
        "all good",                # Easy-going acceptance
        "to easy",                 # "too easy" - confident agreement
        "nice one",                # Approval/encouragement
        "yeah mate",               # Confirmation
        "that's cool",             # Acceptance/approval
        "I'm down to",             # Weight progress reporting
        "pushing for",             # Goal-oriented language
        "smash it",                # Motivation/determination
        "back at it",              # Returning to routine
        "solid effort",            # Acknowledging good work
    ]

    return MemberPersonality(
        ig_username="shane",
        # Goal-focused, practical approach
        communication_style="practical_achiever",
        interests=interests,
        response_preferences="progress_acknowledgment",    # Wants recognition of efforts
        # "nice one mate" but keeps pushing
        celebration_style="modest_determined",
        # Works with Shannon to find answers
        problem_solving_style="collaborative_solutions",
        specific_phrases=specific_phrases,
        conversation_history_patterns=communication_patterns
    )


def analyze_shane_personality():
    """Analyze Shane's unique communication traits"""

    print("🔍 SHANE'S PERSONALITY ANALYSIS")
    print("="*50)

    traits = {
        "Communication Style": "Practical Achiever - Goal-focused with steady progress mindset",
        "Engagement Pattern": "Consistent & Responsive - Reliable check-ins and updates",
        "Motivation Style": "Progress-driven - Loves seeing measurable improvements",
        "Problem Approach": "Collaborative - Works with Shannon to find practical solutions",
        "Sharing Pattern": "Achievement-focused - Reports progress, asks specific questions",
        "Humor Style": "Gentle & Self-aware - Light humor without being over-the-top",
        "Goal Orientation": "Specific targets - 86kg, consistent training, macro tracking",
        "Language Pattern": "Aussie mate culture - 'mate', 'keen', 'sweet', respectful tone"
    }

    for aspect, description in traits.items():
        print(f"📊 {aspect}: {description}")

    print(f"\n🎯 KEY SHANE PATTERNS:")
    print(f"- Celebrates progress but immediately sets next goals")
    print(f"- Shares challenges honestly but stays solution-focused")
    print(f"- Values practical advice over theoretical discussions")
    print(f"- Consistent routine is crucial for his success")
    print(f"- Family-oriented (whole family eating clean, kids sport)")
    print(f"- Work-life balance challenges (shift work, travel, corporate demands)")


def compare_all_four_members():
    """Compare Shane with Sabrina, StaaCi, and Kristy"""

    shane = create_shane_personality()

    from scripts.personalized_member_prompting import create_sabrina_personality
    from scripts.add_staaci_personality import create_staaci_personality
    from scripts.add_kristy_personality import create_kristy_personality

    sabrina = create_sabrina_personality()
    staaci = create_staaci_personality()
    kristy = create_kristy_personality()

    print(f"\n🔍 FOUR-WAY MEMBER COMPARISON")
    print("="*70)

    comparison = {
        "Communication Style": {
            "Sabrina": sabrina.communication_style,
            "StaaCi": staaci.communication_style,
            "Kristy": kristy.communication_style,
            "Shane": shane.communication_style
        },
        "Response Preferences": {
            "Sabrina": sabrina.response_preferences,
            "StaaCi": staaci.response_preferences,
            "Kristy": kristy.response_preferences,
            "Shane": shane.response_preferences
        },
        "Celebration Style": {
            "Sabrina": sabrina.celebration_style,
            "StaaCi": staaci.celebration_style,
            "Kristy": kristy.celebration_style,
            "Shane": shane.celebration_style
        },
        "Problem Solving": {
            "Sabrina": sabrina.problem_solving_style,
            "StaaCi": staaci.problem_solving_style,
            "Kristy": kristy.problem_solving_style,
            "Shane": shane.problem_solving_style
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
    print(f"Shane → Supportive/Progress-focused: 'Nice one mate! You're killing it. Let's push for another 500g this week!'")


def add_shane_to_database():
    """Add Shane's profile to the member personalities database"""

    manager = MemberPersonalityManager()
    shane_personality = create_shane_personality()

    # Store in database
    manager._store_personality_profile(shane_personality)
    print("✅ Added Shane's personality profile to database")

    return shane_personality


def test_shane_personalized_scenarios():
    """Test Shane's personalized response scenarios"""

    test_scenarios = [
        {
            'message': 'Hey mate, down to 88kg this week! Belt is down two holes in the last 4 weeks',
            'expected_personalized': 'Enthusiastic progress acknowledgment + next goal setting',
            'context': 'Progress reporting with specific measurements'
        },
        {
            'message': 'This week was shit, pumped by work and Spanish bosses. On Muscle Chef meals to keep control',
            'expected_personalized': 'Understanding of work challenges + praise for maintaining control',
            'context': 'Work-life balance struggle with practical solution'
        },
        {
            'message': 'Do I keep the same calories and macros? Starting to get over the same two meals',
            'expected_personalized': 'Direct answer to macro question + meal variety solution',
            'context': 'Practical nutrition question with boredom issue'
        },
        {
            'message': 'Can we put these two exercises back in? They hurt but were good',
            'expected_personalized': 'Immediate action + acknowledgment of his pain tolerance',
            'context': 'Specific program request with reasoning'
        },
        {
            'message': 'I\'m keen this week to smash it, planning to train every night',
            'expected_personalized': 'Match his motivation + provide structure/support',
            'context': 'High motivation expression with commitment'
        }
    ]

    print(f"\n{'='*60}")
    print(f"SHANE PERSONALIZED RESPONSE SCENARIOS")
    print(f"{'='*60}")

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. SCENARIO: {scenario['context']}")
        print(f"Message: \"{scenario['message']}\"")
        print(f"Expected Style: {scenario['expected_personalized']}")
        print(f"Generic would be: Standard motivational response without progress focus")
        print("-" * 50)


def main():
    """Main function to add Shane and demonstrate his unique personality"""

    print("🚀 ADDING SHANE TO PERSONALIZED MEMBER SYSTEM")
    print("="*50)

    # 1. Analyze Shane's personality
    print("\n1. Analyzing Shane's personality...")
    analyze_shane_personality()

    # 2. Compare with other members
    print("\n2. Comparing with all other members...")
    compare_all_four_members()

    # 3. Add to database
    print("\n3. Adding Shane to database...")
    add_shane_to_database()

    # 4. Test scenarios
    print("\n4. Testing personalized response scenarios...")
    test_shane_personalized_scenarios()

    print(f"\n🎉 SHANE PERSONALITY PROFILE CREATED!")
    print(f"\n📋 What This Enables:")
    print(f"- Shannon will match Shane's practical, achievement-focused communication")
    print(f"- Responses acknowledge his progress and immediately set next goals")
    print(f"- Problem-solving approach respects his work-life balance challenges")
    print(f"- Celebration style matches his modest but determined personality")
    print(f"- Language matches his Aussie mate culture and respectful tone")

    print(f"\n📊 Now You Have FOUR Distinct Member Personalities:")
    print(f"- Sabrina: Technical/Direct (wants specific answers)")
    print(f"- StaaCi: Storyteller/Casual (loves personal connection)")
    print(f"- Kristy: Witty/Pragmatic (appreciates smart humor + practical advice)")
    print(f"- Shane: Practical/Achiever (progress-focused + collaborative solutions)")
    print(f"- System automatically adapts to each member's unique communication style!")


if __name__ == "__main__":
    main()
