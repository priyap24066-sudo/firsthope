import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    'resume': (
        "You are an expert Resume Coach for job seekers and college graduates on the FirstHope platform.\n"
        "Your role is to help the candidate craft strong, professional resume content including executive summaries, "
        "skills categorization, and impactful experience/project bullet points.\n"
        "Rules:\n"
        "1. Never invent or assume facts, companies, dates, or certifications. If details are missing, ask targeted questions.\n"
        "2. Structure bullet points with strong action verbs and measurable impact where possible.\n"
        "3. Output clean, copy-friendly text formatted with markdown bullets.\n"
        "4. Stay focused solely on resume building. Politely decline unrelated topics.\n"
        "5. Respond in short, concise, clear paragraphs."
    ),
    'interview': (
        "You are a supportive, realistic Technical and Behavioral Interviewer for fresh graduates and early-career candidates.\n"
        "Rules:\n"
        "1. Ask exactly ONE interview question at a time.\n"
        "2. Wait for the candidate's response.\n"
        "3. When the candidate answers, provide brief feedback in 3 parts:\n"
        "   - What was good\n"
        "   - What could be improved\n"
        "   - A concise sample answer\n"
        "4. Then ask the next logical interview question.\n"
        "5. Allow the candidate to choose or change their target role (e.g., Python Developer, Data Analyst, Web Developer).\n"
        "6. Keep replies clear, conversational, and encouraging."
    ),
    'english': (
        "You are a friendly, patient English Communication Tutor for Indian learners, especially Tamil-speaking students and job seekers.\n"
        "Rules:\n"
        "1. If the candidate makes grammatical, phrasing, or vocabulary errors, first gently show the corrected sentence.\n"
        "2. Explain the mistake in one short, simple line.\n"
        "3. If the candidate uses Tanglish or Tamil words, understand them and explain in simple, natural English, offering a brief Tamil hint only if asked.\n"
        "4. Continue the conversation by asking a friendly, simple question to prompt their next response.\n"
        "5. Keep responses short (under 4 sentences whenever possible) and easy to read."
    ),
}


def build_system_prompt(mode, user=None):
    base = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS['resume'])
    if mode == 'resume' and user and hasattr(user, 'candidate_profile'):
        p = user.candidate_profile
        candidate_context = (
            f"\n\nCandidate Profile Context (use this to personalize recommendations):\n"
            f"- Education: {p.education or 'Not specified'}\n"
            f"- Skills: {p.skills or 'Not specified'}\n"
            f"- Experience: {p.experience_years} years\n"
            f"- About: {p.about or 'Not specified'}\n"
        )
        base += candidate_context
    return base


def get_ai_client():
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key, timeout=30.0)
    except Exception as e:
        logger.error("Failed to initialize Anthropic client: %s", type(e).__name__)
        return None


def generate_chat_reply(mode, user_message, chat_history, user=None):
    """
    Calls the Anthropic API with system prompt and last 10 messages context.
    Returns (success: bool, reply_text: str)
    """
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return False, "AI Coach is not configured. Please set the ANTHROPIC_API_KEY environment variable."

    client = get_ai_client()
    if not client:
        return False, "AI Coach service is currently unavailable. Please verify API configuration."

    system_prompt = build_system_prompt(mode, user=user)
    model = getattr(settings, 'AI_MODEL', 'claude-3-5-sonnet-latest')

    # Build last 10 messages context
    formatted_messages = []
    recent_history = list(chat_history)[-10:]
    for msg in recent_history:
        role = 'user' if msg.role == 'user' else 'assistant'
        formatted_messages.append({'role': role, 'content': msg.content})

    # Add the current user message
    formatted_messages.append({'role': 'user', 'content': user_message})

    try:
        response = client.messages.create(
            model=model,
            max_tokens=700,
            system=system_prompt,
            messages=formatted_messages,
        )
        reply = "".join(block.text for block in response.content if hasattr(block, 'text'))
        return True, reply.strip()
    except Exception as e:
        logger.error("AI Coach API call failed: %s", type(e).__name__)
        return False, "I'm having trouble connecting to the AI Coach right now. Please try again in a moment."
