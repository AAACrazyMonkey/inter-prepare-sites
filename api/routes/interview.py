"""API routes for Interview Coach."""

import asyncio
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import InterviewSession, Job, User
from db.session import get_db
from prep.interview_coach import (
    generate_coding_questions,
    generate_final_report,
    score_answer,
)


router = APIRouter(prefix="/interview", tags=["Interview Coach"])


class StartInterviewRequest(BaseModel):
    """Request to start an interview session."""

    user_id: int = 1
    jd_text: Optional[str] = Field(default=None)
    job_id: Optional[int] = Field(default=None)
    num_questions: int = Field(default=4, ge=3, le=5)


class StartInterviewResponse(BaseModel):
    """Response after creating an interview session."""

    session_id: int
    user_id: int
    job_id: int
    questions: list[dict]


class AnswerInterviewRequest(BaseModel):
    """Request to answer one interview question."""

    session_id: int
    question_index: int = Field(ge=0)
    answer: str


async def _ensure_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user:
        return user

    user = User(
        id=user_id,
        email=f"user{user_id}@placeholder.com",
        hashed_password="placeholder",
    )
    db.add(user)
    await db.flush()
    return user


async def _get_or_create_manual_job(db: AsyncSession, jd_text: str) -> Job:
    dedup_hash = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()
    result = await db.execute(select(Job).where(Job.dedup_hash == dedup_hash))
    job = result.scalar_one_or_none()
    if job:
        return job

    job = Job(
        company="Manual JD",
        title="Pasted job description",
        location=None,
        jd_text=jd_text,
        keywords={},
        source_url=None,
        dedup_hash=dedup_hash,
    )
    db.add(job)
    await db.flush()
    return job


def _format_feedback(score: dict) -> str:
    scores = score.get("scores", {})
    feedback = score.get("feedback", {})
    return f"""## Scoring feedback

**Clarity:** {scores.get("clarity", "-")}/5
{feedback.get("clarity", "")}

**Correctness:** {scores.get("correctness", "-")}/5
{feedback.get("correctness", "")}

**Depth:** {scores.get("depth", "-")}/5
{feedback.get("depth", "")}

**Communication:** {scores.get("communication", "-")}/5
{feedback.get("communication", "")}

**Overall:** {score.get("overall_feedback", "")}

**Next improvement:** {score.get("suggested_improvement", "")}
"""


@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """List active jobs for the interview JD dropdown."""
    result = await db.execute(
        select(Job)
        .where(Job.is_active == True)  # noqa: E712
        .order_by(Job.scraped_at.desc())
        .limit(100)
    )
    jobs = result.scalars().all()
    return {
        "jobs": [
            {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "jd_text": job.jd_text,
            }
            for job in jobs
        ]
    }


@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(
    req: StartInterviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start an interview by generating coding questions from a JD."""
    await _ensure_user(db, req.user_id)

    job = None
    jd_text = (req.jd_text or "").strip()
    if req.job_id:
        job = await db.get(Job, req.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        jd_text = job.jd_text or jd_text

    if not jd_text:
        raise HTTPException(status_code=400, detail="Provide jd_text or a job_id with jd_text.")

    if not job:
        job = await _get_or_create_manual_job(db, jd_text)

    questions = await generate_coding_questions(jd_text, req.num_questions)
    if not questions:
        raise HTTPException(status_code=502, detail="Could not generate interview questions.")

    session = InterviewSession(
        user_id=req.user_id,
        job_id=job.id,
        questions=questions,
        answers=[],
        scores=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return StartInterviewResponse(
        session_id=session.id,
        user_id=session.user_id,
        job_id=session.job_id,
        questions=session.questions or [],
    )


@router.post("/answer")
async def answer_question(
    req: AnswerInterviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Score one answer and stream feedback to the caller."""
    session = await db.get(InterviewSession, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    questions = session.questions or []
    if req.question_index >= len(questions):
        raise HTTPException(status_code=400, detail="question_index is out of range.")

    job = await db.get(Job, session.job_id)
    score = await score_answer(questions[req.question_index], req.answer, job.jd_text if job else "")

    answers = list(session.answers or [])
    scores = list(session.scores or [])
    answer_record = {
        "question_index": req.question_index,
        "answer": req.answer,
    }
    score_record = {
        "question_index": req.question_index,
        **score,
    }

    existing_answer = next((i for i, item in enumerate(answers) if item.get("question_index") == req.question_index), None)
    if existing_answer is None:
        answers.append(answer_record)
    else:
        answers[existing_answer] = answer_record

    existing_score = next((i for i, item in enumerate(scores) if item.get("question_index") == req.question_index), None)
    if existing_score is None:
        scores.append(score_record)
    else:
        scores[existing_score] = score_record

    session.answers = answers
    session.scores = scores
    await db.commit()

    feedback_text = _format_feedback(score)

    async def event_stream():
        for chunk in feedback_text.split("\n\n"):
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.02)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/session/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a full interview session record."""
    session = await db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    job = await db.get(Job, session.job_id)
    return {
        "id": session.id,
        "user_id": session.user_id,
        "job_id": session.job_id,
        "job": {
            "company": job.company,
            "title": job.title,
            "jd_text": job.jd_text,
        } if job else None,
        "questions": session.questions or [],
        "answers": session.answers or [],
        "scores": session.scores or [],
        "created_at": str(session.created_at),
    }


@router.get("/history/{user_id}")
async def get_history(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all interview sessions for a user."""
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.created_at.desc())
    )
    sessions = result.scalars().all()

    history = []
    for session in sessions:
        job = await db.get(Job, session.job_id)
        history.append({
            "id": session.id,
            "job_id": session.job_id,
            "job_title": job.title if job else None,
            "company": job.company if job else None,
            "question_count": len(session.questions or []),
            "answered_count": len(session.answers or []),
            "created_at": str(session.created_at),
            "has_report": bool((session.scores or []) and isinstance((session.scores or [])[-1], dict) and (session.scores or [])[-1].get("final_report")),
        })

    return {"user_id": user_id, "sessions": history}


@router.post("/finish/{session_id}")
async def finish_interview(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Finish an interview and generate the final report."""
    session = await db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    job = await db.get(Job, session.job_id)
    questions = session.questions or []
    answers = session.answers or []
    scores = session.scores or []

    report = await generate_final_report(
        questions=questions,
        answers=answers,
        scores=scores,
        jd_text=job.jd_text if job else "",
    )

    session.scores = scores + [{"final_report": report}]
    await db.commit()

    return {
        "session_id": session.id,
        "report": report,
    }
