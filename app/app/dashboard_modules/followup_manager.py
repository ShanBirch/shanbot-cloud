"""
Follow-up Manager Module
Handles follow-up scheduling, recent interactions, and bulk messaging tools
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
from shared_utils import call_gemini_with_retry_sync, GEMINI_MODEL_PRO, GEMINI_API_KEY
# Import specific functions we need - avoiding potential circular imports
try:
    from followup_utils import (
        display_user_followup,
        generate_follow_up_message,
        save_followup_queue
    )
except ImportError:
    # Fallback if followup_utils has import issues
    display_user_followup = None
    generate_follow_up_message = None
    save_followup_queue = None

# Use the local version of get_users_ready_for_followup to avoid import conflicts
from analytics_overview import get_users_from_last_30_days
from shared_utils import get_user_topics
from scheduled_followups import get_user_category, get_topic_for_category

# Configure logging
logger = logging.getLogger(__name__)

# Local Gemini configuration to avoid circular imports
try:
    import google.generativeai as genai
    import streamlit as st

    # Try to get API key from secrets or use fallback
    try:
        GEMINI_API_KEY = st.secrets["general"]["GEMINI_API_KEY"]
    except:
        GEMINI_API_KEY = "AIzaSyAH6467EocGBwuMi-oDLawrNyCKjPHHmN8"

    # Gemini model constants - using latest requested models
    GEMINI_MODEL_PRO = "gemini-2.5-flash-lite-preview-06-17"  # Primary model
    GEMINI_MODEL_FLASH = "gemini-2.5-flash"
    GEMINI_MODEL_LITE = "gemini-2.0-flash-exp"

    # Configure genai
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
        genai.configure(api_key=GEMINI_API_KEY)
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False

except ImportError:
    AI_AVAILABLE = False
    GEMINI_API_KEY = None
    GEMINI_MODEL_PRO = "gemini-pro"

# Local Gemini function to avoid import issues


def call_gemini_with_retry_sync(model_name: str, prompt: str) -> str:
    """Local version of Gemini function with 3-model fallback cascade."""
    if not AI_AVAILABLE:
        return None

    # Define fallback cascade: Lite -> Flash -> Exp -> Stable
    fallback_models = [
        model_name,  # Try requested model first
        GEMINI_MODEL_PRO,  # gemini-2.5-flash-lite-preview-06-17 (primary)
        GEMINI_MODEL_FLASH,  # gemini-2.5-flash
        GEMINI_MODEL_LITE,  # gemini-2.0-flash-exp
        "gemini-pro"  # Final fallback to stable model
    ]

    # Remove duplicates while preserving order
    unique_models = []
    for model in fallback_models:
        if model not in unique_models:
            unique_models.append(model)

    for attempt_model in unique_models:
        try:
            logger.info(f"Trying Gemini model: {attempt_model}")
            model = genai.GenerativeModel(attempt_model)
            response = model.generate_content(prompt)
            logger.info(f"✅ Success with model: {attempt_model}")
            return response.text.strip()
        except Exception as e:
            logger.warning(f"❌ Model {attempt_model} failed: {e}")
            continue

    logger.error("🚨 All Gemini models failed")
    return None


def get_response_level_wait_time(num_responses):
    """Return wait time in days based on response level"""
    if num_responses >= 20:  # High responder (green)
        return 2  # 48 hours
    elif num_responses >= 11:  # Medium responder (yellow)
        return 5  # 5 days
    else:  # Low responder (orange/red)
        return 7  # 7 days


def get_users_ready_for_followup(analytics_data: dict):
    """Determine which users are ready for follow-up based on their response level."""
    ready_for_followup = {
        'high_responders': [],
        'medium_responders': [],
        'low_responders': [],
        'total_count': 0
    }
    current_time = datetime.now()

    # Known non-user keys
    known_non_user_keys = ["conversations",
                           "action_items", "conversation_history"]
    processed_usernames = set()

    # Helper to process a user
    def process_user(username, user_data):
        if username in processed_usernames:
            return
        processed_usernames.add(username)
        metrics = user_data.get('metrics', {})
        if not metrics:
            return

        # FILTER OUT PAYING CLIENTS AND TRIAL MEMBERS - they belong in Check-ins tab
        journey_stage = metrics.get('journey_stage', {})
        if isinstance(journey_stage, dict):
            # Skip paying clients
            if journey_stage.get('is_paying_client', False):
                return
            # Skip trial members
            if journey_stage.get('trial_start_date'):
                return

        last_interaction_ts_str = metrics.get('last_interaction_timestamp')
        last_message_time = None
        if last_interaction_ts_str:
            try:
                last_message_time = datetime.fromisoformat(
                    last_interaction_ts_str.split('+')[0])
            except (ValueError, AttributeError):
                pass
        if not last_message_time:
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                try:
                    last_msg_in_history = conversation_history[-1]
                    last_message_time = datetime.fromisoformat(
                        last_msg_in_history.get('timestamp', '').split('+')[0])
                except (IndexError, ValueError, AttributeError):
                    pass
        if not last_message_time:
            return

        num_responses = metrics.get('user_messages', 0)
        wait_days = get_response_level_wait_time(num_responses)
        time_since_last_message = current_time - last_message_time

        if time_since_last_message.days >= wait_days:
            user_info = {
                'username': username,
                'days_since_last_message': time_since_last_message.days,
                'response_count': num_responses,
                'last_message_time': last_message_time
            }
            if num_responses >= 20:
                ready_for_followup['high_responders'].append(user_info)
            elif num_responses >= 11:
                ready_for_followup['medium_responders'].append(user_info)
            else:
                ready_for_followup['low_responders'].append(user_info)
            ready_for_followup['total_count'] += 1

    # Process users under 'conversations'
    nested_conversations = analytics_data.get('conversations')
    if isinstance(nested_conversations, dict):
        for username, user_data in nested_conversations.items():
            process_user(username, user_data)

    logger.info(
        f"Users ready for followup: High={len(ready_for_followup['high_responders'])}, "
        f"Med={len(ready_for_followup['medium_responders'])}, "
        f"Low={len(ready_for_followup['low_responders'])}")

    return ready_for_followup


# Fallback functions if imports failed
if save_followup_queue is None:
    def save_followup_queue():
        """Fallback save function."""
        try:
            import json
            queue_file = r"C:\Users\Shannon\OneDrive\Desktop\shanbot\followup_queue.json"
            with open(queue_file, 'w') as f:
                json.dump({
                    'messages': st.session_state.get('message_queue', []),
                    'created_at': datetime.now().isoformat()
                }, f, indent=2)
            return True
        except Exception as e:
            st.error(f"Error saving follow-up queue: {e}")
            return False

if generate_follow_up_message is None:
    def generate_follow_up_message(conversation_history, topic, days_since_last=None):
        """Enhanced follow-up message generation with few-shot learning from Shannon's edits."""
        if not GEMINI_API_KEY or GEMINI_API_KEY in ["YOUR_GEMINI_API_KEY", "your_gemini_api_key_here"]:
            return "[Gemini not available]"
        try:
            # Get few-shot examples from Shannon's previous edits
            from dashboard_sqlite_utils import get_good_few_shot_examples
            few_shot_examples = get_good_few_shot_examples(limit=10)

            formatted_history = ""
            for msg in conversation_history:
                sender = "User" if msg.get('type') == 'user' else "Shannon"
                formatted_history += f"{sender}: {msg.get('text', '')}\n"

            # Create timing-aware prompt
            timing_context = ""
            if days_since_last:
                if days_since_last <= 2:
                    timing_context = f"It's been {days_since_last} days since they last messaged - this is a recent follow-up, so keep it casual and direct."
                elif days_since_last <= 7:
                    timing_context = f"It's been {days_since_last} days since they last messaged - acknowledge the gap briefly and re-engage warmly."
                elif days_since_last <= 14:
                    timing_context = f"It's been {days_since_last} days (about {days_since_last//7} weeks) since they last messaged - acknowledge the longer gap and restart the conversation gently."
                else:
                    timing_context = f"It's been {days_since_last} days (over {days_since_last//7} weeks) since they last messaged - this is a re-engagement message, be warm and understanding about the gap."

            # Build few-shot examples section
            few_shot_section = ""
            if few_shot_examples:
                few_shot_section = "\n\nHere are examples of Shannon's actual follow-up messages (learn from these):\n"
                # Use top 5 examples
                for i, example in enumerate(few_shot_examples[:5], 1):
                    user_msg = example['user_message'][:100] + "..." if len(
                        example['user_message']) > 100 else example['user_message']
                    shannon_response = example['shanbot_response']
                    rationale = f" ({example['rationale']})" if example['rationale'] else ""
                    few_shot_section += f"\nExample {i}:\nUser: {user_msg}\nShannon: {shannon_response}{rationale}\n"

            prompt = f"""You are Shannon, a casual Australian fitness coach reaching out to someone on Instagram.

            TIMING CONTEXT: {timing_context}

            TOPIC TO DISCUSS: {topic}

            PREVIOUS CONVERSATION:
            {formatted_history}
            {few_shot_section}

            Create a casual, friendly follow-up message that:
            - Mimics Shannon's authentic style from the examples above
            - Acknowledges the time gap appropriately (if relevant)
            - Transitions naturally into the topic
            - Feels personal and conversational
            - Is between 1-15 words total
            - Uses Shannon's relaxed Australian tone

            Generate ONLY the message, no other text:"""

            return call_gemini_with_retry_sync(GEMINI_MODEL_PRO, prompt)
        except Exception as e:
            logger.error(f"Error generating message: {e}")
            return None

# Enhanced analysis functions for smart follow-up insights


def analyze_conversation_context(metrics):
    """Analyze conversation history to extract smart insights."""
    conversation_history = metrics.get('conversation_history', [])

    if not conversation_history:
        return {
            'recent_context': "No conversation history available",
            'interests': [],
            'conversation_style': "Unknown",
            'response_pattern': "Unknown",
            'last_message_direction': "Unknown",
            'momentum': "Unknown"
        }

    # Get recent messages for context
    recent_messages = conversation_history[-5:]
    recent_context = []
    user_messages = []

    for msg in recent_messages:
        if msg.get('type') == 'user':
            recent_context.append(msg.get('text', ''))
            user_messages.append(msg.get('text', ''))

    # Extract interests from recent messages
    interests = []
    context_text = ' '.join(recent_context).lower()

    # Simple keyword extraction for interests
    interest_keywords = {
        'fitness': ['gym', 'workout', 'training', 'exercise', 'weights', 'cardio'],
        'technology': ['ai', 'tech', 'microsoft', 'software', 'app', 'programming'],
        'nutrition': ['food', 'eating', 'protein', 'diet', 'meal', 'calories'],
        'lifestyle': ['work', 'busy', 'travel', 'family', 'weekend', 'holiday'],
        'health': ['tired', 'energy', 'sleep', 'stress', 'recovery', 'pain']
    }

    for category, keywords in interest_keywords.items():
        if any(keyword in context_text for keyword in keywords):
            interests.append(category)

    # Analyze conversation style
    style_indicators = []
    if any(word in context_text for word in ['mate', 'bro', 'hey', 'yo']):
        style_indicators.append('casual')
    if any(word in context_text for word in ['haha', 'lol', '!', 'nice']):
        style_indicators.append('friendly')
    if any(word in context_text for word in ['thanks', 'appreciate', 'helpful']):
        style_indicators.append('appreciative')

    conversation_style = ', '.join(
        style_indicators) if style_indicators else 'neutral'

    # Determine last message direction
    last_message = conversation_history[-1] if conversation_history else {}
    last_message_direction = "User replied" if last_message.get(
        'type') == 'user' else "Shannon messaged"

    # Calculate response pattern
    user_response_count = len(
        [msg for msg in conversation_history if msg.get('type') == 'user'])
    total_messages = len(conversation_history)

    if user_response_count > 20:
        response_pattern = "Very active (20+ responses)"
    elif user_response_count > 10:
        response_pattern = "Active (10+ responses)"
    elif user_response_count > 5:
        response_pattern = "Moderate (5+ responses)"
    else:
        response_pattern = "Low activity (<5 responses)"

    # Determine conversation momentum
    if last_message.get('type') == 'user':
        momentum = "Active (they replied last)"
    else:
        days_since_last = (datetime.now() - datetime.fromisoformat(last_message.get(
            'timestamp', '').split('+')[0])).days if last_message.get('timestamp') else 999
        if days_since_last <= 1:
            momentum = "Recent (Shannon messaged yesterday)"
        elif days_since_last <= 3:
            momentum = "Cooling (Shannon messaged 2-3 days ago)"
        else:
            momentum = "Cold (No recent activity)"

    return {
        'recent_context': ' | '.join(recent_context[-3:]) if recent_context else "No recent messages",
        'interests': interests,
        'conversation_style': conversation_style,
        'response_pattern': response_pattern,
        'last_message_direction': last_message_direction,
        'momentum': momentum,
        'user_message_count': user_response_count,
        'total_message_count': total_messages
    }


def suggest_smart_topics(metrics, conversation_context):
    """Generate AI-powered topic suggestions based on conversation context."""
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY in ["YOUR_GEMINI_API_KEY", "your_gemini_api_key_here"]:
            return ["Ask about their current training", "Check in on their goals", "Share a fitness tip"]

        # Build context for AI
        recent_context = conversation_context['recent_context']
        interests = ', '.join(
            conversation_context['interests']) if conversation_context['interests'] else 'general fitness'
        conversation_style = conversation_context['conversation_style']

        conversation_history = metrics.get('conversation_history', [])
        formatted_history = ""
        for msg in conversation_history[-5:]:
            sender = "User" if msg.get('type') == 'user' else "Shannon"
            formatted_history += f"{sender}: {msg.get('text', '')}\n"

        prompt = f"""
Based on this conversation context, suggest 3 specific follow-up topics for Shannon to message about:

Recent conversation context: {recent_context}
User's interests: {interests}
Conversation style: {conversation_style}
Recent messages:
{formatted_history}

Shannon is a casual Australian fitness coach. Generate 3 specific, actionable follow-up topics that:
1. Reference something from their recent messages
2. Are relevant to their interests
3. Match the casual conversation style
4. Include a natural question or talking point

Format: Just list 3 topics, one per line, starting with an emoji. Keep each topic to one short sentence.

Example format:
💪 Follow up on their AI interests - ask what they've been watching lately
🎯 Check how their current training is going since they mentioned being busy
🤖 Share a cool fitness tech tip related to their Microsoft interest
"""

        response = call_gemini_with_retry_sync(GEMINI_MODEL_PRO, prompt)
        if response:
            # Split response into topics and clean up
            topics = [topic.strip()
                      for topic in response.split('\n') if topic.strip()]
            return topics[:3]  # Return max 3 topics
        else:
            return ["Ask about their current training", "Check in on their goals", "Share a fitness tip"]

    except Exception as e:
        logger.error(f"Error generating smart topics: {e}")
        return ["Ask about their current training", "Check in on their goals", "Share a fitness tip"]


def calculate_conversation_metrics(metrics):
    """Calculate detailed conversation metrics and follow-up history."""
    conversation_history = metrics.get('conversation_history', [])

    if not conversation_history:
        return {
            'avg_response_time': "No data",
            'shannon_last_message_ago': "No data",
            'followup_history': [],
            'success_rate': "No data",
            'best_contact_time': "No data"
        }

    # Find Shannon's messages to track follow-ups
    shannon_messages = [
        msg for msg in conversation_history if msg.get('type') != 'user']
    user_messages = [
        msg for msg in conversation_history if msg.get('type') == 'user']

    # Calculate time since Shannon's last message
    shannon_last_message = None
    for msg in reversed(conversation_history):
        if msg.get('type') != 'user':
            shannon_last_message = msg
            break

    shannon_last_message_ago = "No Shannon messages"
    if shannon_last_message and shannon_last_message.get('timestamp'):
        try:
            last_msg_time = datetime.fromisoformat(
                shannon_last_message['timestamp'].split('+')[0])
            days_ago = (datetime.now() - last_msg_time).days
            hours_ago = (datetime.now() - last_msg_time).seconds // 3600

            if days_ago > 0:
                shannon_last_message_ago = f"{days_ago} days ago"
            elif hours_ago > 0:
                shannon_last_message_ago = f"{hours_ago} hours ago"
            else:
                shannon_last_message_ago = "Less than 1 hour ago"
        except:
            shannon_last_message_ago = "Unknown"

    # Estimate follow-up history (Shannon messages that weren't direct responses)
    followup_history = []
    for i, msg in enumerate(shannon_messages[-5:]):  # Last 5 Shannon messages
        if msg.get('timestamp'):
            try:
                msg_time = datetime.fromisoformat(
                    msg['timestamp'].split('+')[0])
                # Simple heuristic: if Shannon message isn't immediately after user message, it's likely a follow-up
                is_followup = True
                if i > 0:
                    # Check if there was a user message just before this Shannon message
                    for j in range(len(conversation_history)):
                        if conversation_history[j] == msg and j > 0:
                            prev_msg = conversation_history[j-1]
                            if prev_msg.get('type') == 'user':
                                is_followup = False
                            break

                if is_followup:
                    followup_history.append(msg_time.strftime('%b %d'))
            except:
                pass

    # Calculate response success rate
    success_rate = "No data"
    if len(shannon_messages) > 0:
        # Simple heuristic: count user messages that came after Shannon messages
        responses_after_shannon = 0
        for i, msg in enumerate(conversation_history[:-1]):
            if msg.get('type') != 'user':  # Shannon message
                # Check if next message is from user
                next_msg = conversation_history[i+1]
                if next_msg.get('type') == 'user':
                    responses_after_shannon += 1

        if len(shannon_messages) > 0:
            rate = (responses_after_shannon / len(shannon_messages)) * 100
            success_rate = f"{rate:.0f}%"

    # Analyze message timing for best contact time
    user_times = []
    for msg in user_messages:
        if msg.get('timestamp'):
            try:
                msg_time = datetime.fromisoformat(
                    msg['timestamp'].split('+')[0])
                hour = msg_time.hour
                user_times.append(hour)
            except:
                pass

    best_contact_time = "No data"
    if user_times:
        # Find most common hour range
        morning = sum(1 for h in user_times if 6 <= h < 12)
        afternoon = sum(1 for h in user_times if 12 <= h < 18)
        evening = sum(1 for h in user_times if 18 <= h <= 23)
        night = sum(1 for h in user_times if 0 <= h < 6)

        max_time = max(morning, afternoon, evening, night)
        if max_time == morning:
            best_contact_time = "Mornings (6am-12pm)"
        elif max_time == afternoon:
            best_contact_time = "Afternoons (12pm-6pm)"
        elif max_time == evening:
            best_contact_time = "Evenings (6pm-11pm)"
        else:
            best_contact_time = "Late night/Early morning"

    return {
        'shannon_last_message_ago': shannon_last_message_ago,
        'followup_history': followup_history,
        'success_rate': success_rate,
        'best_contact_time': best_contact_time,
        'total_shannon_messages': len(shannon_messages),
        'total_user_messages': len(user_messages)
    }


def display_enhanced_user_followup(user_followup_info, all_analytics_data, auto_analyze=False):
    """Enhanced user follow-up display with optional smart insights and recommendations."""
    username = user_followup_info['username']

    # Get user data
    user_container = all_analytics_data.get('conversations', {}).get(username)
    if not user_container or 'metrics' not in user_container:
        st.error(f"Could not find data for user '{username}'.")
        return

    metrics = user_container['metrics']

    # Only run AI analysis if requested or if already generated
    if auto_analyze or f"analysis_{username}" in st.session_state:
        if f"analysis_{username}" not in st.session_state:
            conversation_context = analyze_conversation_context(metrics)
            conv_metrics = calculate_conversation_metrics(metrics)
            smart_topics = suggest_smart_topics(metrics, conversation_context)

            # Store results in session state to avoid re-running
            st.session_state[f"analysis_{username}"] = {
                'conversation_context': conversation_context,
                'conv_metrics': conv_metrics,
                'smart_topics': smart_topics
            }
        else:
            # Use cached analysis
            cached = st.session_state[f"analysis_{username}"]
            conversation_context = cached['conversation_context']
            conv_metrics = cached['conv_metrics']
            smart_topics = cached['smart_topics']
    else:
        # Provide basic fallbacks without AI analysis
        conversation_context = {
            'recent_context': "Click 'Generate Analysis' to analyze conversation",
            'interests': [],
            'conversation_style': "Not analyzed",
            'response_pattern': f"{user_followup_info['response_count']} responses",
            'last_message_direction': "Unknown",
            'momentum': "Unknown"
        }
        conv_metrics = {
            'shannon_last_message_ago': "Not analyzed",
            'followup_history': [],
            'success_rate': "Not analyzed",
            'best_contact_time': "Not analyzed",
            'total_shannon_messages': 0,
            'total_user_messages': 0
        }
        smart_topics = [
            "Click 'Generate Analysis' below to get AI suggestions"]

    # Determine response level and color
    response_count = user_followup_info['response_count']
    if response_count >= 20:
        response_emoji = "🟢"
        response_level = "High Responder"
    elif response_count >= 11:
        response_emoji = "🟡"
        response_level = "Medium Responder"
    else:
        response_emoji = "🟠"
        response_level = "Low Responder"

    # Create expander with enhanced title
    title = f"{response_emoji} {username} - {user_followup_info['days_since_last_message']} days since last message ({response_level})"

    with st.expander(title, expanded=False):

        # === ENHANCED USER INFORMATION SECTION ===
        col_info, col_history = st.columns([1, 1])

        with col_info:
            st.write("### 📊 Enhanced User Information")

            col_basic, col_timing = st.columns([1, 1])

            with col_basic:
                st.write(
                    f"**Response count:** {response_count} {response_emoji}")
                st.write(f"**Response level:** {response_level}")
                st.write(
                    f"**Last message:** {user_followup_info['last_message_time'].strftime('%Y-%m-%d %H:%M')}")
                st.write(
                    f"**Last message direction:** {conversation_context['last_message_direction']}")

            with col_timing:
                st.write(
                    f"**Shannon's last message:** {conv_metrics['shannon_last_message_ago']}")
                st.write(
                    f"**Follow-up success rate:** {conv_metrics['success_rate']}")
                st.write(
                    f"**Best contact time:** {conv_metrics['best_contact_time']}")
                st.write(
                    f"**Conversation momentum:** {conversation_context['momentum']}")

            # Follow-up history
            if conv_metrics['followup_history']:
                st.write("**Previous follow-ups:** " +
                         " | ".join(conv_metrics['followup_history'][-3:]))
            else:
                st.write("**Previous follow-ups:** None tracked")

        with col_history:
            st.write("### 💬 Conversation Context")

            # Recent context
            if conversation_context['recent_context'] != "No recent messages":
                st.write("**Recent context:**")
                st.info(f"💭 {conversation_context['recent_context']}")

            # Detected interests
            if conversation_context['interests']:
                st.write("**Detected interests:**")
                interests_str = " | ".join(
                    [f"#{interest}" for interest in conversation_context['interests']])
                st.write(f"🎯 {interests_str}")
            else:
                st.write("**Detected interests:** None detected")

            # Conversation style
            st.write(
                f"**Conversation style:** {conversation_context['conversation_style']}")
            st.write(
                f"**Activity pattern:** {conversation_context['response_pattern']}")

        st.divider()

        # === SMART TOPIC SUGGESTIONS SECTION ===
        st.write("### 🧠 Smart Topic Suggestions")
        st.caption(
            "AI-generated suggestions based on conversation context and interests")

        if smart_topics and smart_topics != ["Click 'Generate Analysis' below to get AI suggestions"]:
            for i, topic in enumerate(smart_topics, 1):
                st.write(f"**{i}.** {topic}")

            # Refresh topics button (only show if analysis has been done)
            if st.button(f"🔄 Refresh Smart Topics", key=f"refresh_topics_{username}"):
                with st.spinner("Generating new topic suggestions..."):
                    conversation_context = analyze_conversation_context(
                        metrics)
                    new_topics = suggest_smart_topics(
                        metrics, conversation_context)
                    if new_topics:
                        # Update cached analysis
                        st.session_state[f"analysis_{username}"]["smart_topics"] = new_topics
                        st.session_state[f"analysis_{username}"]["conversation_context"] = conversation_context
                        st.success("✨ New topics generated!")
                        st.rerun()
        else:
            st.info("💡 Click 'Generate Analysis' below to get AI suggestions")

            # Generate analysis button for individual users
            if st.button(f"🤖 Generate Analysis", key=f"generate_analysis_{username}", type="primary"):
                with st.spinner(f"Analyzing conversation for {username}..."):
                    conversation_context = analyze_conversation_context(
                        metrics)
                    conv_metrics = calculate_conversation_metrics(metrics)
                    smart_topics = suggest_smart_topics(
                        metrics, conversation_context)

                    # Store results in session state
                    st.session_state[f"analysis_{username}"] = {
                        'conversation_context': conversation_context,
                        'conv_metrics': conv_metrics,
                        'smart_topics': smart_topics
                    }
                    st.success(f"✅ Analysis complete for {username}!")
                    st.rerun()

        st.divider()

        # === MESSAGE STRATEGY RECOMMENDATIONS ===
        st.write("### 🎯 Follow-up Strategy Recommendations")

        strategy_col1, strategy_col2 = st.columns([1, 1])

        with strategy_col1:
            # Timing recommendation
            days_since = user_followup_info['days_since_last_message']
            if conversation_context['last_message_direction'] == "User replied":
                timing_status = "✅ Good to contact"
                timing_reason = "They replied last - your turn to message"
            elif days_since >= 7:
                timing_status = "🚨 Urgent follow-up"
                timing_reason = f"{days_since} days without contact"
            elif days_since >= 3:
                timing_status = "⏰ Ready for follow-up"
                timing_reason = f"{days_since} days since last message"
            else:
                timing_status = "⏳ Still early"
                timing_reason = f"Only {days_since} days since last message"

            st.write(f"**Timing status:** {timing_status}")
            st.write(f"**Reason:** {timing_reason}")

        with strategy_col2:
            # Message approach recommendation
            if conversation_context['interests']:
                approach = f"Reference their {conversation_context['interests'][0]} interest"
            else:
                approach = "General fitness check-in"

            if conversation_context['conversation_style'] == 'casual':
                tone = "Keep it casual and friendly"
            else:
                tone = "Professional but warm tone"

            st.write(f"**Suggested approach:** {approach}")
            st.write(f"**Recommended tone:** {tone}")

        st.divider()

        # === CONVERSATION HISTORY SECTION ===
        st.write("### 📜 Recent Conversation History")
        conversation_history = metrics.get('conversation_history', [])

        if conversation_history:
            st.write("**Last 5 messages:**")
            history_container = st.container()
            with history_container:
                for i, msg in enumerate(conversation_history[-5:]):
                    sender = "👤 User" if msg.get(
                        'type') == 'user' else "🤖 Shannon"
                    timestamp = ""
                    if msg.get('timestamp'):
                        try:
                            msg_time = datetime.fromisoformat(
                                msg['timestamp'].split('+')[0])
                            timestamp = f" ({msg_time.strftime('%b %d, %H:%M')})"
                        except:
                            pass

                    # Truncate long messages
                    text = msg.get('text', '')
                    if len(text) > 100:
                        text = text[:100] + "..."

                    st.write(f"**{sender}**{timestamp}: {text}")
        else:
            st.info("No conversation history available")

        st.divider()

        # === MESSAGE GENERATION AND ACTIONS ===
        st.write("### ✍️ Generate Follow-up Message")

        # Check if message already generated
        message_key = f"generated_message_{username}"
        topic_key = f"selected_topic_{username}"

        if message_key in st.session_state and st.session_state[message_key]:
            st.write("**Generated Message:**")

            # Create dynamic key to force text area refresh on regeneration
            regeneration_count = st.session_state.get(
                f"regen_count_{username}", 0)
            text_area_key = f"edit_{username}_{regeneration_count}"

            # Allow editing of the generated message
            edited_message = st.text_area(
                "Edit message before queuing:",
                value=st.session_state[message_key],
                key=text_area_key,
                height=120,
                help="Review and edit the message to make it perfect before queuing"
            )

            # Update stored message if edited
            if edited_message != st.session_state[message_key]:
                st.session_state[message_key] = edited_message

            # Action buttons
            col_regen, col_queue, col_clear = st.columns([1, 1, 1])

            with col_regen:
                if st.button("🔄 Regenerate", key=f"regen_{username}", use_container_width=True):
                    with st.spinner("Regenerating message..."):
                        # Use smart topic if available
                        topic_to_use = smart_topics[0] if smart_topics else "General follow-up"
                        new_message = generate_follow_up_message(
                            conversation_history, topic_to_use, user_followup_info.get('days_since_last_message', None))
                        if new_message:
                            st.session_state[message_key] = new_message
                            st.session_state[topic_key] = topic_to_use
                            # Store original for learning comparison
                            st.session_state[f"original_generated_{username}"] = new_message
                            # Increment regeneration count to force text area refresh
                            current_count = st.session_state.get(
                                f"regen_count_{username}", 0)
                            st.session_state[f"regen_count_{username}"] = current_count + 1
                            st.success("✅ Message regenerated!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to regenerate message")

            with col_queue:
                if st.button("📤 Queue Message", key=f"queue_{username}", type="primary", use_container_width=True):
                    # Initialize message queue if not exists
                    if 'message_queue' not in st.session_state:
                        st.session_state.message_queue = []

                    # Add to queue
                    topic_used = st.session_state.get(topic_key, "Follow-up")
                    st.session_state.message_queue.append({
                        'username': username,
                        'message': edited_message,
                        'topic': topic_used,
                        'queued_time': datetime.now().isoformat()
                    })

                    # LEARNING LOG: Save follow-up edits for training
                    try:
                        from dashboard_sqlite_utils import add_to_learning_log

                        # Get the original AI-generated message
                        original_key = f"original_generated_{username}"
                        original_message = st.session_state.get(
                            original_key, "")

                        # Check if Shannon edited the message
                        if original_message and original_message.strip() != edited_message.strip():
                            # Create a mock conversation context for learning log
                            last_user_message = ""
                            if conversation_history:
                                for msg in reversed(conversation_history):
                                    if msg.get('type') == 'user':
                                        last_user_message = msg.get('text', '')
                                        break

                            # Build the prompt context that was used
                            timing_context = ""
                            days_since_last = user_followup_info.get(
                                'days_since_last_message', None)
                            if days_since_last:
                                if days_since_last <= 2:
                                    timing_context = f"Recent follow-up ({days_since_last} days)"
                                elif days_since_last <= 7:
                                    timing_context = f"Weekly follow-up ({days_since_last} days)"
                                elif days_since_last <= 14:
                                    timing_context = f"Bi-weekly follow-up ({days_since_last} days)"
                                else:
                                    timing_context = f"Re-engagement ({days_since_last} days)"

                            prompt_context = f"Follow-up message for {username}. Topic: {topic_used}. {timing_context}. Last user message: {last_user_message[:100]}"

                            # Save to learning log (use negative review_id for follow-ups to distinguish from main chat)
                            learning_review_id = - \
                                (int(datetime.now().timestamp()))

                            add_to_learning_log(
                                review_id=learning_review_id,
                                user_ig_username=username,
                                user_subscriber_id="",  # Not applicable for follow-ups
                                original_prompt_text=prompt_context,
                                original_gemini_response=original_message,
                                edited_response_text=edited_message,
                                user_notes=f"Follow-up message edit - Topic: {topic_used}",
                                is_good_example_for_few_shot=1  # Mark as good example
                            )

                            logger.info(
                                f"Saved follow-up edit to learning log for {username}")
                            st.toast(
                                "📚 Message edit saved for AI training!", icon="🎯")

                        # Clean up the original message key
                        if original_key in st.session_state:
                            del st.session_state[original_key]

                    except Exception as e:
                        logger.error(
                            f"Error saving follow-up edit to learning log: {e}")
                        # Don't block the queue operation if learning log fails

                    st.success(f"✅ Message queued for {username}!")

                    # Clear the generated message after queuing
                    if message_key in st.session_state:
                        del st.session_state[message_key]
                    if topic_key in st.session_state:
                        del st.session_state[topic_key]

                    st.rerun()

            with col_clear:
                if st.button("🗑️ Clear", key=f"clear_{username}", use_container_width=True):
                    if message_key in st.session_state:
                        del st.session_state[message_key]
                    if topic_key in st.session_state:
                        del st.session_state[topic_key]
                    st.info("Message cleared")
                    st.rerun()

        else:
            # Show generation options
            st.write("**Generate a personalized follow-up message:**")

            col_gen1, col_gen2 = st.columns([1, 1])

            with col_gen1:
                if st.button("🤖 Smart Generate", key=f"smart_gen_{username}", type="primary", use_container_width=True):
                    with st.spinner("Generating smart follow-up..."):
                        # Use the first smart topic
                        topic_to_use = smart_topics[0] if smart_topics else "General follow-up"
                        message = generate_follow_up_message(
                            conversation_history, topic_to_use, user_followup_info.get('days_since_last_message', None))
                        if message:
                            st.session_state[message_key] = message
                            st.session_state[topic_key] = topic_to_use
                            # Store original for learning comparison
                            st.session_state[f"original_generated_{username}"] = message
                            st.success("✅ Smart message generated!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to generate message")

            with col_gen2:
                if st.button("📝 Basic Generate", key=f"basic_gen_{username}", use_container_width=True):
                    with st.spinner("Generating basic follow-up..."):
                        basic_topic = "General catch-up and check-in"
                        message = generate_follow_up_message(
                            conversation_history, basic_topic, user_followup_info.get('days_since_last_message', None))
                        if message:
                            st.session_state[message_key] = message
                            st.session_state[topic_key] = basic_topic
                            # Store original for learning comparison
                            st.session_state[f"original_generated_{username}"] = message
                            st.success("✅ Basic message generated!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to generate message")


# Use our enhanced version as the display function
display_user_followup = display_enhanced_user_followup

# Ensure enhanced function is used throughout the module
display_user_followup = display_enhanced_user_followup


def get_recent_users_with_details(analytics_data_dict):
    """Get users from last 30 days with full data structure for followup manager."""
    current_time = datetime.now()
    thirty_days_ago = current_time - timedelta(days=30)

    recent_users = []
    conversations_data = analytics_data_dict.get('conversations', {})

    for username, user_container in conversations_data.items():
        metrics = user_container.get('metrics', {})
        if not metrics:
            continue

        # Try to get last interaction time
        last_interaction = None
        last_interaction_ts_str = metrics.get('last_interaction_timestamp')

        if last_interaction_ts_str:
            try:
                last_interaction = datetime.fromisoformat(
                    last_interaction_ts_str.split('+')[0])
            except (ValueError, AttributeError):
                pass

        # Fallback to conversation history
        if not last_interaction:
            conversation_history = metrics.get('conversation_history', [])
            if conversation_history:
                try:
                    last_msg = conversation_history[-1]
                    last_interaction = datetime.fromisoformat(
                        last_msg.get('timestamp', '').split('+')[0])
                except (ValueError, AttributeError):
                    pass

        # If we found a valid timestamp and it's within 30 days
        if last_interaction and last_interaction >= thirty_days_ago:
            conversation_history = metrics.get('conversation_history', [])
            user_messages = sum(
                1 for msg in conversation_history if msg.get('type') == 'user')
            ai_messages = sum(
                1 for msg in conversation_history if msg.get('type') != 'user')

            recent_users.append({
                'username': username,
                'ig_username': metrics.get('ig_username', username),
                'last_interaction': last_interaction,
                'days_ago': (current_time - last_interaction).days,
                'user_messages': user_messages,
                'ai_messages': ai_messages,
                'total_messages': len(conversation_history),
                'metrics': metrics
            })

    # Sort by most recent interaction first
    recent_users.sort(key=lambda x: x['last_interaction'], reverse=True)
    return recent_users


def display_followup_manager(analytics_data_dict):
    """Consolidated follow-up management combining scheduled follow-ups, recent interactions, and bulk tools"""
    st.header("📬 Follow-up Manager")

    # --- REFACTORED: Efficient Queue Processing Logic ---
    if 'generation_queue' in st.session_state and st.session_state.generation_queue:
        queue = st.session_state.generation_queue
        total_in_queue = st.session_state.get(
            'generation_queue_total', len(queue))

        # Get the next username to process
        username_to_process = queue[0]

        # Directly and efficiently get the user's data
        user_container = analytics_data_dict.get(
            'conversations', {}).get(username_to_process)

        # Display progress bar
        progress_value = (total_in_queue - len(queue) + 1) / total_in_queue
        st.progress(
            progress_value, text=f"Generating for {username_to_process}... ({total_in_queue - len(queue) + 1}/{total_in_queue})")

        if user_container and 'metrics' in user_container:
            metrics = user_container['metrics']

            # Generate message logic
            user_category = get_user_category(metrics)
            current_topic = get_topic_for_category(user_category, metrics)
            conversation_history = metrics.get('conversation_history', [])

            # Find the user_info for this username from followup data
            user_info = None
            followup_data_list = get_users_ready_for_followup(
                analytics_data_dict)
            for category in ['high_responders', 'medium_responders', 'low_responders']:
                for user in followup_data_list[category]:
                    if user['username'] == username_to_process:
                        user_info = user
                        break
                if user_info:
                    break

            days_since_last = user_info.get(
                'days_since_last_message', None) if user_info else None

            generated_message = generate_follow_up_message(
                conversation_history, current_topic, days_since_last)

            if generated_message:
                st.session_state[f"generated_message_{username_to_process}"] = generated_message
                st.session_state[f"selected_topic_{username_to_process}"] = current_topic
                logger.info(
                    f"Successfully generated message for {username_to_process}")
            else:
                logger.error(
                    f"Failed to generate message for {username_to_process}")
        else:
            logger.error(
                f"Could not find data for user '{username_to_process}' in queue. Skipping.")

        # Pop the processed user from the queue and rerun for the next one
        st.session_state.generation_queue.pop(0)
        st.rerun()

    # --- UI Display Logic ---
    else:
        if 'generation_queue' in st.session_state:
            # This block runs when the queue has just finished
            st.success("✅ All follow-up messages generated successfully!")
            st.balloons()
            # Clean up session state variables
            del st.session_state['generation_queue']
            if 'generation_queue_total' in st.session_state:
                del st.session_state['generation_queue_total']

        # Display the main UI only when not processing a queue

        # Initialize session state for followup data
        if 'followup_data_loaded' not in st.session_state:
            st.session_state.followup_data_loaded = False
            st.session_state.followup_data_list = None

        # Quick load button instead of automatic loading
        if not st.session_state.followup_data_loaded:
            st.info(
                "💡 **Follow-up Manager Ready** - Click below to load your leads ready for follow-up")

            col_load, col_info = st.columns([1, 2])
            with col_load:
                if st.button("🔄 Load Follow-up Data", type="primary", use_container_width=True):
                    with st.spinner("Loading follow-up data from 748 leads..."):
                        st.session_state.followup_data_list = get_users_ready_for_followup(
                            analytics_data_dict)
                        st.session_state.followup_data_loaded = True
                        st.success(
                            f"✅ Loaded! Found {st.session_state.followup_data_list['total_count']} leads ready for follow-up")
                        st.rerun()

            with col_info:
                st.caption(
                    "This will analyze your conversation data to find leads ready for follow-up based on:")
                st.caption(
                    "• **High responders** (20+ messages): 2+ days since last contact")
                st.caption(
                    "• **Medium responders** (11-19 messages): 5+ days since last contact")
                st.caption(
                    "• **Low responders** (1-10 messages): 7+ days since last contact")

                # Add refresh button to clear cache
                if st.button("🔄 Reset Data", help="Clear loaded data to reload fresh"):
                    st.session_state.followup_data_loaded = False
                    st.session_state.followup_data_list = None
                    st.rerun()

            return

        # Data is loaded - proceed with normal display
        try:
            followup_data_list = st.session_state.followup_data_list

            # Validate that we got the expected dictionary structure
            if not isinstance(followup_data_list, dict):
                st.error(
                    f"⚠️ Follow-up data returned unexpected type: {type(followup_data_list)}")
                st.error(f"Data: {str(followup_data_list)[:200]}...")
                return

            # Ensure all required keys exist
            required_keys = ['high_responders',
                             'medium_responders', 'low_responders', 'total_count']
            for key in required_keys:
                if key not in followup_data_list:
                    st.error(
                        f"⚠️ Missing required key '{key}' in follow-up data")
                    followup_data_list[key] = [] if key != 'total_count' else 0

        except Exception as e:
            st.error(f"⚠️ Error getting follow-up data: {str(e)}")
            # Provide fallback empty structure
            followup_data_list = {
                'high_responders': [],
                'medium_responders': [],
                'low_responders': [],
                'total_count': 0
            }

        # Create tabs for the three main sections
        tab1, tab2, tab3 = st.tabs(
            ["🎯 Ready for Follow-up", "💬 Recent Interactions", "📤 Bulk Actions"])

        with tab1:
            st.subheader("Users Ready for Follow-up")
            st.caption("Based on response patterns and wait times")

            # Display summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Ready", followup_data_list['total_count'])
            with col2:
                high_count = len(followup_data_list['high_responders'])
                st.metric("High Responders (48h)", high_count)
            with col3:
                medium_count = len(followup_data_list['medium_responders'])
                st.metric("Medium Responders (5d)", medium_count)
            with col4:
                low_count = len(followup_data_list['low_responders'])
                st.metric("Low Responders (7d)", low_count)

            # Display queued messages if any exist
            if 'message_queue' in st.session_state and st.session_state.message_queue:
                st.info(
                    f"📬 {len(st.session_state.message_queue)} messages queued for sending")

                col_view, col_send = st.columns([1, 1])
                with col_view:
                    if st.button("👀 View Queued Messages", use_container_width=True):
                        with st.expander("Queued Messages", expanded=True):
                            for msg_item in st.session_state.message_queue:
                                st.write(f"**To:** {msg_item['username']}")
                                st.write(f"**Topic:** {msg_item['topic']}")
                                st.write(f"**Message:** {msg_item['message']}")
                                st.write("---")

                with col_send:
                    if st.button("🚀 Send All Queued", type="primary", use_container_width=True):
                        if save_followup_queue():
                            st.success(
                                "✅ All messages sent to auto_response_sender.py for processing!")
                            st.info("💡 Starting Instagram automation browser...")

                            # Actually start the auto_response_sender script
                            try:
                                import subprocess
                                import os

                                # Path to your auto_response_sender.py script
                                sender_script_rel_to_cwd = os.path.join(
                                    "app", "dashboard_modules", "auto_response_sender.py")

                                # Check absolute path
                                absolute_sender_script_path = os.path.join(
                                    r"C:\Users\Shannon\OneDrive\Desktop\shanbot",
                                    sender_script_rel_to_cwd
                                )

                                if os.path.exists(absolute_sender_script_path):
                                    # Start the auto_response_sender in a new process
                                    st.info(
                                        "🔄 Starting Instagram automation script...")

                                    process = subprocess.Popen([
                                        "python",
                                        sender_script_rel_to_cwd
                                    ],
                                        cwd=r"C:\Users\Shannon\OneDrive\Desktop\shanbot",
                                        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(
                                            subprocess, 'CREATE_NEW_CONSOLE') else 0
                                    )

                                    st.success(
                                        "🚀 Instagram automation started! Browser should open in a few seconds.")
                                    st.info(
                                        "📝 The browser will stay open and process your queued messages automatically.")
                                    st.session_state.message_queue = []
                                    st.rerun()
                                else:
                                    st.error(
                                        f"❌ auto_response_sender.py not found at: {absolute_sender_script_path}")
                                    st.info(
                                        "💡 Messages saved to queue file - you can manually run auto_response_sender.py")

                            except Exception as e:
                                st.error(
                                    f"❌ Failed to start Instagram automation: {str(e)}")
                                st.info(
                                    "💡 Messages saved to queue file - you can manually run auto_response_sender.py from the command line")
                                st.session_state.message_queue = []
                                st.rerun()
                        else:
                            st.error("❌ Failed to save messages to queue")

            # Create sub-tabs for different response levels
            if followup_data_list['total_count'] > 0:
                high_sub, medium_sub, low_sub = st.tabs([
                    f"🟢 High ({high_count})",
                    f"🟡 Medium ({medium_count})",
                    f"🟠 Low ({low_count})"
                ])

                with high_sub:
                    # Action buttons for high responders
                    col_gen, col_queue = st.columns([1, 1])

                    with col_gen:
                        if st.button("🤖 Analyze All High Responders", key="tab1_gen_high", use_container_width=True):
                            users_to_queue = [user['username']
                                              for user in followup_data_list['high_responders']]
                            if users_to_queue:
                                # Trigger AI analysis for all high responders
                                with st.spinner(f"Analyzing {len(users_to_queue)} high responders..."):
                                    for user_info in followup_data_list['high_responders']:
                                        username = user_info['username']
                                        user_container = analytics_data_dict.get(
                                            'conversations', {}).get(username)
                                        if user_container and 'metrics' in user_container:
                                            metrics = user_container['metrics']

                                            # Run AI analysis and cache results
                                            conversation_context = analyze_conversation_context(
                                                metrics)
                                            conv_metrics = calculate_conversation_metrics(
                                                metrics)
                                            smart_topics = suggest_smart_topics(
                                                metrics, conversation_context)

                                            st.session_state[f"analysis_{username}"] = {
                                                'conversation_context': conversation_context,
                                                'conv_metrics': conv_metrics,
                                                'smart_topics': smart_topics
                                            }

                                st.session_state.generation_queue = users_to_queue
                                st.session_state.generation_queue_total = len(
                                    users_to_queue)
                                st.success(
                                    f"✅ Analysis complete for {len(users_to_queue)} high responders!")
                                st.rerun()

                    with col_queue:
                        if st.button("📤 Queue All High Responder Messages", key="tab1_queue_high", type="primary", use_container_width=True):
                            if not followup_data_list['high_responders']:
                                st.warning("No high responders to queue")
                            else:
                                queued_count = 0
                                with st.spinner(f"Generating and queueing messages for {len(followup_data_list['high_responders'])} high responders..."):
                                    for user_info in followup_data_list['high_responders']:
                                        username = user_info['username']
                                        user_container = analytics_data_dict.get(
                                            'conversations', {}).get(username)

                                        if user_container and 'metrics' in user_container:
                                            metrics = user_container['metrics']

                                            # Get user category and topic
                                            user_category = get_user_category(
                                                metrics)
                                            current_topic = get_topic_for_category(
                                                user_category, metrics)
                                            conversation_history = metrics.get(
                                                'conversation_history', [])

                                            # Generate message with timing context
                                            days_since_last = user_info.get(
                                                'days_since_last_message', None)
                                            generated_message = generate_follow_up_message(
                                                conversation_history, current_topic, days_since_last)

                                            if generated_message:
                                                # Add to queue
                                                if 'message_queue' not in st.session_state:
                                                    st.session_state.message_queue = []

                                                st.session_state.message_queue.append({
                                                    'username': username,
                                                    'message': generated_message,
                                                    'topic': current_topic,
                                                    'queued_time': datetime.now().isoformat()
                                                })
                                                queued_count += 1

                                if queued_count > 0:
                                    st.success(
                                        f"✅ Queued {queued_count} messages for high responders!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to queue any messages")

                    # Display users with their enhanced follow-up information
                    if followup_data_list['high_responders']:
                        # Show expandable list instead of auto-expanding all users
                        st.write(
                            f"**{len(followup_data_list['high_responders'])} high responders ready:**")

                        # Show first 3 by default, rest on demand
                        visible_count = 3
                        for i, user_info_item in enumerate(followup_data_list['high_responders']):
                            if i < visible_count:
                                display_enhanced_user_followup(
                                    user_info_item, analytics_data_dict, auto_analyze=False)
                            else:
                                break

                        # Show remaining users on demand
                        remaining = len(
                            followup_data_list['high_responders']) - visible_count
                        if remaining > 0:
                            # Use persistent session state for show more
                            if 'show_more_high_responders' not in st.session_state:
                                st.session_state.show_more_high_responders = False

                            if st.button(f"Show {remaining} more high responders", key="show_more_high"):
                                st.session_state.show_more_high_responders = True

                            if st.session_state.show_more_high_responders:
                                for user_info_item in followup_data_list['high_responders'][visible_count:]:
                                    display_enhanced_user_followup(
                                        user_info_item, analytics_data_dict, auto_analyze=False)

                                # Add a collapse button
                                if st.button("🔼 Hide additional high responders", key="hide_more_high"):
                                    st.session_state.show_more_high_responders = False
                                    st.rerun()
                    else:
                        st.info("No high responders ready for follow-up")

                with medium_sub:
                    # Action buttons for medium responders
                    col_gen, col_queue = st.columns([1, 1])

                    with col_gen:
                        if st.button("🤖 Analyze All Medium Responders", key="tab1_gen_med", use_container_width=True):
                            users_to_queue = [user['username']
                                              for user in followup_data_list['medium_responders']]
                            if users_to_queue:
                                # Trigger AI analysis for all medium responders
                                with st.spinner(f"Analyzing {len(users_to_queue)} medium responders..."):
                                    for user_info in followup_data_list['medium_responders']:
                                        username = user_info['username']
                                        user_container = analytics_data_dict.get(
                                            'conversations', {}).get(username)
                                        if user_container and 'metrics' in user_container:
                                            metrics = user_container['metrics']

                                            # Run AI analysis and cache results
                                            conversation_context = analyze_conversation_context(
                                                metrics)
                                            conv_metrics = calculate_conversation_metrics(
                                                metrics)
                                            smart_topics = suggest_smart_topics(
                                                metrics, conversation_context)

                                            st.session_state[f"analysis_{username}"] = {
                                                'conversation_context': conversation_context,
                                                'conv_metrics': conv_metrics,
                                                'smart_topics': smart_topics
                                            }

                                st.session_state.generation_queue = users_to_queue
                                st.session_state.generation_queue_total = len(
                                    users_to_queue)
                                st.success(
                                    f"✅ Analysis complete for {len(users_to_queue)} medium responders!")
                                st.rerun()

                    with col_queue:
                        if st.button("📤 Queue All Medium Responder Messages", key="tab1_queue_med", type="primary", use_container_width=True):
                            if not followup_data_list['medium_responders']:
                                st.warning("No medium responders to queue")
                            else:
                                queued_count = 0
                                with st.spinner(f"Generating and queueing messages for {len(followup_data_list['medium_responders'])} medium responders..."):
                                    for user_info in followup_data_list['medium_responders']:
                                        username = user_info['username']
                                        user_container = analytics_data_dict.get(
                                            'conversations', {}).get(username)

                                        if user_container and 'metrics' in user_container:
                                            metrics = user_container['metrics']

                                            # Get user category and topic
                                            user_category = get_user_category(
                                                metrics)
                                            current_topic = get_topic_for_category(
                                                user_category, metrics)
                                            conversation_history = metrics.get(
                                                'conversation_history', [])

                                            # Generate message with timing context
                                            days_since_last = user_info.get(
                                                'days_since_last_message', None)
                                            generated_message = generate_follow_up_message(
                                                conversation_history, current_topic, days_since_last)

                                            if generated_message:
                                                # Add to queue
                                                if 'message_queue' not in st.session_state:
                                                    st.session_state.message_queue = []

                                                st.session_state.message_queue.append({
                                                    'username': username,
                                                    'message': generated_message,
                                                    'topic': current_topic,
                                                    'queued_time': datetime.now().isoformat()
                                                })
                                                queued_count += 1

                                if queued_count > 0:
                                    st.success(
                                        f"✅ Queued {queued_count} messages for medium responders!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to queue any messages")

                    # Display users with their enhanced follow-up information
                    if followup_data_list['medium_responders']:
                        # Show expandable list instead of auto-expanding all users
                        st.write(
                            f"**{len(followup_data_list['medium_responders'])} medium responders ready:**")

                        # Show first 3 by default, rest on demand
                        visible_count = 3
                        for i, user_info_item in enumerate(followup_data_list['medium_responders']):
                            if i < visible_count:
                                display_enhanced_user_followup(
                                    user_info_item, analytics_data_dict, auto_analyze=False)
                            else:
                                break

                        # Show remaining users on demand
                        remaining = len(
                            followup_data_list['medium_responders']) - visible_count
                        if remaining > 0:
                            # Use persistent session state for show more
                            if 'show_more_medium_responders' not in st.session_state:
                                st.session_state.show_more_medium_responders = False

                            if st.button(f"Show {remaining} more medium responders", key="show_more_medium"):
                                st.session_state.show_more_medium_responders = True

                            if st.session_state.show_more_medium_responders:
                                for user_info_item in followup_data_list['medium_responders'][visible_count:]:
                                    display_enhanced_user_followup(
                                        user_info_item, analytics_data_dict, auto_analyze=False)

                                # Add a collapse button
                                if st.button("🔼 Hide additional medium responders", key="hide_more_medium"):
                                    st.session_state.show_more_medium_responders = False
                                    st.rerun()
                    else:
                        st.info("No medium responders ready for follow-up")

                with low_sub:
                    low_count = len(followup_data_list['low_responders'])

                    # Action buttons for low responders
                    col_gen, col_queue = st.columns([1, 1])

                    with col_gen:
                        st.write("**🤖 Analysis**")
                        if low_count > 50:
                            st.warning(
                                f"⚠️ {low_count} low responders - will use significant AI processing.")
                            confirm_low = st.button(
                                f"⚡ Analyze All {low_count} Low Responders", key="tab1_gen_low_confirm", type="secondary", use_container_width=True)
                        else:
                            confirm_low = st.button(
                                "🤖 Analyze All Low Responders", key="tab1_gen_low", use_container_width=True)

                        if confirm_low:
                            users_to_queue = [
                                user['username'] for user in followup_data_list['low_responders']]
                            if users_to_queue:
                                # Trigger AI analysis for all low responders
                                with st.spinner(f"Analyzing {len(users_to_queue)} low responders... This may take a while."):
                                    for user_info in followup_data_list['low_responders']:
                                        username = user_info['username']
                                        user_container = analytics_data_dict.get(
                                            'conversations', {}).get(username)
                                        if user_container and 'metrics' in user_container:
                                            metrics = user_container['metrics']

                                            # Run AI analysis and cache results
                                            conversation_context = analyze_conversation_context(
                                                metrics)
                                            conv_metrics = calculate_conversation_metrics(
                                                metrics)
                                            smart_topics = suggest_smart_topics(
                                                metrics, conversation_context)

                                            st.session_state[f"analysis_{username}"] = {
                                                'conversation_context': conversation_context,
                                                'conv_metrics': conv_metrics,
                                                'smart_topics': smart_topics
                                            }

                                st.session_state.generation_queue = users_to_queue
                                st.session_state.generation_queue_total = len(
                                    users_to_queue)
                                st.success(
                                    f"✅ Analysis complete for {len(users_to_queue)} low responders!")
                                st.rerun()

                    with col_queue:
                        st.write("**📤 Queue Messages**")
                        if low_count > 100:
                            st.warning(
                                f"⚠️ {low_count} low responders - this will take time!")
                            queue_confirm = st.button(
                                f"📤 Queue All {low_count} Low Responder Messages", key="tab1_queue_low_confirm", type="primary", use_container_width=True)
                        else:
                            queue_confirm = st.button(
                                "📤 Queue All Low Responder Messages", key="tab1_queue_low", type="primary", use_container_width=True)

                        if queue_confirm:
                            if not followup_data_list['low_responders']:
                                st.warning("No low responders to queue")
                            else:
                                queued_count = 0
                                with st.spinner(f"Generating and queueing messages for {low_count} low responders... This may take a while."):
                                    for user_info in followup_data_list['low_responders']:
                                        username = user_info['username']
                                        user_container = analytics_data_dict.get(
                                            'conversations', {}).get(username)

                                        if user_container and 'metrics' in user_container:
                                            metrics = user_container['metrics']

                                            # Get user category and topic
                                            user_category = get_user_category(
                                                metrics)
                                            current_topic = get_topic_for_category(
                                                user_category, metrics)
                                            conversation_history = metrics.get(
                                                'conversation_history', [])

                                            # Generate message using existing function with timing context
                                            generated_message = generate_follow_up_message(
                                                conversation_history, current_topic, user_info['days_ago'])

                                            if generated_message:
                                                # Add to queue
                                                if 'message_queue' not in st.session_state:
                                                    st.session_state.message_queue = []

                                                st.session_state.message_queue.append({
                                                    'username': username,
                                                    'message': generated_message,
                                                    'topic': current_topic,
                                                    'queued_time': datetime.now().isoformat()
                                                })
                                                queued_count += 1

                                if queued_count > 0:
                                    st.success(
                                        f"✅ Queued {queued_count} messages for low responders!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to queue any messages")

                    # Display users with their enhanced follow-up information
                    if followup_data_list['low_responders']:
                        low_count = len(followup_data_list['low_responders'])
                        st.write(f"**{low_count} low responders ready:**")

                        if low_count > 50:
                            st.warning(
                                f"⚠️ You have {low_count} low responders! Showing first 5 only to prevent performance issues.")
                            visible_count = 5
                        else:
                            visible_count = 3

                        # Show limited number by default
                        for i, user_info_item in enumerate(followup_data_list['low_responders']):
                            if i < visible_count:
                                display_enhanced_user_followup(
                                    user_info_item, analytics_data_dict, auto_analyze=False)
                            else:
                                break

                        # Show remaining users on demand
                        remaining = low_count - visible_count
                        if remaining > 0:
                            # Use persistent session state for show more
                            if 'show_more_low_responders' not in st.session_state:
                                st.session_state.show_more_low_responders = False

                            col_show, col_warning = st.columns([1, 2])
                            with col_show:
                                if st.button(f"Show {remaining} more low responders", key="show_more_low"):
                                    st.session_state.show_more_low_responders = True
                            with col_warning:
                                if remaining > 100:
                                    st.caption(
                                        "⚠️ Warning: Loading many users may cause browser slowdown")

                            if st.session_state.show_more_low_responders:
                                for user_info_item in followup_data_list['low_responders'][visible_count:]:
                                    display_enhanced_user_followup(
                                        user_info_item, analytics_data_dict, auto_analyze=False)

                                # Add a collapse button
                                if st.button("🔼 Hide additional low responders", key="hide_more_low"):
                                    st.session_state.show_more_low_responders = False
                                    st.rerun()
                    else:
                        st.info("No low responders ready for follow-up")
            else:
                st.success("🎉 No users currently need follow-up!")

        with tab2:
            st.subheader("Recent Interactions (Last 30 Days)")
            st.caption("Quick follow-up options for recently active users")

            # Get recent users with full data structure
            recent_users = get_recent_users_with_details(analytics_data_dict)

            if not recent_users:
                st.info("No recent interactions in the last 30 days")
                return

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Recent Users", len(recent_users))
            with col2:
                # Safely convert user_messages to int, defaulting to 0 if not valid
                total_user_messages = sum(int(user.get('user_messages', 0)) if isinstance(user.get('user_messages'), (int, str)) and str(user.get('user_messages', 0)).isdigit() else 0
                                          for user in recent_users)
                st.metric("Total User Messages", total_user_messages)
            with col3:
                # Safely convert total_messages to int, defaulting to 0 if not valid
                total_messages_sum = sum(int(user.get('total_messages', 0)) if isinstance(user.get('total_messages'), (int, str)) and str(user.get('total_messages', 0)).isdigit() else 0
                                         for user in recent_users)
                avg_messages = total_messages_sum / \
                    len(recent_users) if recent_users else 0
                st.metric("Avg Messages/User", f"{avg_messages:.1f}")

            # Search functionality
            search_term = st.text_input(
                "🔍 Search users:", placeholder="Type username to filter...")

            if search_term:
                filtered_users = [user for user in recent_users
                                  if search_term.lower() in user['ig_username'].lower()]
            else:
                filtered_users = recent_users[:10]  # Show first 10 by default

            if filtered_users:
                st.write(f"Showing {len(filtered_users)} users:")
                for user in filtered_users:
                    # Status emoji based on recency
                    if user['days_ago'] == 0:
                        status_emoji = "🟢"
                    elif user['days_ago'] <= 3:
                        status_emoji = "🟡"
                    elif user['days_ago'] <= 7:
                        status_emoji = "🟠"
                    else:
                        status_emoji = "🔴"

                    # User type
                    journey_stage = user.get(
                        'metrics', {}).get('journey_stage', {})
                    is_paying = journey_stage.get('is_paying_client', False) if isinstance(
                        journey_stage, dict) else False
                    trial_start = journey_stage.get('trial_start_date') if isinstance(
                        journey_stage, dict) else None

                    if is_paying:
                        user_type = "💰"
                    elif trial_start:
                        user_type = "🆓"
                    else:
                        user_type = "👤"

                    with st.expander(
                        f"{status_emoji} {user_type} **{user['ig_username']}** - {user['days_ago']} days ago | "
                        f"Messages: {user.get('user_messages', 0)} user, {user.get('ai_messages', 0)} AI",
                        expanded=False
                    ):
                        col_info, col_message = st.columns([1, 2])

                        with col_info:
                            st.write("**User Information:**")
                            st.write(
                                f"Last interaction: {user['last_interaction'].strftime('%Y-%m-%d %H:%M')}")
                            st.write(
                                f"Total messages: {user['total_messages']}")
                            st.write(f"Days since last: {user['days_ago']}")

                            # Show last few messages
                            if user.get('metrics', {}).get('conversation_history'):
                                st.write("**Recent messages:**")
                                for msg in user['metrics']['conversation_history'][-3:]:
                                    sender = "👤" if msg.get(
                                        'type') == 'user' else "🤖"
                                    text_preview = msg.get('text', '')[
                                        :80] + "..." if len(msg.get('text', '')) > 80 else msg.get('text', '')
                                    st.caption(f"{sender} {text_preview}")

                        with col_message:
                            st.write("**Follow-up Message:**")

                            # Check if user has a generated message stored in session state
                            message_key = f"recent_msg_{user['ig_username']}"
                            topic_key = f"recent_topic_{user['ig_username']}"

                            # Generate message button
                            col_gen, col_profile = st.columns([1, 1])
                            with col_gen:
                                if st.button("🤖 Generate Message", key=f"gen_recent_{user['ig_username']}", use_container_width=True):
                                    with st.spinner("Generating follow-up message..."):
                                        # Get user topics for context
                                        user_topics = get_user_topics(
                                            user['metrics'])
                                        current_topic = user_topics[0] if user_topics else "General catch-up"

                                        # Generate message using existing function with timing context
                                        generated_message = generate_follow_up_message(
                                            user['metrics'].get(
                                                'conversation_history', []),
                                            current_topic,
                                            # Pass days since last interaction
                                            user['days_ago']
                                        )

                                        if generated_message:
                                            st.session_state[message_key] = generated_message
                                            st.session_state[topic_key] = current_topic
                                            st.success("Message generated!")
                                            st.rerun()
                                        else:
                                            st.error(
                                                "Failed to generate message")

        with tab3:
            st.subheader("Bulk Follow-up Generation")
            st.caption("Generate messages for entire categories at once.")

            if followup_data_list['total_count'] > 0:
                high_count = len(followup_data_list['high_responders'])
                medium_count = len(followup_data_list['medium_responders'])
                low_count = len(followup_data_list['low_responders'])

                high_sub, medium_sub, low_sub = st.tabs([
                    f"🟢 High ({high_count})",
                    f"🟡 Medium ({medium_count})",
                    f"🟠 Low ({low_count})"
                ])

                with high_sub:
                    if st.button("Generate Follow-ups for all High Responders", key="tab3_gen_high"):
                        users_to_queue = [user['username']
                                          for user in followup_data_list['high_responders']]
                        if users_to_queue:
                            st.session_state.generation_queue = users_to_queue
                            st.session_state.generation_queue_total = len(
                                users_to_queue)
                            st.rerun()

                with medium_sub:
                    if st.button("Generate Follow-ups for all Medium Responders", key="tab3_gen_med"):
                        users_to_queue = [user['username']
                                          for user in followup_data_list['medium_responders']]
                        if users_to_queue:
                            st.session_state.generation_queue = users_to_queue
                            st.session_state.generation_queue_total = len(
                                users_to_queue)
                            st.rerun()

                with low_sub:
                    if st.button("Generate Follow-ups for all Low Responders", key="tab3_gen_low"):
                        users_to_queue = [user['username']
                                          for user in followup_data_list['low_responders']]
                        if users_to_queue:
                            st.session_state.generation_queue = users_to_queue
                            st.session_state.generation_queue_total = len(
                                users_to_queue)
                            st.rerun()
            else:
                st.info("No users are currently ready for a bulk follow-up.")
