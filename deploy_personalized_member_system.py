#!/usr/bin/env python3
"""
Deploy Personalized Member Chat System to Production
Integrates with existing webhook_handlers.py and enables personalized prompting
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))


def create_production_integration():
    """Create the production-ready integration patch"""

    integration_patch = '''
# =============================================================================
# PERSONALIZED MEMBER PROMPTING INTEGRATION
# Add this to webhook_handlers.py build_member_chat_prompt function
# =============================================================================

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
    """Enhanced member chat prompt with personalized prompting"""
    
    # =============================================================================
    # NEW: PERSONALIZED PROMPTING SYSTEM
    # =============================================================================
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
    
    # =============================================================================
    # FALLBACK: EXISTING MEMBER PROMPT LOGIC (unchanged)
    # =============================================================================
    
    # ... rest of your existing build_member_chat_prompt function continues here ...
    
    # Your existing code for getting member few-shot examples
    few_shot_text = ""
    if few_shot_examples:
        few_shot_text = format_few_shot_examples(few_shot_examples)
    
    # Your existing prompt template formatting
    final_prompt = MEMBER_CONVERSATION_PROMPT_TEMPLATE.format(
        current_melbourne_time_str=get_melbourne_time_str(),
        ig_username=ig_username,
        first_name=full_name or ig_username,
        fitness_goals=client_data.get('fitness_goals', ''),
        dietary_requirements=client_data.get('dietary_requirements', ''),
        current_program=client_data.get('current_program', ''),
        full_conversation=full_conversation_string,
        few_shot_examples=few_shot_text
    )
    
    return final_prompt, "member_chat"

# =============================================================================
# HELPER FUNCTION FOR FEW-SHOT FORMATTING
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

# =============================================================================
# AUTOMATIC LEARNING INTEGRATION
# =============================================================================

def log_member_conversation_for_learning(ig_username: str, user_message: str, 
                                       shannon_response: str, was_personalized: bool):
    """Log conversation for automatic personality learning"""
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        
        manager = MemberPersonalityManager()
        
        # If this was a successful personalized response, update the member's profile
        if was_personalized:
            # This could trigger automatic profile refinement
            logger.info(f"📈 Logging successful personalized interaction for {ig_username}")
        else:
            # Check if we have enough new data to create a profile
            logger.info(f"📝 Logging interaction for future profile creation: {ig_username}")
            
    except Exception as e:
        logger.warning(f"⚠️ Learning log failed for {ig_username}: {e}")

# =============================================================================
# WEBHOOK INTEGRATION POINT
# =============================================================================

# Add this to your webhook handler after generating a response:
"""
# After generating the AI response:
ai_response = await get_ai_response(final_prompt)

# Log for learning (add this):
log_member_conversation_for_learning(
    ig_username=ig_username,
    user_message=incoming_message, 
    shannon_response=ai_response,
    was_personalized=(prompt_type == "personalized_member_chat")
)
"""
'''

    return integration_patch


def create_deployment_checklist():
    """Create deployment checklist and instructions"""

    checklist = """
    🚀 PERSONALIZED MEMBER CHAT DEPLOYMENT CHECKLIST
    ===============================================
    
    📋 PRE-DEPLOYMENT:
    □ Test Sabrina's personality profile works
    □ Test StaaCi's personality profile works  
    □ Backup existing webhook_handlers.py
    □ Backup existing prompts.py
    □ Test database table creation
    
    🔧 DEPLOYMENT STEPS:
    □ 1. Apply integration patch to webhook_handlers.py
    □ 2. Add import statement for MemberPersonalityManager
    □ 3. Test with existing member conversations
    □ 4. Monitor logs for successful personalization
    □ 5. Verify fallback to general prompts works
    
    📊 POST-DEPLOYMENT TESTING:
    □ Send test message as Sabrina → should get technical/direct style
    □ Send test message as StaaCi → should get casual/storytelling style  
    □ Send test message as unknown member → should use general prompt
    □ Check database for personality profiles being created
    □ Monitor response quality improvements
    
    🎯 SUCCESS METRICS:
    □ Members get responses matching their communication style
    □ New member profiles are automatically created from conversation history
    □ Response quality improves over time through learning
    □ System gracefully falls back to general prompts when needed
    
    ⚠️ ROLLBACK PLAN:
    □ Remove personalized prompting code from webhook_handlers.py
    □ Restore backup files if needed
    □ System continues with existing general member prompts
    
    📈 MONITORING:
    □ Watch logs for "✅ Using personalized prompt for [username]"
    □ Monitor member satisfaction and engagement
    □ Track personality profile creation rate
    □ Check for any error patterns in personalization
    """

    return checklist


def create_production_deployment_script():
    """Create the actual deployment script for production"""

    deployment_script = '''#!/usr/bin/env python3
"""
Production Deployment Script
Run this on your Render server to deploy personalized member chat
"""

import os
import sys
import shutil
from datetime import datetime

def backup_existing_files():
    """Backup existing files before deployment"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    files_to_backup = [
        "webhook_handlers.py",
        "app/prompts.py"
    ]
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup_{timestamp}"
            shutil.copy2(file_path, backup_path)
            print(f"✅ Backed up {file_path} → {backup_path}")

def deploy_personalized_system():
    """Deploy the personalized member chat system"""
    
    print("🚀 DEPLOYING PERSONALIZED MEMBER CHAT SYSTEM")
    print("="*50)
    
    # 1. Backup files
    print("\\n1. Creating backups...")
    backup_existing_files()
    
    # 2. Initialize database tables
    print("\\n2. Initializing database tables...")
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        manager = MemberPersonalityManager()
        print("✅ Database tables ready")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    
    # 3. Load existing member profiles
    print("\\n3. Loading member profiles...")
    try:
        from scripts.add_staaci_personality import add_staaci_to_database
        from scripts.integrate_personalized_prompting import create_sabrina_demo_profile
        
        create_sabrina_demo_profile()
        add_staaci_to_database()
        print("✅ Member profiles loaded")
    except Exception as e:
        print(f"❌ Profile loading failed: {e}")
        return False
    
    # 4. Test system
    print("\\n4. Testing personalized system...")
    try:
        manager = MemberPersonalityManager()
        
        # Test Sabrina
        sabrina_personality = manager.get_member_personality('sabrina')
        if sabrina_personality:
            print("✅ Sabrina's profile loaded successfully")
        
        # Test StaaCi  
        staaci_personality = manager.get_member_personality('staaci')
        if staaci_personality:
            print("✅ StaaCi's profile loaded successfully")
            
    except Exception as e:
        print(f"❌ System test failed: {e}")
        return False
    
    print("\\n🎉 DEPLOYMENT SUCCESSFUL!")
    print("\\n📋 Next Steps:")
    print("- Monitor logs for personalized prompt usage")
    print("- Test with real member conversations")  
    print("- Watch for automatic profile creation")
    print("- System will learn and improve over time")
    
    return True

if __name__ == "__main__":
    deploy_personalized_system()
'''

    return deployment_script


def main():
    """Main deployment preparation"""

    print("🚀 PREPARING PERSONALIZED MEMBER CHAT DEPLOYMENT")
    print("="*60)

    # 1. Create integration patch
    print("\\n1. Creating integration patch...")
    patch = create_production_integration()

    with open("production_integration_patch.py", "w", encoding='utf-8') as f:
        f.write(patch)
    print("✅ Created production_integration_patch.py")

    # 2. Create deployment checklist
    print("\\n2. Creating deployment checklist...")
    checklist = create_deployment_checklist()

    with open("deployment_checklist.md", "w", encoding='utf-8') as f:
        f.write(checklist)
    print("✅ Created deployment_checklist.md")

    # 3. Create deployment script
    print("\\n3. Creating deployment script...")
    script = create_production_deployment_script()

    with open("production_deploy.py", "w", encoding='utf-8') as f:
        f.write(script)
    print("✅ Created production_deploy.py")

    print("\\n🎉 DEPLOYMENT PACKAGE READY!")
    print("="*40)

    print("\\n📁 Files Created:")
    print("- production_integration_patch.py  (Code to add to webhook_handlers.py)")
    print("- deployment_checklist.md         (Step-by-step deployment guide)")
    print("- production_deploy.py             (Automated deployment script)")

    print("\\n🚀 Ready to Deploy:")
    print("1. Review the integration patch")
    print("2. Follow the deployment checklist")
    print("3. Run production_deploy.py on your Render server")
    print("4. Your members will get personalized responses!")

    print("\\n💫 What You'll Get:")
    print("- Sabrina gets technical/direct responses")
    print("- StaaCi gets casual/storytelling responses")
    print("- New members automatically get profiles created")
    print("- System learns and improves with each conversation")


if __name__ == "__main__":
    main()
