"""API routes for Plan Generator."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import StreamingResponse
from prep.plan_generator import follow_up_conversation_stream

from db.session import get_db
from db.models import User, PrepPlan, ProgressLog
from api.schemas.plan import (
    AssessmentRequest,
    AssessmentResponse,
    FollowUpMessage,
    FollowUpResponse,
    CheckInRequest,
    CheckInResponse,
    AdjustPlanRequest,
    AdjustPlanResponse,
    StudyPlan,
)
from prep.plan_generator import (
    analyze_assessment,
    follow_up_conversation,
    generate_plan,
    adjust_plan,
    generate_checkin_feedback,
)

router = APIRouter(prefix="/plan", tags=["Plan Generator"])

# In-memory conversation storage (replace with DB/Redis in production)
_conversations: dict[int, dict] = {}


@router.post("/assess", response_model=AssessmentResponse)
async def submit_assessment(
    req: AssessmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Step 1: User submits initial assessment questionnaire."""

    # For now, use user_id=1 (add auth later)
    user_id = 1

    assessment_data = req.model_dump()

    # Call LLM to analyze assessment
    result = await analyze_assessment(assessment_data)

    # Store assessment in conversation memory
    _conversations[user_id] = {
        "assessment": assessment_data,
        "history": [],
        "assessment_complete": False,
    }

    return AssessmentResponse(
        user_id=user_id,
        assessment_summary=result["summary"],
        follow_up_questions=result["follow_up_questions"],
    )


@router.post("/follow-up", response_model=FollowUpResponse)
async def follow_up(
    req: FollowUpMessage,
    db: AsyncSession = Depends(get_db),
):
    """Step 2: Continue follow-up conversation to gather more info."""

    conv = _conversations.get(req.user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="No assessment found. Please submit assessment first via /plan/assess",
        )

    # Add user message to history
    conv["history"].append({"role": "user", "content": req.message})

    # Get LLM response
    result = await follow_up_conversation(
        assessment=conv["assessment"],
        conversation_history=conv["history"],
        user_message=req.message,
    )

    # Add assistant reply to history
    conv["history"].append({"role": "assistant", "content": result["reply"]})
    conv["assessment_complete"] = result["is_assessment_complete"]

    return FollowUpResponse(
        reply=result["reply"],
        is_assessment_complete=result["is_assessment_complete"],
        ready_to_generate_plan=result["ready_to_generate_plan"],
    )


@router.post("/generate", response_model=StudyPlan)
async def generate_study_plan(
    user_id: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Step 3: Generate the study plan based on assessment + conversation."""

    conv = _conversations.get(user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="No assessment found. Please submit assessment first.",
        )

    # Build conversation context string
    context_parts = []
    for msg in conv["history"]:
        role = "User" if msg["role"] == "user" else "Coach"
        context_parts.append(f"{role}: {msg['content']}")
    conversation_context = "\n".join(context_parts)

    # Ensure user exists
    from db.models import User
    existing_user = await db.get(User, user_id)
    if not existing_user:
        new_user = User(
            id=user_id,
            email=f"user{user_id}@placeholder.com",
            hashed_password="placeholder",
        )
        db.add(new_user)
        await db.flush()


    # Generate plan via LLM
    plan_data = await generate_plan(
        assessment=conv["assessment"],
        conversation_context=conversation_context,
    )

    # Save to database
    prep_plan = PrepPlan(
        user_id=user_id,
        #job_id=0,  # 0 = general prep, not tied to specific job
        job_id=None,
        plan_data={
            "assessment": conv["assessment"],
            "plan": plan_data,
            "conversation_context": conversation_context,
        },
    )
    db.add(prep_plan)
    await db.commit()
    await db.refresh(prep_plan)

    return StudyPlan(
        user_id=user_id,
        target_role=plan_data.get("target_role", conv["assessment"]["target_role"]),
        total_weeks=plan_data.get("total_weeks", len(plan_data.get("weeks", []))),
        weeks=plan_data.get("weeks", []),
        daily_routine_suggestion=plan_data.get("daily_routine_suggestion", ""),
        notes=plan_data.get("notes", ""),
    )


@router.post("/checkin", response_model=CheckInResponse)
async def daily_checkin(
    req: CheckInRequest,
    db: AsyncSession = Depends(get_db),
):
    """Step 4: User submits daily progress check-in."""

    # Save progress log to database
    log = ProgressLog(
        user_id=req.user_id,
        date=req.date,
        topics=req.topics_studied,
        lc_solved=req.leetcode_solved,
        lc_correct=req.leetcode_correct,
        hours_studied=req.hours_studied,
    )
    db.add(log)
    await db.commit()

    # Get recent logs for context
    week_ago = req.date - timedelta(days=7)
    result = await db.execute(
        select(ProgressLog)
        .where(
            and_(
                ProgressLog.user_id == req.user_id,
                ProgressLog.date >= week_ago,
            )
        )
        .order_by(ProgressLog.date)
    )
    recent_logs = result.scalars().all()

    # Get current plan
    plan_result = await db.execute(
        select(PrepPlan)
        .where(PrepPlan.user_id == req.user_id)
        .order_by(PrepPlan.updated_at.desc())
        .limit(1)
    )
    current_plan = plan_result.scalar_one_or_none()

    # Format logs for LLM
    logs_data = [
        {
            "date": str(l.date),
            "topics": l.topics,
            "lc_solved": l.lc_solved,
            "lc_correct": l.lc_correct,
            "hours": l.hours_studied,
        }
        for l in recent_logs
    ]

    checkin_data = {
        "date": str(req.date),
        "topics_studied": req.topics_studied,
        "leetcode_solved": req.leetcode_solved,
        "leetcode_correct": req.leetcode_correct,
        "hours_studied": req.hours_studied,
        "difficulty_notes": req.difficulty_notes,
        "confidence_rating": req.confidence_rating,
    }

    plan_context = {}
    if current_plan and current_plan.plan_data:
        plan_context = current_plan.plan_data.get("plan", {})

    # Generate feedback
    feedback = await generate_checkin_feedback(
        checkin_data=checkin_data,
        current_plan=plan_context,
        recent_logs=logs_data,
    )

    # Calculate streak
    all_logs_result = await db.execute(
        select(ProgressLog)
        .where(ProgressLog.user_id == req.user_id)
        .order_by(ProgressLog.date.desc())
    )
    all_logs = all_logs_result.scalars().all()

    streak = 0
    check_date = req.date
    log_dates = {l.date for l in all_logs}
    while check_date in log_dates:
        streak += 1
        check_date -= timedelta(days=1)

    total_solved = sum(l.lc_solved for l in all_logs)

    return CheckInResponse(
        summary=feedback.get("summary", "Progress recorded."),
        encouragement=feedback.get("encouragement", "Keep going!"),
        streak_days=streak,
        total_problems_solved=total_solved,
    )


@router.post("/adjust")
async def adjust_study_plan(
    req: AdjustPlanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Step 5: User manually triggers plan adjustment."""

    # Get current plan
    plan_result = await db.execute(
        select(PrepPlan)
        .where(PrepPlan.user_id == req.user_id)
        .order_by(PrepPlan.updated_at.desc())
        .limit(1)
    )
    current_plan = plan_result.scalar_one_or_none()

    if not current_plan:
        raise HTTPException(
            status_code=404,
            detail="No existing plan found. Please generate a plan first.",
        )

    # Get all progress logs
    logs_result = await db.execute(
        select(ProgressLog)
        .where(ProgressLog.user_id == req.user_id)
        .order_by(ProgressLog.date)
    )
    all_logs = logs_result.scalars().all()

    logs_data = [
        {
            "date": str(l.date),
            "topics": l.topics,
            "lc_solved": l.lc_solved,
            "lc_correct": l.lc_correct,
            "hours": l.hours_studied,
        }
        for l in all_logs
    ]

    # Adjust plan via LLM
    plan_data = current_plan.plan_data.get("plan", {})
    adjusted = await adjust_plan(
        current_plan=plan_data,
        progress_logs=logs_data,
        reason=req.reason,
    )

    # Save new plan
    changes = adjusted.pop("changes_summary", ["Plan adjusted based on progress"])

    new_plan = PrepPlan(
        user_id=req.user_id,
        job_id=0,
        plan_data={
            "assessment": current_plan.plan_data.get("assessment", {}),
            "plan": adjusted,
            "adjusted_from": current_plan.id,
            "adjustment_reason": req.reason,
        },
    )
    db.add(new_plan)
    await db.commit()

    return {
        "old_plan_id": current_plan.id,
        "new_plan_id": new_plan.id,
        "changes_made": changes,
        "new_plan": adjusted,
    }


@router.get("/current/{user_id}")
async def get_current_plan(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the user's current active study plan."""

    result = await db.execute(
        select(PrepPlan)
        .where(PrepPlan.user_id == user_id)
        .order_by(PrepPlan.updated_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this user.")

    return {
        "plan_id": plan.id,
        "plan": plan.plan_data.get("plan", {}),
        "updated_at": str(plan.updated_at),
    }


@router.get("/progress/{user_id}")
async def get_progress(
    user_id: int,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Get user's recent progress logs."""

    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(ProgressLog)
        .where(
            and_(
                ProgressLog.user_id == user_id,
                ProgressLog.date >= since,
            )
        )
        .order_by(ProgressLog.date)
    )
    logs = result.scalars().all()

    return {
        "user_id": user_id,
        "period_days": days,
        "logs": [
            {
                "date": str(l.date),
                "topics": l.topics,
                "lc_solved": l.lc_solved,
                "lc_correct": l.lc_correct,
                "hours_studied": l.hours_studied,
            }
            for l in logs
        ],
        "total_problems": sum(l.lc_solved for l in logs),
        "total_hours": sum(l.hours_studied for l in logs),
    }

@router.post("/follow-up/stream")
async def follow_up_stream(
    req: FollowUpMessage,
    db: AsyncSession = Depends(get_db),
):
    """Stream follow-up conversation response via SSE."""

    conv = _conversations.get(req.user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="No assessment found. Please submit assessment first.",
        )

    conv["history"].append({"role": "user", "content": req.message})

    async def event_generator():
        full_reply = ""
        async for token in follow_up_conversation_stream(
            assessment=conv["assessment"],
            conversation_history=conv["history"],
            user_message=req.message,
        ):
            full_reply += token
            yield f"data: {token}\n\n"

        conv["history"].append({"role": "assistant", "content": full_reply})
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
