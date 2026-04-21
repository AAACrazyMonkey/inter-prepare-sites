"""Plan Generator - generates and adjusts personalized study plans."""

import json
from prep.llm_client import chat_completion
from prep.llm_client import chat_completion, chat_completion_stream


SYSTEM_PROMPT = """You are an expert internship preparation coach for CS graduate students 
targeting Silicon Valley SWE/ML internships. You help students create personalized study plans.

Your expertise includes:
- LeetCode problem patterns and optimal study order
- System design interview preparation
- Behavioral interview preparation
- ML/AI interview topics (for ML roles)
- US tech recruiting timelines and what companies look for

You are encouraging but realistic. You give actionable, specific advice."""


async def analyze_assessment(assessment: dict) -> dict:
    """Analyze user's initial assessment and generate follow-up questions."""

    prompt = f"""A user just completed their initial assessment for internship preparation.
Here are their answers:

{json.dumps(assessment, indent=2)}

Based on this information:
1. Write a brief summary of their current situation (2-3 sentences).
2. Generate 3-5 follow-up questions to better understand their preparation needs.
   Focus on gaps in the assessment - things you need to know to create an effective plan.
   For example: specific topics they've studied, past project experience, 
   interview experience, preferred learning style, etc.

Respond in JSON format:
{{
    "summary": "...",
    "follow_up_questions": ["...", "...", "..."]
}}

Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    # Parse JSON from response (strip markdown fences if present)
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


async def follow_up_conversation(
    assessment: dict,
    conversation_history: list[dict],
    user_message: str,
) -> dict:
    """Continue the follow-up conversation to gather more info."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here is the user's initial assessment:\n{json.dumps(assessment, indent=2)}",
        },
        {"role": "assistant", "content": "I've reviewed the assessment. Let me ask some follow-up questions."},
    ]

    # Add conversation history
    for msg in conversation_history:
        messages.append(msg)

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Ask LLM to respond and judge if assessment is complete
    messages.append({
        "role": "user",
        "content": """Based on the conversation so far, respond to the user naturally.
Then determine: do you have enough information to generate a comprehensive study plan?

Respond in JSON format:
{
    "reply": "Your natural response to the user...",
    "is_assessment_complete": true/false,
    "ready_to_generate_plan": true/false
}

Set ready_to_generate_plan to true only when you have a clear picture of:
- Their technical level (with specifics)
- Their timeline and available hours
- Their target roles and companies
- Their strengths and weaknesses

Respond ONLY with the JSON, no other text."""
    })

    response = await chat_completion(messages=messages, temperature=0.7)

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


async def generate_plan(assessment: dict, conversation_context: str) -> dict:
    """Generate a complete study plan based on assessment and conversation."""

    prompt = f"""Based on the following user assessment and conversation, generate a detailed 
weekly study plan for internship preparation.

Assessment:
{json.dumps(assessment, indent=2)}

Additional context from conversation:
{conversation_context}

Create a week-by-week plan. For each week, include:
- A theme (e.g., "Arrays & Hashing Fundamentals")
- Specific topics with subtopics
- Suggested LeetCode problems (by name or number)
- Estimated hours per topic
- Priority level (high/medium/low)
- A weekly goal

Also include:
- A suggested daily routine
- General notes and tips

Respond in JSON format:
{{
    "target_role": "swe/ml/ds",
    "total_weeks": <number>,
    "weeks": [
        {{
            "week_number": 1,
            "theme": "...",
            "topics": [
                {{
                    "topic": "Arrays & Hashing",
                    "subtopics": ["Two pointers", "Sliding window"],
                    "suggested_problems": ["Two Sum", "Best Time to Buy and Sell Stock"],
                    "estimated_hours": 5.0,
                    "priority": "high"
                }}
            ],
            "weekly_goal": "..."
        }}
    ],
    "daily_routine_suggestion": "...",
    "notes": "..."
}}

Make the plan realistic based on the user's available time.
Order topics from fundamental to advanced.
Prioritize weak areas but include review of strong areas too.

Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=8192,
    )

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


async def adjust_plan(
    current_plan: dict,
    progress_logs: list[dict],
    reason: str,
) -> dict:
    """Adjust an existing plan based on user progress and feedback."""

    prompt = f"""The user wants to adjust their study plan.

Current plan:
{json.dumps(current_plan, indent=2)}

Their recent progress logs:
{json.dumps(progress_logs, indent=2)}

Reason for adjustment: {reason if reason else "User wants a general re-evaluation"}

Based on their progress:
- Identify topics they've mastered (high correct rate, high confidence)
- Identify topics they're struggling with (low correct rate, mentioned as difficult)
- Consider their actual study pace vs planned pace

Generate an adjusted plan. Deprioritize mastered topics, escalate weak areas,
and adjust the timeline if they're ahead or behind schedule.

Respond in the same JSON format as the original plan, with these additions:
{{
    "changes_summary": ["list of key changes made"],
    ...rest of plan fields...
}}

Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=8192,
    )

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


async def generate_checkin_feedback(
    checkin_data: dict,
    current_plan: dict,
    recent_logs: list[dict],
) -> dict:
    """Generate encouraging feedback after a daily check-in."""

    prompt = f"""The user just completed their daily check-in.

Today's check-in:
{json.dumps(checkin_data, indent=2)}

Their current study plan theme: {current_plan.get("current_week_theme", "N/A")}

Recent progress (last 7 days):
{json.dumps(recent_logs[-7:] if recent_logs else [], indent=2)}

Generate a brief, encouraging response. Include:
1. A summary of today's progress
2. An encouraging message (be specific, not generic)
3. If they mentioned difficulties, give a brief tip

Respond in JSON format:
{{
    "summary": "...",
    "encouragement": "..."
}}

Keep it concise - 2-3 sentences each. 
Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
    )

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)

async def follow_up_conversation_stream(
    assessment: dict,
    conversation_history: list[dict],
    user_message: str,
):
    """Stream the follow-up conversation response token by token."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here is the user's initial assessment:\n{json.dumps(assessment, indent=2)}",
        },
        {"role": "assistant", "content": "I've reviewed the assessment. Let me ask some follow-up questions."},
    ]

    for msg in conversation_history:
        messages.append(msg)

    messages.append({"role": "user", "content": user_message})

    async for token in chat_completion_stream(messages=messages, temperature=0.7):
        yield token