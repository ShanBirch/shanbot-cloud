
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
    
    formatted = "\n\nHere are examples of how Shannon responds to members:\n"
    for example in few_shot_examples[-5:]:  # Use last 5 examples
        user_msg = example.get('user_message', '')
        shannon_response = example.get('shannon_response', '')
        if user_msg and shannon_response:
            formatted += f"\nMember: {user_msg}\nShannon: {shannon_response}\n"
    
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
