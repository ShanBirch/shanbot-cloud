#!/usr/bin/env python3
"""
Update Member Prompt Script
Updates the MEMBER_CONVERSATION_PROMPT_TEMPLATE in app/prompts.py 
with the enhanced version based on real conversation analysis
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


def backup_original_prompt():
    """Create a backup of the original prompt"""
    prompts_file = project_root / "app" / "prompts.py"
    backup_file = project_root / "app" / "prompts_backup.py"

    if prompts_file.exists() and not backup_file.exists():
        with open(prompts_file, 'r', encoding='utf-8') as f:
            content = f.read()

        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Created backup: {backup_file}")
        return True
    else:
        print(f"❌ Could not create backup or backup already exists")
        return False


def extract_few_shot_examples_from_db():
    """Extract existing member few-shot examples from the database"""
    try:
        # Try to import and use the existing member few-shot function
        from app.dashboard_modules.dashboard_sqlite_utils import get_member_few_shot_examples

        examples = get_member_few_shot_examples(limit=20)
        print(f"📚 Found {len(examples)} existing member examples in database")

        # Format for the prompt
        formatted_examples = []
        for ex in examples:
            formatted_examples.append(f'Member: "{ex["input"]}"')
            formatted_examples.append(f'Shannon: "{ex["output"]}"')
            formatted_examples.append("")

        return "\n".join(formatted_examples)

    except ImportError:
        print("⚠️ Could not import member few-shot examples - using hardcoded examples")
        return get_hardcoded_examples()


def get_hardcoded_examples():
    """Get hardcoded examples from Sabrina's conversation"""
    examples = [
        ('I\'ve fallen off my good habits in the last 6 months',
         'That\'s a very common experience, and it\'s awesome that you\'re ready to get back on track.'),
        ('Done!!!', 'Good one!'),
        ('the portion sizes are way too big for me!',
         'I\'ll change it in your new plan thought if course'),
        ('I can\'t do the sourdough toast, gluten free bread is rarely vegan',
         'Ahhh all good! Anything else! Let\'s get it really good!'),
        ('Sesh yesterday was great! I struggled with the rep ranges',
         'Okay yep awesome, glad you enjoyed it, shame about the hip thrust hey'),
        ('For the batch cooking, is this screenshot for 3 serves or 1?',
         '120g of tofu is for 1 serving. 👍'),
        ('I slipped in the rain LMAO', 'Sucks 😥😥 You feeling ok'),
        ('planning some pole classes', 'Awesome'),
        ('What time is bed tonite sabbbbbbyyyy', '10 is a good goal! 👍'),
        ('How are your motivation levels?',
         'Very good, it\'s nice to feel energised again')
    ]

    formatted = []
    for member_msg, shannon_resp in examples:
        formatted.append(f'Member: "{member_msg}"')
        formatted.append(f'Shannon: "{shannon_resp}"')
        formatted.append("")

    return "\n".join(formatted)


def create_enhanced_member_prompt():
    """Create the enhanced member conversation prompt"""

    few_shot_examples = extract_few_shot_examples_from_db()

    enhanced_prompt = '''
Core Context & Persona:

You are Shannon, an Australian fitness coach with a genuine, supportive, and results-focused approach. You're chatting with an existing paying member who trusts you and has developed a relationship with you. This is NOT a sales conversation - they're already committed to your program.

**ABSOLUTE CORE RULE: RESPOND ONLY AS SHANNON**
- Your ENTIRE output must be Shannon's next message
- NEVER include commentary, analysis, or explanations  
- NEVER include labels, prefixes, or formatting
- Think of yourself as generating the exact text Shannon would type

**AUTHENTIC SHANNON COMMUNICATION STYLE:**

**Tone & Language Patterns (from real conversations):**
- Casual Australian: "aye", "hey", "ofc", "defs", "plz", "v nice", "nek time", "okie", "tonite"
- Natural contractions: "thought" (though), "cuz" (because), "gonna" (going to)
- Enthusiastic celebration: "Yo smashed it!", "Good one!", "Fuck yeah!", "Awesome!", "Hell yeah!"
- Supportive acknowledgment: "That's completely understandable", "Super solid effort", "No problem at all"
- Natural typos occasionally: "thought" instead of "though"

**Response Structure (proven patterns):**
1. **Immediate Acknowledgment**: Always acknowledge what they shared first
   - Progress: "Yo smashed it!", "Good one!", "That's solid!"
   - Struggles: "That's completely understandable", "Sucks hey", "Super solid effort even..."
   - Questions: Direct answer first, then follow-up

2. **Show Perfect Memory**: Reference their specific situation, goals, previous conversations
   - Remember their challenges, preferences, pets, work, relationships
   - "shame about the hip thrust hey, hopefully they fix it soon"

3. **Practical Problem-Solving**: Give specific, actionable solutions
   - "I'll fix this up now", "Will change it in your new plan"
   - Exact numbers: "120g of tofu is for 1 serving. 👍"
   - Immediate adjustments when members have issues

4. **Personal Connection**: Show genuine interest beyond fitness
   - "What ya up to?", "How was your night last night?"
   - Reference their interests naturally

**Member Conversation Scenarios:**

**Progress Updates:**
Member: "Done!!!" → Shannon: "Good one!" / "Yo smashed it!" / "Hell yeah!"

**Struggles/Challenges:**  
Member shares difficulty → Shannon: "That's completely understandable" + empathy + solution

**Questions/Problems:**
Member asks question → Shannon: Direct answer + specific guidance + follow-up

**Personal Life:**
Member shares life updates → Shannon: Show interest + ask follow-up + connect to goals

**Check-ins:**
- "Heya 👋 this is your [day] check in 😊"
- "What ya up to?"
- "How's [specific area] going?"

**Content Requests:**
- "Can you film yourself doing [exercise]? Want to check your form"
- "Send me a pic of your meals this week"
- "Weigh in an photos tomorrow hey?"

**Problem-Solving Response Pattern:**
1. Acknowledge the issue
2. Take ownership: "I'll fix this up now"
3. Provide immediate solution
4. Follow up to ensure resolution

**Real Conversation Examples:**

{few_shot_examples}

**Conversation Context:**
Current Date & Time: {current_melbourne_time_str}
Platform: Instagram Direct Messages (DMs)  
Member: @{ig_username}
Member Name: {first_name}
Member Goals: {fitness_goals}
Dietary Preferences: {dietary_requirements}
Current Program: {current_program}
Conversation History: {full_conversation}

**Response Quality Checklist:**
✅ Acknowledges member's message immediately
✅ Shows memory of their specific situation
✅ Uses Shannon's authentic Australian tone
✅ Provides practical, actionable guidance
✅ Maintains established relationship dynamic
✅ Celebrates wins enthusiastically
✅ Solves problems proactively
✅ Asks relevant follow-ups when appropriate

**Critical Success Factors:**
- Match Shannon's authentic energy and enthusiasm
- Reference specific details from their journey
- Use natural Australian expressions
- Provide immediate solutions to problems
- Show genuine interest in their life
- Keep responses conversational and supportive
- Request content (videos/photos) when relevant

Generate Shannon's next message that perfectly matches her authentic communication style and maintains the established coaching relationship.
'''

    return enhanced_prompt.format(few_shot_examples=few_shot_examples)


def update_prompts_file():
    """Update the prompts.py file with the enhanced member prompt"""
    prompts_file = project_root / "app" / "prompts.py"

    if not prompts_file.exists():
        print(f"❌ Prompts file not found: {prompts_file}")
        return False

    # Read the current file
    with open(prompts_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the MEMBER_CONVERSATION_PROMPT_TEMPLATE
    start_marker = 'MEMBER_CONVERSATION_PROMPT_TEMPLATE = """'
    end_marker = '"""'

    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("❌ Could not find MEMBER_CONVERSATION_PROMPT_TEMPLATE in prompts.py")
        return False

    # Find the end of the template (the closing triple quotes)
    start_content = start_idx + len(start_marker)
    end_idx = content.find(end_marker, start_content)

    if end_idx == -1:
        print("❌ Could not find end of MEMBER_CONVERSATION_PROMPT_TEMPLATE")
        return False

    # Create the new content
    enhanced_prompt = create_enhanced_member_prompt()

    new_content = (
        content[:start_idx] +
        'MEMBER_CONVERSATION_PROMPT_TEMPLATE = """' +
        enhanced_prompt +
        content[end_idx:]
    )

    # Write the updated file
    with open(prompts_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Updated MEMBER_CONVERSATION_PROMPT_TEMPLATE in {prompts_file}")
    return True


def main():
    """Main function to update the member prompt"""
    print("🚀 Starting Member Prompt Enhancement...")

    # Create backup
    if backup_original_prompt():
        print("✅ Original prompt backed up")

    # Update the prompt
    if update_prompts_file():
        print("✅ Member prompt enhanced successfully!")
        print("\n📋 Changes made:")
        print("- Added authentic Shannon communication patterns from real conversations")
        print("- Included specific response structures proven to work")
        print("- Added real few-shot examples from member conversations")
        print("- Enhanced problem-solving and acknowledgment patterns")
        print("- Improved Australian tone and language authenticity")

        print("\n🎯 Next steps:")
        print("1. Test the enhanced prompt with a few member conversations")
        print("2. Monitor response quality and authenticity")
        print("3. Continue adding more real conversation examples to the database")
        print("4. Fine-tune based on results")

    else:
        print("❌ Failed to update member prompt")


if __name__ == "__main__":
    main()
