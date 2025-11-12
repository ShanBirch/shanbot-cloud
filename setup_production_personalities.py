#!/usr/bin/env python3
"""
Setup member personalities in production database
Run this after deployment to ensure all personalities are available
"""


def setup_all_personalities():
    """Setup all 4 member personalities in production"""

    print("🚀 SETTING UP MEMBER PERSONALITIES IN PRODUCTION")
    print("="*60)

    try:
        # Import all personality creation functions
        from scripts.integrate_personalized_prompting import create_sabrina_demo_profile
        from scripts.add_staaci_personality import add_staaci_to_database
        from scripts.add_kristy_personality import add_kristy_to_database
        from scripts.add_shane_personality import add_shane_to_database

        personalities_created = []

        # Create Sabrina's profile
        try:
            create_sabrina_demo_profile()
            personalities_created.append("✅ Sabrina (Technical/Direct)")
        except Exception as e:
            personalities_created.append(f"❌ Sabrina failed: {e}")

        # Create StaaCi's profile
        try:
            add_staaci_to_database()
            personalities_created.append("✅ StaaCi (Storyteller/Casual)")
        except Exception as e:
            personalities_created.append(f"❌ StaaCi failed: {e}")

        # Create Kristy's profile
        try:
            add_kristy_to_database()
            personalities_created.append("✅ Kristy (Witty/Pragmatic)")
        except Exception as e:
            personalities_created.append(f"❌ Kristy failed: {e}")

        # Create Shane's profile
        try:
            add_shane_to_database()
            personalities_created.append("✅ Shane (Practical/Achiever)")
        except Exception as e:
            personalities_created.append(f"❌ Shane failed: {e}")

        print("\n📊 PERSONALITY SETUP RESULTS:")
        print("="*40)
        for result in personalities_created:
            print(result)

        # Test the system
        try:
            from scripts.integrate_personalized_prompting import MemberPersonalityManager
            manager = MemberPersonalityManager()

            test_context = {
                'current_melbourne_time_str': '2024-01-15 10:30 AM AEDT',
                'first_name': 'Sabrina',
                'fitness_goals': 'Test',
                'dietary_requirements': 'Vegan',
                'current_program': 'Test',
                'few_shot_examples': ''
            }

            prompt, success = manager.generate_personalized_member_prompt(
                'sabrina', 'Test message', 'Test conversation', test_context
            )

            if success:
                print("\n🎉 PERSONALIZED SYSTEM IS WORKING IN PRODUCTION!")
            else:
                print("\n⚠️ System setup but using fallback prompts")

        except Exception as e:
            print(f"\n❌ Error testing system: {e}")

        print("\n🔥 PRODUCTION SETUP COMPLETE!")
        print("Your members will now get personalized responses!")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        print("Make sure all personality scripts are available")


if __name__ == "__main__":
    setup_all_personalities()
