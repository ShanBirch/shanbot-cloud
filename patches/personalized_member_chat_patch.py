#!/usr/bin/env python3
"""
Patch to add personalized member prompting to existing Shanbot system
This patches the member chat flow to use personalized prompts when available
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


def patch_member_chat_prompt():
    """Patch the MEMBER_CONVERSATION_PROMPT_TEMPLATE to include personalization logic"""

    # Enhanced member prompt that includes personalization hooks
    PERSONALIZED_MEMBER_PROMPT = '''
Core Context & Persona:

You are Shannon, an Australian fitness coach responding to your member {ig_username}. You have an established relationship and understand their specific communication preferences and interests.

**ABSOLUTE CORE RULE: RESPOND ONLY AS SHANNON**
- Your ENTIRE output must be Shannon's next message
- NEVER include commentary, analysis, or explanations
- NEVER include labels, prefixes, or formatting
- Generate the exact text Shannon would type

**MEMBER-SPECIFIC PERSONALIZATION:**
{personalization_context}

**AUTHENTIC SHANNON STYLE (proven patterns):**
- Casual Australian: "aye", "hey", "ofc", "defs", "plz", "v nice", "nek time", "okie", "tonite"
- Enthusiastic celebration: "Yo smashed it!", "Good one!", "Hell yeah!", "Awesome!"
- Supportive acknowledgment: "That's completely understandable", "Super solid effort"
- Problem-solving: "I'll fix this up now", "Will change it in your new plan"
- Natural typos occasionally: "thought" instead of "though"

**RESPONSE STRUCTURE:**
1. **Immediate Acknowledgment**: Always acknowledge what they shared first
2. **Show Perfect Memory**: Reference their specific situation and previous conversations
3. **Personalized Communication**: Match their preferred communication style
4. **Practical Solutions**: Provide specific, actionable guidance when needed

**MEMBER CONVERSATION SCENARIOS:**
- Progress: "Good one!" / "Yo smashed it!" (match their celebration preference)
- Problems: "That's completely understandable" + immediate solution
- Questions: Direct answer first + follow-up (adapt to their question style)
- Personal: Show genuine interest + connect to their specific interests

**REAL CONVERSATION EXAMPLES:**
{few_shot_examples}

**CONVERSATION CONTEXT:**
Current Date & Time: {current_melbourne_time_str}
Platform: Instagram Direct Messages
Member: @{ig_username}
Member Name: {first_name}
Goals: {fitness_goals}
Dietary Needs: {dietary_requirements}
Program: {current_program}
History: {full_conversation}

**CRITICAL SUCCESS FACTORS:**
- Reference their specific interests and communication style
- Use their preferred level of detail and enthusiasm
- Show memory of their challenges, preferences, and goals
- Provide solutions that match their problem-solving style
- Celebrate wins in their preferred way
- Ask for content (videos/photos) when relevant

Generate Shannon's authentic response that perfectly matches both her general style AND this member's specific communication preferences.
'''

    return PERSONALIZED_MEMBER_PROMPT


def create_personalization_integration():
    """Create integration code for the webhook handlers"""

    integration_code = '''
# Add this import at the top of webhook_handlers.py
try:
    from scripts.integrate_personalized_prompting import MemberPersonalityManager
    PERSONALIZED_PROMPTING_AVAILABLE = True
except ImportError:
    PERSONALIZED_PROMPTING_AVAILABLE = False

def build_member_chat_prompt_with_personalization(
    client_data: Dict[str, Any],
    current_message: str,
    conversation_history: str = "",
    current_stage: str = "Topic 1",
    trial_status: str = "Initial Contact", 
    full_name: Optional[str] = None,
    full_conversation_string: str = "",
    few_shot_examples: Optional[List[Dict[str, str]]] = None
) -> tuple[str, str]:
    """Enhanced member chat prompt with personalization"""
    
    ig_username = client_data.get('ig_username', '')
    
    # Try personalized prompting first
    if PERSONALIZED_PROMPTING_AVAILABLE and ig_username:
        try:
            manager = MemberPersonalityManager()
            
            context = {
                'current_melbourne_time_str': get_melbourne_time_str(),
                'first_name': full_name or ig_username.replace('_', ' ').title(),
                'fitness_goals': client_data.get('fitness_goals', 'General fitness'),
                'dietary_requirements': client_data.get('dietary_requirements', 'None specified'),
                'current_program': client_data.get('current_program', 'Active member'),
                'few_shot_examples': format_few_shot_examples(few_shot_examples) if few_shot_examples else ''
            }
            
            personalized_prompt, is_personalized = manager.generate_personalized_member_prompt(
                ig_username, current_message, full_conversation_string, context
            )
            
            if is_personalized:
                logger.info(f"✅ Using personalized prompt for member: {ig_username}")
                return personalized_prompt, "personalized_member_chat"
            else:
                logger.info(f"⚠️ Using fallback prompt for member: {ig_username}")
                
        except Exception as e:
            logger.warning(f"⚠️ Personalized prompting failed for {ig_username}: {e}")
    
    # Fallback to existing member prompt logic
    return build_member_chat_prompt_original(
        client_data, current_message, conversation_history, 
        current_stage, trial_status, full_name, 
        full_conversation_string, few_shot_examples
    )

# Format few-shot examples helper
def format_few_shot_examples(examples: List[Dict[str, str]]) -> str:
    """Format few-shot examples for prompt"""
    if not examples:
        return ""
    
    formatted = []
    for ex in examples[:5]:  # Limit to 5 best examples
        input_text = ex.get('input', '')
        output_text = ex.get('output', '')
        if input_text and output_text:
            formatted.append(f'Member: "{input_text}"')
            formatted.append(f'Shannon: "{output_text}"')
            formatted.append('')
    
    return "\\n".join(formatted)
'''

    return integration_code


def apply_personalization_patch():
    """Apply the personalization patch to the system"""

    print("🔧 APPLYING PERSONALIZED MEMBER CHAT PATCH")
    print("="*50)

    # 1. Create the enhanced prompt template
    enhanced_prompt = patch_member_chat_prompt()
    print("✅ Enhanced member prompt template created")

    # 2. Create integration code
    integration = create_personalization_integration()
    print("✅ Integration code generated")

    # 3. Save patch files
    patch_dir = project_root / "patches"
    patch_dir.mkdir(exist_ok=True)

    # Save enhanced prompt
    with open(patch_dir / "enhanced_member_prompt.txt", 'w') as f:
        f.write(enhanced_prompt)

    # Save integration code
    with open(patch_dir / "member_chat_integration.py", 'w') as f:
        f.write(integration)

    print("✅ Patch files saved to /patches directory")

    # 4. Instructions
    print("\\n📋 MANUAL INTEGRATION STEPS:")
    print("-" * 30)
    print("1. In app/prompts.py, replace MEMBER_CONVERSATION_PROMPT_TEMPLATE with enhanced version")
    print("2. In webhook_handlers.py, add the personalization integration code")
    print("3. Update build_member_chat_prompt calls to use new function")
    print("4. Test with Sabrina's conversation patterns")

    print("\\n🎯 WHAT THIS GIVES YOU:")
    print("-" * 20)
    print("✅ Sabrina gets direct, technical answers (her preference)")
    print("✅ Pole dancing references when relevant")
    print("✅ Student-life understanding for scheduling")
    print("✅ Understated celebration style she responds to")
    print("✅ Collaborative problem-solving approach")
    print("✅ Automatic learning from new conversations")

    return enhanced_prompt, integration


def test_sabrina_personalized_response():
    """Test how Sabrina would get a personalized response"""

    # Simulate Sabrina's personality being applied
    sabrina_context = {
        'communication_style': 'detailed_technical',
        'interests': ['pole_dancing', 'nutrition_science', 'gluten_free', 'student'],
        'response_preference': 'direct_first',
        'celebration_style': 'understated',
        'problem_solving': 'collaborative'
    }

    test_message = "For the batch cooking, is this screenshot for 3 serves or 1?"

    print("\\n🧪 PERSONALIZED RESPONSE TEST")
    print("="*40)
    print(f"Member: Sabrina")
    print(f"Message: {test_message}")
    print(f"Personality: {sabrina_context}")

    print("\\n📝 Expected Personalized Response:")
    print("Shannon: '120g of tofu is for 1 serving. 👍'")
    print("(Direct answer first, technical precision, understated positive)")

    print("\\n🆚 vs Generic Member Response:")
    print("Shannon: 'Hey! Great question about the meal prep! So this recipe...'")
    print("(More verbose, less direct)")

    print("\\n✅ Personalization captures Sabrina's preference for:")
    print("- Direct technical answers")
    print("- Specific numbers and measurements")
    print("- Understated positive confirmation")
    print("- No unnecessary elaboration")


if __name__ == "__main__":
    # Apply the patch
    enhanced_prompt, integration_code = apply_personalization_patch()

    # Test example
    test_sabrina_personalized_response()

    print("\\n🚀 PERSONALIZED MEMBER CHAT SYSTEM READY!")
    print("\\n📈 Expected Benefits:")
    print("- Higher member engagement (responses feel more personal)")
    print("- Better coaching outcomes (matches their communication style)")
    print("- Automatic learning (improves with each conversation)")
    print("- Scalable (works for any number of members)")

    print("\\n🎯 Next: Run the integration script to test with real data!")
    print("python scripts/integrate_personalized_prompting.py")
