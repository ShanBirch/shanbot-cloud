#!/usr/bin/env python3
"""
Member Conversation Trainer
Analyzes real member conversations to continuously improve the member chat prompt
"""

import re
import json
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict, Counter
import sqlite3
from pathlib import Path


@dataclass
class ConversationExample:
    member_message: str
    shannon_response: str
    context_type: str
    quality_score: int = 5
    patterns: List[str] = None


class MemberConversationTrainer:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "app/shanbot.db"
        self.examples = []
        self.patterns = {
            'acknowledgments': defaultdict(list),
            'celebrations': defaultdict(list),
            'problem_solving': defaultdict(list),
            'check_ins': defaultdict(list),
            'content_requests': defaultdict(list),
            'aussie_expressions': Counter(),
            'response_lengths': []
        }

    def parse_conversation_text(self, conversation_text: str) -> List[ConversationExample]:
        """Parse a raw conversation transcript into structured examples"""
        lines = conversation_text.strip().split('\n')
        examples = []

        for i, line in enumerate(lines):
            if line.startswith('Shannon: '):
                shannon_msg = line.replace('Shannon: ', '').strip()

                # Get the preceding member message for context
                member_msg = ""
                if i > 0 and lines[i-1].startswith(('Sabrina: ', 'Member: ')):
                    member_msg = re.sub(
                        r'^(Sabrina|Member): ', '', lines[i-1]).strip()

                if member_msg and shannon_msg:
                    context_type = self._classify_interaction(
                        member_msg, shannon_msg)
                    quality_score = self._score_response_quality(shannon_msg)
                    patterns = self._extract_patterns(shannon_msg)

                    examples.append(ConversationExample(
                        member_message=member_msg,
                        shannon_response=shannon_msg,
                        context_type=context_type,
                        quality_score=quality_score,
                        patterns=patterns
                    ))

        return examples

    def _classify_interaction(self, member_msg: str, shannon_response: str) -> str:
        """Classify the type of interaction"""
        member_lower = member_msg.lower()
        response_lower = shannon_response.lower()

        # Progress/completion
        if any(word in member_lower for word in ['done', 'finished', 'completed', 'did it']):
            return 'progress_celebration'

        # Questions about nutrition/fitness
        if '?' in member_msg and any(word in member_lower for word in ['eat', 'food', 'calories', 'macros', 'protein']):
            return 'nutrition_question'

        if '?' in member_msg and any(word in member_lower for word in ['exercise', 'workout', 'training', 'reps', 'weight']):
            return 'exercise_question'

        # Problems/issues
        if any(word in member_lower for word in ['problem', 'issue', 'cant', "can't", 'struggling', 'difficult']):
            return 'problem_solving'

        # Personal sharing
        if any(word in member_lower for word in ['i went', 'i did', 'yesterday', 'today', 'my day']):
            return 'personal_sharing'

        # Check-ins/how are you
        if 'how' in member_lower and any(word in member_lower for word in ['are', 'going', 'been']):
            return 'check_in_response'

        # Struggles/challenges
        if any(word in member_lower for word in ['tired', 'sore', 'hurt', 'pain', 'sick', 'stressed']):
            return 'support_needed'

        return 'general_chat'

    def _score_response_quality(self, response: str) -> int:
        """Score response quality based on Shannon's authentic patterns"""
        score = 5  # baseline
        response_lower = response.lower()

        # Positive indicators
        if any(expr in response_lower for expr in ['aye', 'hey', 'ofc', 'defs', 'plz']):
            score += 1  # Authentic Australian expressions

        if any(celebration in response_lower for celebration in ['good one', 'smashed it', 'awesome', 'hell yeah']):
            score += 2  # Enthusiastic celebration

        if 'understand' in response_lower or 'makes sense' in response_lower:
            score += 1  # Empathetic acknowledgment

        if response.count('!') >= 1:
            score += 1  # Appropriate enthusiasm

        if 5 <= len(response.split()) <= 25:
            score += 1  # Good length

        # Negative indicators
        if len(response.split()) > 50:
            score -= 2  # Too long

        if len(response.split()) < 2:
            score -= 1  # Too short

        if response.startswith('http'):
            score -= 1  # Just a link

        return max(1, min(10, score))

    def _extract_patterns(self, response: str) -> List[str]:
        """Extract communication patterns from Shannon's response"""
        patterns = []
        response_lower = response.lower()

        # Aussie expressions
        aussie_words = ['aye', 'hey', 'ofc', 'defs',
                        'plz', 'okie', 'tonite', 'v nice', 'nek time']
        for word in aussie_words:
            if word in response_lower:
                patterns.append(f"aussie_{word}")

        # Enthusiasm markers
        if any(word in response_lower for word in ['good one', 'smashed', 'awesome', 'hell yeah', 'fuck yeah']):
            patterns.append("high_enthusiasm")

        # Problem solving
        if any(word in response_lower for word in ["i'll fix", "i'll change", "will sort", "updated"]):
            patterns.append("proactive_solution")

        # Questions
        if '?' in response:
            patterns.append("asks_question")

        # Emojis
        if any(char in response for char in ['😊', '❤️', '😥', '👍', '🥰']):
            patterns.append("uses_emoji")

        return patterns

    def analyze_patterns(self, examples: List[ConversationExample]):
        """Analyze patterns across all examples"""
        for example in examples:
            # Track patterns by context type
            self.patterns['acknowledgments'][example.context_type].append(
                example.shannon_response)
            self.patterns['response_lengths'].append(
                len(example.shannon_response.split()))

            # Count Australian expressions
            for pattern in (example.patterns or []):
                if pattern.startswith('aussie_'):
                    self.patterns['aussie_expressions'][pattern] += 1

    def generate_training_insights(self) -> Dict:
        """Generate insights for improving the prompt"""
        insights = {
            'most_common_patterns': dict(self.patterns['aussie_expressions'].most_common(10)),
            'avg_response_length': sum(self.patterns['response_lengths']) / len(self.patterns['response_lengths']) if self.patterns['response_lengths'] else 0,
            'context_response_patterns': {},
            'high_quality_examples': []
        }

        # Analyze response patterns by context
        for context_type, responses in self.patterns['acknowledgments'].items():
            if responses:
                insights['context_response_patterns'][context_type] = {
                    'count': len(responses),
                    'examples': responses[:3]  # Top 3 examples
                }

        # Get high-quality examples (score >= 7)
        high_quality = [ex for ex in self.examples if ex.quality_score >= 7]
        insights['high_quality_examples'] = [
            {
                'member': ex.member_message,
                'shannon': ex.shannon_response,
                'type': ex.context_type,
                'score': ex.quality_score
            }
            for ex in high_quality[:10]
        ]

        return insights

    def save_to_database(self, examples: List[ConversationExample]):
        """Save analyzed examples to the learning database"""
        try:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent))

            from app.dashboard_modules.dashboard_sqlite_utils import add_to_learning_log

            for example in examples:
                if example.quality_score >= 6:  # Only save good examples
                    add_to_learning_log(
                        review_id=0,  # Placeholder
                        user_ig_username="training_data",
                        user_subscriber_id="training_data",
                        original_prompt_text=example.member_message,
                        original_gemini_response="",  # No original AI response
                        edited_response_text=example.shannon_response,
                        user_notes=f"Training data - {example.context_type}",
                        is_good_example_for_few_shot=1,
                        conversation_type='member'
                    )

            print(
                f"✅ Saved {len([ex for ex in examples if ex.quality_score >= 6])} high-quality examples to database")

        except Exception as e:
            print(f"⚠️ Could not save to database: {e}")

    def train_from_conversation(self, conversation_text: str, save_to_db: bool = True) -> Dict:
        """Train from a conversation and return insights"""
        examples = self.parse_conversation_text(conversation_text)
        self.examples.extend(examples)

        self.analyze_patterns(examples)

        if save_to_db:
            self.save_to_database(examples)

        insights = self.generate_training_insights()

        print(f"📊 Analyzed {len(examples)} conversation exchanges")
        print(
            f"📈 Average response quality score: {sum(ex.quality_score for ex in examples) / len(examples):.1f}")
        print(
            f"🎯 High-quality examples found: {len([ex for ex in examples if ex.quality_score >= 7])}")

        return insights


def main():
    """Example usage with Sabrina's conversation"""
    trainer = MemberConversationTrainer()

    # Example: Process the Sabrina conversation
    sabrina_conversation = """
Sabrina: I've fallen off my good habits in the last 6 months. I want to get back to consistent strength training, meal prepping, sleeping before midnight, reading, walking
Shannon: That's a very common experience, and it's awesome that you're ready to get back on track.
Sabrina: Studying my masters degree
Shannon: That's completely understandable. It's so difficult to stay on track when you're managing a master's degree and dealing with frequent illness.
Sabrina: Done!!!
Shannon: Good one!
Sabrina: the portion sizes are way too big for me! I usually eat 1/4 to 1/3 cup (dry) rice, and 100g tofu
Shannon: I'll change it in your new plan thought if course
Sabrina: I can't do the sourdough toast, gluten free bread is rarely vegan as they use egg protein as a stabiliser
Shannon: Ahhh all good! Anything else! Let's get it really good!
Sabrina: For the batch cooking, is this screenshot for 3 serves or 1?
Shannon: 120g of tofu is for 1 serving. 👍
Sabrina: I slipped in the rain LMAO
Shannon: Sucks 😥😥 You feeling ok
Sabrina: planning some pole classes
Shannon: Awesome
    """

    insights = trainer.train_from_conversation(sabrina_conversation)

    print("\n=== TRAINING INSIGHTS ===")
    print(json.dumps(insights, indent=2))


if __name__ == "__main__":
    main()
