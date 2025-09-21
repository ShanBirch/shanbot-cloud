#!/usr/bin/env python3
"""
Personalized Member Prompting System
Combines general Shannon style with individual member patterns
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MemberPersonality:
    ig_username: str
    communication_style: str  # 'detailed', 'concise', 'casual', 'technical'
    interests: List[str]
    response_preferences: str  # 'direct_first', 'empathy_first', 'solution_focused'
    celebration_style: str  # 'enthusiastic', 'understated', 'playful'
    problem_solving_style: str  # 'collaborative', 'directive', 'supportive'
    specific_phrases: List[str]
    conversation_history_patterns: Dict


class PersonalizedMemberPromptEngine:
    def __init__(self):
        self.member_profiles = {}
        self.general_patterns = self._load_general_patterns()

    def _load_general_patterns(self) -> Dict:
        """Load the general Shannon patterns we already built"""
        return {
            'aussie_expressions': ['aye', 'hey', 'ofc', 'defs', 'plz', 'v nice'],
            'enthusiasm': ['Good one!', 'Yo smashed it!', 'Hell yeah!'],
            'empathy': ['That\'s completely understandable', 'Sucks hey'],
            'problem_solving': ['I\'ll fix this up now', 'Will change it'],
            'base_tone': 'casual_australian_supportive'
        }

    def analyze_member_patterns(self, ig_username: str, conversation_history: List[Dict]) -> MemberPersonality:
        """Analyze individual member's communication patterns"""

        # Analyze their conversation style
        member_messages = [
            msg for msg in conversation_history if msg.get('type') == 'user']
        shannon_responses = [
            msg for msg in conversation_history if msg.get('type') == 'ai']

        # Extract patterns
        communication_style = self._analyze_communication_style(
            member_messages)
        interests = self._extract_interests(member_messages)
        response_preferences = self._analyze_response_preferences(
            member_messages, shannon_responses)
        celebration_style = self._analyze_celebration_preferences(
            shannon_responses)

        return MemberPersonality(
            ig_username=ig_username,
            communication_style=communication_style,
            interests=interests,
            response_preferences=response_preferences,
            celebration_style=celebration_style,
            problem_solving_style=self._analyze_problem_solving_style(
                member_messages),
            specific_phrases=self._extract_member_specific_phrases(
                member_messages),
            conversation_history_patterns=self._analyze_conversation_patterns(
                conversation_history)
        )

    def _analyze_communication_style(self, member_messages: List[Dict]) -> str:
        """Determine if member prefers detailed, concise, casual, or technical responses"""
        avg_length = sum(len(msg.get('text', '').split(
        )) for msg in member_messages) / len(member_messages) if member_messages else 0

        technical_words = ['macros', 'protein', 'calories',
                           'form', 'technique', 'sets', 'reps']
        technical_count = sum(1 for msg in member_messages if any(
            word in msg.get('text', '').lower() for word in technical_words))

        if avg_length > 20:
            return 'detailed'
        elif technical_count / len(member_messages) > 0.3:
            return 'technical'
        elif avg_length < 8:
            return 'concise'
        else:
            return 'casual'

    def _extract_interests(self, member_messages: List[Dict]) -> List[str]:
        """Extract member's specific interests from their messages"""
        interests = []
        interest_keywords = {
            'pole_dancing': ['pole', 'dancing', 'tricks', 'choreography'],
            'nutrition_science': ['macros', 'protein', 'calories', 'nutrients'],
            'gluten_free': ['gluten', 'gluten free', 'celiac'],
            'animal_lover': ['dog', 'cat', 'pet', 'bunny'],
            'student': ['study', 'uni', 'university', 'masters', 'degree'],
            'cooking': ['cooking', 'baking', 'recipe', 'meal prep']
        }

        for interest, keywords in interest_keywords.items():
            if any(keyword in ' '.join(msg.get('text', '') for msg in member_messages).lower() for keyword in keywords):
                interests.append(interest)

        return interests

    def _analyze_response_preferences(self, member_messages: List[Dict], shannon_responses: List[Dict]) -> str:
        """Analyze what type of responses this member responds best to"""
        # Look at member engagement after different response types
        question_responses = sum(
            1 for msg in member_messages if '?' in msg.get('text', ''))
        total_messages = len(member_messages)

        if question_responses / total_messages > 0.4:
            return 'direct_first'  # They ask lots of questions, want direct answers
        else:
            return 'empathy_first'  # They share more, appreciate empathy first

    def _analyze_celebration_preferences(self, shannon_responses: List[Dict]) -> str:
        """Determine how this member likes to be celebrated"""
        enthusiastic_responses = sum(1 for msg in shannon_responses if any(
            word in msg.get('text', '').lower() for word in ['!', 'awesome', 'smashed']))

        if enthusiastic_responses / len(shannon_responses) > 0.6:
            return 'enthusiastic'
        else:
            return 'understated'

    def _analyze_problem_solving_style(self, member_messages: List[Dict]) -> str:
        """Determine their preferred problem-solving approach"""
        collaborative_indicators = [
            'what do you think', 'should i', 'would you']
        collaborative_count = sum(1 for msg in member_messages if any(
            phrase in msg.get('text', '').lower() for phrase in collaborative_indicators))

        if collaborative_count > 2:
            return 'collaborative'
        else:
            return 'directive'

    def _extract_member_specific_phrases(self, member_messages: List[Dict]) -> List[str]:
        """Extract unique phrases this member uses"""
        common_phrases = []
        all_text = ' '.join(msg.get('text', '')
                            for msg in member_messages).lower()

        # Look for repeated patterns
        unique_phrases = ['lmao', 'v nice', 'omg', 'lol', 'haha']
        for phrase in unique_phrases:
            if phrase in all_text:
                common_phrases.append(phrase)

        return common_phrases

    def _analyze_conversation_patterns(self, conversation_history: List[Dict]) -> Dict:
        """Analyze broader conversation patterns"""
        return {
            'typical_response_time': 'immediate',  # Could be calculated from timestamps
            'conversation_length_preference': 'medium',
            'topic_transitions': 'gradual',
            'question_asking_frequency': 'high'
        }

    def generate_personalized_prompt(self, ig_username: str, member_personality: MemberPersonality, current_message: str, general_context: Dict) -> str:
        """Generate a prompt that combines general Shannon style with personal patterns"""

        # Base prompt with general Shannon patterns
        base_prompt = f"""
You are Shannon, responding to your member {member_personality.ig_username}.

GENERAL SHANNON STYLE: {self.general_patterns}

PERSONALIZED FOR {member_personality.ig_username.upper()}:
- Communication Style: {member_personality.communication_style}
- Interests: {', '.join(member_personality.interests)}
- Response Preference: {member_personality.response_preferences}
- Celebration Style: {member_personality.celebration_style}
- Problem Solving: {member_personality.problem_solving_style}
- Their Phrases: {', '.join(member_personality.specific_phrases)}

PERSONALIZED RESPONSE RULES:
"""

        # Add personalized rules based on their patterns
        if member_personality.communication_style == 'detailed':
            base_prompt += "- Provide thorough explanations and context\n"
        elif member_personality.communication_style == 'concise':
            base_prompt += "- Keep responses short and direct\n"
        elif member_personality.communication_style == 'technical':
            base_prompt += "- Include specific numbers, macros, and technical details\n"

        if 'pole_dancing' in member_personality.interests:
            base_prompt += "- Reference their pole training when relevant\n"

        if 'student' in member_personality.interests:
            base_prompt += "- Show understanding of academic stress and schedules\n"

        if member_personality.response_preferences == 'direct_first':
            base_prompt += "- Answer questions directly first, then add support\n"
        else:
            base_prompt += "- Lead with empathy and understanding\n"

        if member_personality.celebration_style == 'understated':
            base_prompt += "- Celebrate wins with calm enthusiasm rather than high energy\n"

        # Add current context
        base_prompt += f"""
CURRENT MESSAGE: {current_message}
CONTEXT: {general_context}

Generate Shannon's response that matches both her general style AND {member_personality.ig_username}'s specific patterns.
"""

        return base_prompt

# Example usage for Sabrina


def create_sabrina_personality() -> MemberPersonality:
    """Example of Sabrina's analyzed personality"""
    return MemberPersonality(
        ig_username="sabrina",
        communication_style="detailed",  # She asks thorough questions
        interests=["pole_dancing", "nutrition_science",
                   "gluten_free", "student", "animal_lover"],
        # She asks specific questions and wants direct answers
        response_preferences="direct_first",
        # Responds well to "Good one!" rather than "HELL YEAH!!!"
        celebration_style="understated",
        # Asks "what do you think", wants to be involved
        problem_solving_style="collaborative",
        specific_phrases=["LMAO", "omg", "yea", "okie"],
        conversation_history_patterns={
            "detailed_questions": True,
            "technical_interest": True,
            "proactive_problem_solving": True,
            "shares_personal_details": True
        }
    )


if __name__ == "__main__":
    engine = PersonalizedMemberPromptEngine()
    sabrina = create_sabrina_personality()

    # Example personalized prompt
    prompt = engine.generate_personalized_prompt(
        ig_username="sabrina",
        member_personality=sabrina,
        current_message="For the batch cooking, is this screenshot for 3 serves or 1?",
        general_context={
            "conversation_type": "nutrition_question", "meal_plan_week": 1}
    )

    print("=== PERSONALIZED PROMPT FOR SABRINA ===")
    print(prompt)
