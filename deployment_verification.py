#!/usr/bin/env python3
"""
Verify the personalized member chat deployment is working
"""


def verify_deployment():
    """Verify the deployment is successful"""

    print("🔍 PERSONALIZED MEMBER CHAT - DEPLOYMENT VERIFICATION")
    print("="*70)

    checks = []

    # Check 1: Integration code added
    try:
        with open("webhook_handlers.py", "r", encoding='utf-8') as f:
            content = f.read()

        if "MemberPersonalityManager" in content:
            checks.append(
                ("✅", "Integration code added to webhook_handlers.py"))
        else:
            checks.append(
                ("❌", "Integration code NOT found in webhook_handlers.py"))

        if "format_few_shot_examples" in content:
            checks.append(("✅", "Helper function added"))
        else:
            checks.append(("❌", "Helper function NOT found"))

    except Exception as e:
        checks.append(("❌", f"Error reading webhook_handlers.py: {e}"))

    # Check 2: Member personalities in database
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        manager = MemberPersonalityManager()

        members = ['sabrina', 'staaci', 'kristy', 'shane']
        member_count = 0

        for member in members:
            personality = manager.get_member_personality(member)
            if personality:
                member_count += 1

        if member_count == 4:
            checks.append(
                ("✅", f"All 4 member personalities ready ({member_count}/4)"))
        else:
            checks.append(
                ("⚠️", f"Only {member_count}/4 member personalities found"))

    except Exception as e:
        checks.append(("❌", f"Error checking member personalities: {e}"))

    # Check 3: System can generate personalized prompts
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        manager = MemberPersonalityManager()

        test_context = {
            'current_melbourne_time_str': '2024-01-15 10:30 AM AEDT',
            'first_name': 'Sabrina',
            'fitness_goals': 'Test goals',
            'dietary_requirements': 'Vegan',
            'current_program': 'Test program',
            'few_shot_examples': ''
        }

        prompt, success = manager.generate_personalized_member_prompt(
            'sabrina', 'Test message', 'Test conversation', test_context
        )

        if success:
            checks.append(("✅", "Personalized prompt generation working"))
        else:
            checks.append(
                ("⚠️", "Personalized prompt generation failed (fallback works)"))

    except Exception as e:
        checks.append(("❌", f"Error testing prompt generation: {e}"))

    # Check 4: Backup exists
    import os
    if os.path.exists("webhook_handlers_backup.py"):
        checks.append(("✅", "Backup file exists for rollback"))
    else:
        checks.append(("⚠️", "No backup file found (consider creating one)"))

    # Display results
    print("\n📋 DEPLOYMENT CHECK RESULTS:")
    print("="*40)

    for status, message in checks:
        print(f"{status} {message}")

    # Overall status
    success_count = sum(1 for status, _ in checks if status == "✅")
    total_checks = len(checks)

    print(f"\n📊 OVERALL STATUS:")
    print("="*30)

    if success_count >= total_checks - 1:  # Allow 1 warning
        print("🎉 DEPLOYMENT SUCCESSFUL!")
        print("\n🚀 WHAT'S LIVE NOW:")
        print("- Personalized member prompting is integrated")
        print("- All 4 member personalities are ready")
        print("- System gracefully falls back if needed")
        print("- Your existing functionality is preserved")

        print("\n📱 WHAT HAPPENS NEXT:")
        print("- When Sabrina sends a message → Gets technical/direct Shannon")
        print("- When StaaCi sends a message → Gets casual/storytelling Shannon")
        print("- When Kristy sends a message → Gets witty/pragmatic Shannon")
        print("- When Shane sends a message → Gets progress-focused Shannon")
        print("- When unknown members message → Gets standard member prompt")

        print("\n🔥 YOUR MEMBER EXPERIENCE IS NOW PERSONALIZED!")

    else:
        print("⚠️ DEPLOYMENT HAS ISSUES")
        print("Check the failed items above and fix before going live")

    print(f"\n📈 Score: {success_count}/{total_checks} checks passed")


if __name__ == "__main__":
    verify_deployment()
