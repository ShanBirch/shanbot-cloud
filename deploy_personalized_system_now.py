#!/usr/bin/env python3
"""
Deploy Personalized Member Chat System - FINAL DEPLOYMENT
Complete integration guide with all 4 member personalities ready
"""

import os
from pathlib import Path


def show_four_member_system():
    """Show the complete four-member personality system"""

    print("🎯 COMPLETE PERSONALIZED MEMBER SYSTEM")
    print("="*60)

    members = {
        "Sabrina": {
            "style": "Technical/Direct",
            "example": "That's 1 tbsp, here's the exact macro breakdown",
            "triggers": "Asks specific questions, wants precise answers",
            "celebration": "Understated - 'Good one!'"
        },
        "StaaCi": {
            "style": "Storyteller/Casual",
            "example": "Fk yeah boi! That meal's growing on ya hey? Love it!",
            "triggers": "Shares personal stories, loves connection",
            "celebration": "Enthusiastic - 'Fk yeah!'"
        },
        "Kristy": {
            "style": "Witty/Pragmatic",
            "example": "Fair play! That's solid progress. What's next?",
            "triggers": "Self-deprecating humor, practical questions",
            "celebration": "Understated sarcasm - 'yeooooww'"
        },
        "Shane": {
            "style": "Practical/Achiever",
            "example": "Nice one mate! You're killing it. Let's push for another 500g this week!",
            "triggers": "Progress reports, goal-oriented language",
            "celebration": "Modest determination - 'nice one mate'"
        }
    }

    for name, details in members.items():
        print(f"\n👤 {name}:")
        print(f"   Style: {details['style']}")
        print(f"   Example: \"{details['example']}\"")
        print(f"   Triggers: {details['triggers']}")
        print(f"   Celebration: {details['celebration']}")


def create_webhook_integration_code():
    """Create the exact code to add to webhook_handlers.py"""

    integration_code = '''
# =============================================================================
# PERSONALIZED MEMBER PROMPTING INTEGRATION
# Add this to webhook_handlers.py build_member_chat_prompt function
# Replace the existing member prompt section (around line 1867)
# =============================================================================

if is_paying_client or trial_start_date_exists or client_status in ["active client", "trial", "paying client"]:
    
    # NEW: TRY PERSONALIZED PROMPTING FIRST
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        
        ig_username = client_data.get('ig_username', '')
        if ig_username:
            logger.info(f"🎯 Attempting personalized prompt for {ig_username}")
            
            manager = MemberPersonalityManager()
            
            # Build context for personalized prompting
            context = {
                'current_melbourne_time_str': get_melbourne_time_str(),
                'first_name': full_name or ig_username,
                'fitness_goals': client_data.get('fitness_goals', ''),
                'dietary_requirements': client_data.get('dietary_requirements', ''),
                'current_program': client_data.get('current_program', ''),
                'few_shot_examples': format_few_shot_examples(few_shot_examples) if few_shot_examples else ''
            }
            
            # Try personalized prompting
            personalized_prompt, success = manager.generate_personalized_member_prompt(
                ig_username, current_message, full_conversation_string, context
            )
            
            if success:
                logger.info(f"✅ Using personalized prompt for {ig_username}")
                return personalized_prompt, "personalized_member_chat"
            else:
                logger.info(f"⚠️ Personalized prompting unavailable for {ig_username}, using fallback")
    
    except Exception as e:
        logger.warning(f"⚠️ Personalized prompting failed for {ig_username}: {e}")
    
    # FALLBACK: Use existing member prompt (your current code continues unchanged)
    base_prompt_template = prompts.MEMBER_CONVERSATION_PROMPT_TEMPLATE
    prompt_type = "member_chat"
    logger.info(f"Using MEMBER_CONVERSATION_PROMPT_TEMPLATE for member: {full_name}")

# =============================================================================
# HELPER FUNCTION - Add this near the top of webhook_handlers.py
# =============================================================================

def format_few_shot_examples(few_shot_examples: List[Dict[str, str]]) -> str:
    """Format few-shot examples for prompt injection"""
    if not few_shot_examples:
        return ""
    
    formatted = "\\n\\nHere are examples of how Shannon responds to members:\\n"
    for example in few_shot_examples[-5:]:  # Use last 5 examples
        user_msg = example.get('user_message', '')
        shannon_response = example.get('shannon_response', '')
        if user_msg and shannon_response:
            formatted += f"\\nMember: {user_msg}\\nShannon: {shannon_response}\\n"
    
    return formatted
'''

    return integration_code


def create_deployment_checklist():
    """Create final deployment checklist"""

    checklist = """
🚀 PERSONALIZED MEMBER CHAT - DEPLOYMENT CHECKLIST
================================================

✅ PREPARATION COMPLETE:
□ 4 member personalities created (Sabrina, StaaCi, Kristy, Shane)
□ Database tables created and verified
□ Personalized prompting engine tested
□ Integration code prepared
□ Fallback system tested

🔧 DEPLOYMENT STEPS:

1. BACKUP EXISTING CODE:
   □ Copy webhook_handlers.py to webhook_handlers_backup.py
   □ Save current working system before changes

2. ADD HELPER FUNCTION:
   □ Add format_few_shot_examples() near top of webhook_handlers.py
   □ This handles few-shot example formatting

3. REPLACE MEMBER PROMPT SECTION:
   □ Find build_member_chat_prompt function (around line 1867)
   □ Replace the member prompt section with personalized code
   □ Keep all existing fallback logic intact

4. TEST DEPLOYMENT:
   □ Send test message from Sabrina → check for technical response
   □ Send test message from StaaCi → check for casual response  
   □ Send test message from Kristy → check for witty response
   □ Send test message from Shane → check for progress-focused response
   □ Send test message from unknown member → check fallback works

5. MONITOR LOGS:
   □ Watch for "🎯 Attempting personalized prompt for [username]"
   □ Check for "✅ Using personalized prompt for [username]" 
   □ Verify fallback messages: "⚠️ Personalized prompting unavailable"
   □ No errors or crashes in webhook processing

📊 SUCCESS INDICATORS:
□ Sabrina gets technical, direct responses
□ StaaCi gets casual, storytelling responses
□ Kristy gets witty, pragmatic responses  
□ Shane gets progress-focused, mate-culture responses
□ Unknown members get generic member responses (fallback)
□ Zero webhook failures or crashes
□ Response times stay under 3 seconds

🔄 ROLLBACK PLAN (if needed):
□ Restore webhook_handlers_backup.py
□ System returns to existing member prompts
□ All functionality continues as before

⚠️ IMPORTANT NOTES:
- The system is designed to be SAFE - if anything fails, it uses existing prompts
- Personalization only affects KNOWN members with profiles
- All new members still get generic prompts until profiles are created
- The system learns and improves automatically over time
"""

    return checklist


def test_all_personalities():
    """Test that all 4 personalities are in the database"""

    print("\n🧪 TESTING ALL MEMBER PERSONALITIES:")
    print("="*50)

    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager

        manager = MemberPersonalityManager()

        members = ['sabrina', 'staaci', 'kristy', 'shane']
        all_ready = True

        for member in members:
            personality = manager.get_member_personality(member)
            if personality:
                print(f"✅ {member.title()}: {personality.communication_style}")
            else:
                print(f"❌ {member.title()}: Profile not found")
                all_ready = False

        if all_ready:
            print(f"\n🎉 ALL 4 MEMBER PERSONALITIES READY FOR DEPLOYMENT!")
            return True
        else:
            print(f"\n❌ Some personalities missing. Run member creation scripts first.")
            return False

    except Exception as e:
        print(f"❌ Error testing personalities: {e}")
        return False


def show_expected_results():
    """Show what users can expect after deployment"""

    results = """
🎯 EXPECTED RESULTS AFTER DEPLOYMENT
===================================

📱 SABRINA SENDS: "For the batch cooking, is this screenshot for 3 serves or 1?"
🤖 SHANNON RESPONDS: "That's for 3 serves mate. Each portion is about 180g protein, 45g carbs."
💡 STYLE: Technical, direct, specific numbers

📱 STAACI SENDS: "Had the tofu meal again, it's growing on me! Dogs are going crazy today lol"  
🤖 SHANNON RESPONDS: "Fk yeah boi! Love that it's growing on ya! Haha the dogs keeping you active hey? ❤️"
💡 STYLE: Casual, storytelling, personal connection

📱 KRISTY SENDS: "I'm anxious as st today, can't get out of bed"
🤖 SHANNON RESPONDS: "Fair play, rough days happen. Get some water into ya, maybe just a walk? ❤️"
💡 STYLE: Witty, pragmatic, understated support

📱 SHANE SENDS: "Hey mate, down to 88kg this week! Belt is down two holes"
🤖 SHANNON RESPONDS: "Nice one mate! You're killing it! Let's push for another 500g this week. Keep that momentum! 💪"
💡 STYLE: Progress-focused, collaborative, achievement celebration

📱 NEW MEMBER SENDS: "How should I track my calories?"
🤖 SHANNON RESPONDS: [Generic member prompt - no personalization yet]
💡 STYLE: Standard member response until profile is created
"""

    return results


def main():
    """Complete deployment guide"""

    print("🚀 PERSONALIZED MEMBER CHAT SYSTEM - FINAL DEPLOYMENT")
    print("="*70)

    # 1. Show the complete system
    show_four_member_system()

    # 2. Test all personalities are ready
    all_ready = test_all_personalities()

    if not all_ready:
        print("\n❌ Cannot deploy - some personalities missing")
        return

    # 3. Show integration code
    print(f"\n💻 INTEGRATION CODE:")
    print("="*30)
    integration_code = create_webhook_integration_code()

    with open("webhook_integration_code.txt", "w", encoding='utf-8') as f:
        f.write(integration_code)
    print("✅ Created webhook_integration_code.txt")

    # 4. Create deployment checklist
    checklist = create_deployment_checklist()

    with open("final_deployment_checklist.md", "w", encoding='utf-8') as f:
        f.write(checklist)
    print("✅ Created final_deployment_checklist.md")

    # 5. Show expected results
    results = show_expected_results()

    with open("expected_results.md", "w", encoding='utf-8') as f:
        f.write(results)
    print("✅ Created expected_results.md")

    print(f"\n🎉 DEPLOYMENT PACKAGE COMPLETE!")
    print("="*40)

    print(f"\n📁 Files Created:")
    print(f"- webhook_integration_code.txt     (Exact code to add)")
    print(f"- final_deployment_checklist.md    (Step-by-step guide)")
    print(f"- expected_results.md              (What to expect)")

    print(f"\n🚀 READY TO DEPLOY:")
    print(f"1. Follow the deployment checklist")
    print(f"2. Add the integration code to webhook_handlers.py")
    print(f"3. Test with your 4 members")
    print(f"4. Watch the magic happen!")

    print(f"\n💫 WHAT YOU'LL GET:")
    print(f"- Sabrina gets technical/direct Shannon")
    print(f"- StaaCi gets casual/storytelling Shannon")
    print(f"- Kristy gets witty/pragmatic Shannon")
    print(f"- Shane gets progress-focused/mate Shannon")
    print(f"- Each member gets the perfect version of you for them!")

    print(f"\n🔥 YOU'RE READY TO REVOLUTIONIZE YOUR MEMBER EXPERIENCE!")


if __name__ == "__main__":
    main()
