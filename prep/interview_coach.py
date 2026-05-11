"""Interview Coach - generates coding interviews and evaluates answers."""

import json

from prep.llm_client import chat_completion


SYSTEM_PROMPT = """You are an expert technical interviewer for CS internship candidates.
You create realistic coding interview questions from job descriptions and evaluate answers
with precise, constructive feedback.

You focus on:
- Algorithmic problem solving and tradeoffs
- Data structures and coding patterns relevant to the role
- Communication quality and interview clarity
- Practical depth expected from a strong internship candidate

Be fair, specific, and actionable. Do not be harsh for its own sake."""


def _parse_json_response(response: str) -> dict:
    """Parse JSON, allowing the model to accidentally wrap it in markdown fences."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


async def generate_coding_questions(jd_text: str, num_questions: int = 4) -> list[dict]:
    """Generate 3-5 coding questions based on a job description."""
    count = min(5, max(3, num_questions))
    prompt = f"""Generate {count} coding interview questions tailored to this internship job description.

Job description:
{jd_text}

Each question should be suitable for a 25-40 minute technical interview answer.
Mix fundamentals with role-relevant topics. Avoid requiring obscure libraries.

Respond in JSON format:
{{
  "questions": [
    {{
      "title": "...",
      "description": "...",
      "difficulty": "easy|medium|hard",
      "focus_points": ["...", "..."],
      "expected_approach": "Brief private rubric of what a strong answer should cover"
    }}
  ]
}}

Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=4096,
    )
    data = _parse_json_response(response)
    return data.get("questions", [])[:count]


async def score_answer(question: dict, answer: str, jd_text: str = "") -> dict:
    """Score a single answer across four interview dimensions."""
    prompt = f"""Evaluate the candidate's answer to this coding interview question.

Job description context:
{jd_text if jd_text else "N/A"}

Question:
{json.dumps(question, indent=2)}

Candidate answer:
{answer}

Score each dimension from 1 to 5:
- Clarity: how understandable and organized the answer is
- Correctness: whether the algorithm/solution is valid
- Depth: tradeoffs, complexity analysis, edge cases, and alternatives
- Communication: interview-style explanation and collaboration

Respond in JSON format:
{{
  "scores": {{
    "clarity": 1,
    "correctness": 1,
    "depth": 1,
    "communication": 1
  }},
  "feedback": {{
    "clarity": "...",
    "correctness": "...",
    "depth": "...",
    "communication": "..."
  }},
  "overall_feedback": "...",
  "suggested_improvement": "..."
}}

Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=4096,
    )
    return _parse_json_response(response)


async def generate_final_report(
    questions: list[dict],
    answers: list[dict],
    scores: list[dict],
    jd_text: str = "",
) -> dict:
    """Generate a final summary report for an interview session."""
    prompt = f"""Generate a final interview report for this coding interview session.

Job description context:
{jd_text if jd_text else "N/A"}

Questions:
{json.dumps(questions, indent=2)}

Answers:
{json.dumps(answers, indent=2)}

Per-question scores and feedback:
{json.dumps(scores, indent=2)}

Include:
1. Overall performance
2. Strengths
3. Weak areas
4. Specific next-step advice
5. A concise readiness assessment

Respond in JSON format:
{{
  "overall_performance": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "recommendations": ["...", "..."],
  "readiness": "...",
  "average_scores": {{
    "clarity": 0.0,
    "correctness": 0.0,
    "depth": 0.0,
    "communication": 0.0
  }}
}}

Respond ONLY with the JSON, no other text."""

    response = await chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=4096,
    )
    return _parse_json_response(response)
