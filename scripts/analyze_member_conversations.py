#!/usr/bin/env python3
"""
Member Conversation Pattern Analyzer
Analyzes real member conversations to extract Shannon's authentic patterns
for improving the MEMBER_CONVERSATION_PROMPT_TEMPLATE
"""

import re
from typing import List, Dict, Tuple
from collections import defaultdict


class MemberConversationAnalyzer:
    def __init__(self):
        self.shannon_patterns = {
            'acknowledgments': [],
            'aussie_expressions': [],
            'enthusiasm_markers': [],
            'problem_solving': [],
            'check_ins': [],
            'content_requests': [],
            'personal_connections': [],
            'practical_guidance': []
        }

    def analyze_conversation(self, conversation_text: str) -> Dict:
        """Analyze a member conversation and extract Shannon's patterns"""
        lines = conversation_text.split('\n')
        shannon_messages = []
        context_pairs = []

        # Extract Shannon's messages and their context
        for i, line in enumerate(lines):
            if line.startswith('Shannon: '):
                shannon_msg = line.replace('Shannon: ', '').strip()
                shannon_messages.append(shannon_msg)

                # Get preceding Sabrina message for context
                if i > 0 and lines[i-1].startswith('Sabrina: '):
                    sabrina_msg = lines[i-1].replace('Sabrina: ', '').strip()
                    context_pairs.append({
                        'member_message': sabrina_msg,
                        'shannon_response': shannon_msg
                    })

        # Analyze patterns
        patterns = self._extract_patterns(shannon_messages, context_pairs)
        return {
            'total_shannon_messages': len(shannon_messages),
            'context_pairs': len(context_pairs),
            'patterns': patterns,
            'conversation_structure': self._analyze_structure(context_pairs)
        }

    def _extract_patterns(self, messages: List[str], pairs: List[Dict]) -> Dict:
        """Extract specific communication patterns"""
        patterns = defaultdict(list)

        for msg in messages:
            # Aussie expressions
            aussie_words = ['aye', 'hey', 'ofc', 'defs',
                            'plz', 'okie', 'tonite', 'v nice', 'nek time']
            for word in aussie_words:
                if word in msg.lower():
                    patterns['aussie_expressions'].append(
                        f"'{word}' in: {msg[:50]}...")

            # Enthusiasm markers
            enthusiasm = ['!', 'Yo', 'Good one', 'Fuck yeah',
                          'Awesome', 'smashed it', 'killing it']
            for marker in enthusiasm:
                if marker.lower() in msg.lower():
                    patterns['enthusiasm_markers'].append(
                        f"'{marker}' in: {msg[:50]}...")

            # Check-in patterns
            checkin_phrases = ['how are you',
                               'how was your', "what's up", 'what ya up to']
            for phrase in checkin_phrases:
                if phrase.lower() in msg.lower():
                    patterns['check_ins'].append(msg)

            # Content requests
            content_requests = ['can you film',
                                'send me a pic', 'let me know', 'book in']
            for request in content_requests:
                if request.lower() in msg.lower():
                    patterns['content_requests'].append(msg)

            # Problem solving (when Shannon adjusts/fixes things)
            problem_solving = ['ill fix', 'ill change',
                               'updated', 'fixed', 'sorted']
            for solve in problem_solving:
                if solve.lower() in msg.lower():
                    patterns['problem_solving'].append(msg)

        # Analyze context pairs for response patterns
        for pair in pairs:
            member_msg = pair['member_message'].lower()
            shannon_response = pair['shannon_response']

            # Acknowledgment patterns
            if any(word in member_msg for word in ['sorry', 'apologize', 'my bad']):
                patterns['acknowledgments'].append(
                    f"To apology: {shannon_response}")

            if any(word in member_msg for word in ['struggling', 'difficult', 'hard', 'problem']):
                patterns['acknowledgments'].append(
                    f"To struggle: {shannon_response}")

            if any(word in member_msg for word in ['done', 'finished', 'completed']):
                patterns['acknowledgments'].append(
                    f"To completion: {shannon_response}")

        return dict(patterns)

    def _analyze_structure(self, pairs: List[Dict]) -> Dict:
        """Analyze conversation flow and structure patterns"""
        structures = {
            'response_lengths': [],
            'question_frequency': 0,
            'emoji_usage': 0,
            'personal_references': 0
        }

        for pair in pairs:
            response = pair['shannon_response']

            # Response length analysis
            word_count = len(response.split())
            structures['response_lengths'].append(word_count)

            # Question frequency
            if '?' in response:
                structures['question_frequency'] += 1

            # Emoji usage
            emoji_pattern = re.compile(
                r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+')
            if emoji_pattern.search(response):
                structures['emoji_usage'] += 1

            # Personal references (names, personal details)
            if any(name in response.lower() for name in ['sab', 'sabrina', 'your']):
                structures['personal_references'] += 1

        # Calculate averages
        if structures['response_lengths']:
            structures['avg_response_length'] = sum(
                structures['response_lengths']) / len(structures['response_lengths'])

        structures['question_rate'] = structures['question_frequency'] / \
            len(pairs) if pairs else 0
        structures['emoji_rate'] = structures['emoji_usage'] / \
            len(pairs) if pairs else 0

        return structures


def create_few_shot_examples_from_analysis(conversation_text: str) -> List[Dict[str, str]]:
    """Extract high-quality few-shot examples from the conversation"""
    lines = conversation_text.split('\n')
    examples = []

    for i, line in enumerate(lines):
        if line.startswith('Shannon: ') and i > 0:
            # Get the previous Sabrina message
            prev_line = lines[i-1]
            if prev_line.startswith('Sabrina: '):
                member_msg = prev_line.replace('Sabrina: ', '').strip()
                shannon_response = line.replace('Shannon: ', '').strip()

                # Filter for high-quality examples
                if (len(shannon_response.split()) >= 3 and  # Not too short
                    len(shannon_response.split()) <= 30 and  # Not too long
                    '?' in shannon_response or  # Contains question OR
                    # Positive response
                    any(word in shannon_response.lower() for word in ['good', 'awesome', 'yeah', 'that\'s']) and
                        not shannon_response.startswith('http')):  # Not just a link

                    examples.append({
                        'input': member_msg,
                        'output': shannon_response,
                        'category': classify_response(shannon_response)
                    })

    return examples


def classify_response(response: str) -> str:
    """Classify Shannon's response type"""
    response_lower = response.lower()

    if any(word in response_lower for word in ['good', 'awesome', 'smashed', 'killing']):
        return 'celebration'
    elif '?' in response:
        return 'question'
    elif any(word in response_lower for word in ['fix', 'change', 'update', 'sort']):
        return 'problem_solving'
    elif any(word in response_lower for word in ['understand', 'understandable', 'makes sense']):
        return 'acknowledgment'
    elif any(word in response_lower for word in ['film', 'pic', 'send', 'show']):
        return 'content_request'
    else:
        return 'general_support'


if __name__ == "__main__":
    # Example usage with Sabrina's conversation
    sabrina_conversation = """
Sabrina: I've fallen off my good habits in the last 6 months. I want to get back to consistent strength training, meal prepping, sleeping before midnight, reading, walking
Shannon: That's a very common experience, and it's awesome that you're ready to get back on track.
Sabrina: Studying my masters degree
Shannon: That's completely understandable. It's so difficult to stay on track when you're managing a master's degree and dealing with frequent illness.
    """

    analyzer = MemberConversationAnalyzer()
    results = analyzer.analyze_conversation(sabrina_conversation)

    print("=== MEMBER CONVERSATION ANALYSIS ===")
    print(f"Total Shannon messages: {results['total_shannon_messages']}")
    print(f"Context pairs: {results['context_pairs']}")

    print("\n=== PATTERNS FOUND ===")
    for pattern_type, examples in results['patterns'].items():
        if examples:
            print(f"\n{pattern_type.upper()}:")
            for example in examples[:3]:  # Show first 3 examples
                print(f"  - {example}")

    print("\n=== CONVERSATION STRUCTURE ===")
    structure = results['conversation_structure']
    print(
        f"Average response length: {structure.get('avg_response_length', 0):.1f} words")
    print(f"Question rate: {structure['question_rate']:.1%}")
    print(f"Emoji usage rate: {structure['emoji_rate']:.1%}")
