#!/usr/bin/env python3
"""
Integration patch to add personalized member prompting to existing webhook system
This shows exactly what to add to your current webhook_handlers.py
"""


def show_current_member_prompt_location():
    """Show where the current member prompt is built"""

    current_code = '''
    # CURRENT CODE in webhook_handlers.py around line 1867:
    
    if is_paying_client or trial_start_date_exists or client_status in ["active client", "trial", "paying client"]:
        base_prompt_template = prompts.MEMBER_CONVERSATION_PROMPT_TEMPLATE  # <-- THIS IS WHERE TO ADD PERSONALIZATION
        prompt_type = "member_chat"
        logger.info(f"Using MEMBER_CONVERSATION_PROMPT_TEMPLATE for member: {full_name}")
    '''

    print("🔍 CURRENT MEMBER PROMPT LOCATION:")
    print("="*50)
    print(current_code)


def show_personalized_integration():
    """Show the exact code to add personalized prompting"""

    integration_code = '''
# ADD THIS TO webhook_handlers.py build_member_chat_prompt function:
# Replace the existing member prompt section with this:

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
    '''

    print("\n💻 INTEGRATION CODE:")
    print("="*50)
    print(integration_code)


def show_helper_function():
    """Show the helper function to add"""

    helper_code = '''
# ADD THIS HELPER FUNCTION to webhook_handlers.py (near the top with other helper functions):

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

    print("\n🔧 HELPER FUNCTION:")
    print("="*50)
    print(helper_code)


def test_staaci_recognition():
    """Test that StaaCi will be recognized"""

    print("\n🧪 TESTING STAACI RECOGNITION:")
    print("="*50)

    # Test the personalized system
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager

        manager = MemberPersonalityManager()

        # Check if StaaCi's profile exists
        staaci_personality = manager.get_member_personality('staaci')

        if staaci_personality:
            print("✅ StaaCi's personality profile found in database!")
            print(
                f"   - Communication Style: {staaci_personality.communication_style}")
            print(
                f"   - Celebration Style: {staaci_personality.celebration_style}")
            print(
                f"   - Key Interests: {', '.join(staaci_personality.interests[:3])}...")

            # Test a sample message
            test_context = {
                'current_melbourne_time_str': '2024-01-15 10:30 AM AEDT',
                'first_name': 'StaaCi',
                'fitness_goals': 'Lose 5-10kg and tone up',
                'dietary_requirements': 'Vegan',
                'current_program': 'Vegan Challenge',
                'few_shot_examples': ''
            }

            test_message = "Had the tofu meal again, it's growing on me!"

            prompt, success = manager.generate_personalized_member_prompt(
                'staaci', test_message, 'Previous conversation...', test_context
            )

            if success:
                print("\n✅ PERSONALIZED PROMPT GENERATION WORKS!")
                print("StaaCi will get personalized responses! 🎉")
            else:
                print("\n❌ Personalized prompt generation failed")
        else:
            print("❌ StaaCi's personality profile NOT found")
            print("   Run: python scripts/add_staaci_personality.py")

    except Exception as e:
        print(f"❌ Error testing StaaCi recognition: {e}")


def show_deployment_steps():
    """Show the exact deployment steps"""

    steps = '''
🚀 DEPLOYMENT STEPS TO LINK STAACI TO WEBHOOK:

1. ADD PERSONALIZATION TO webhook_handlers.py:
   - Find the build_member_chat_prompt function (around line 1867)
   - Replace the member prompt section with the integration code above
   - Add the helper function for few-shot formatting

2. TEST THE INTEGRATION:
   - Send a test message from StaaCi's Instagram
   - Check logs for "✅ Using personalized prompt for staaci"
   - Verify she gets casual/storytelling responses

3. VERIFY OTHER MEMBERS:
   - Test with Sabrina → should get technical/direct responses
   - Test with unknown member → should fall back to general prompt
   - System learns automatically from new conversations

4. MONITOR LOGS:
   - Look for "🎯 Attempting personalized prompt for [username]"
   - Watch for successful personalization vs fallbacks
   - Track new personality profiles being created

📋 AFTER DEPLOYMENT:
✅ StaaCi sends message → Gets casual, storytelling Shannon response
✅ Sabrina sends message → Gets technical, direct Shannon response  
✅ New member sends message → System analyzes and creates profile
✅ All existing functionality continues working unchanged
    '''

    print("\n📋 DEPLOYMENT STEPS:")
    print("="*50)
    print(steps)


def main():
    """Show complete integration guide"""

    print("🔗 LINKING STAACI TO YOUR WEBHOOK SYSTEM")
    print("="*60)

    # 1. Show current location
    show_current_member_prompt_location()

    # 2. Show integration code
    show_personalized_integration()

    # 3. Show helper function
    show_helper_function()

    # 4. Test StaaCi recognition
    test_staaci_recognition()

    # 5. Show deployment steps
    show_deployment_steps()

    print("\n🎉 RESULT:")
    print("="*20)
    print("After this integration:")
    print("- StaaCi gets personalized casual/storytelling responses")
    print("- Sabrina gets personalized technical/direct responses")
    print("- New members automatically get profiles created")
    print("- System gracefully falls back when needed")
    print("- All existing functionality continues working")


if __name__ == "__main__":
    main()
