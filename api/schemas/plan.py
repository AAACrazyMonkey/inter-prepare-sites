"""Pydantic schemas for Plan Generator module."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


# ── Step 1: Initial Assessment Questionnaire ──

class AssessmentRequest(BaseModel):
    """User's initial assessment questionnaire answers."""
    target_role: str = Field(
        description="Target role type",
        examples=["swe", "ml", "ds", "all"]
    )
    coding_level: str = Field(
        description="Current coding/algorithm proficiency",
        examples=["beginner", "intermediate", "advanced"]
    )
    timeline: str = Field(
        description="When user plans to start applying",
        examples=["1_month", "2_3_months", "6_months"]
    )
    leetcode_count: int = Field(
        default=0,
        description="Number of LeetCode problems solved so far"
    )
    familiar_topics: list[str] = Field(
        default=[],
        description="Topics user is already comfortable with",
        examples=[["arrays", "strings", "hash_tables"]]
    )
    weak_topics: list[str] = Field(
        default=[],
        description="Topics user struggles with",
        examples=[["dp", "graphs", "system_design"]]
    )
    hours_per_day: float = Field(
        default=2.0,
        description="Hours available for study per day"
    )
    target_companies: list[str] = Field(
        default=[],
        description="Specific companies user is targeting",
        examples=[["google", "meta", "amazon"]]
    )


class AssessmentResponse(BaseModel):
    """Response after initial assessment."""
    user_id: int
    assessment_summary: str
    follow_up_questions: list[str]


# ── Step 2: Follow-up Conversation ──

class FollowUpMessage(BaseModel):
    """A message in the follow-up conversation."""
    user_id: int
    message: str


class FollowUpResponse(BaseModel):
    """LLM's follow-up response."""
    reply: str
    is_assessment_complete: bool
    ready_to_generate_plan: bool


# ── Step 3: Generated Study Plan ──

class WeeklyTopic(BaseModel):
    """A single topic within a weekly plan."""
    topic: str
    subtopics: list[str]
    suggested_problems: list[str]
    estimated_hours: float
    priority: str = Field(description="high / medium / low")


class WeekPlan(BaseModel):
    """One week's study plan."""
    week_number: int
    theme: str
    topics: list[WeeklyTopic]
    weekly_goal: str


class StudyPlan(BaseModel):
    """Complete generated study plan."""
    user_id: int
    target_role: str
    total_weeks: int
    weeks: list[WeekPlan]
    daily_routine_suggestion: str
    notes: str


# ── Step 4: Daily Check-in ──

class CheckInRequest(BaseModel):
    """User's daily progress check-in."""
    user_id: int
    date: date
    topics_studied: list[str] = Field(default=[])
    leetcode_solved: int = Field(default=0)
    leetcode_correct: int = Field(default=0)
    hours_studied: float = Field(default=0.0)
    difficulty_notes: str = Field(
        default="",
        description="What the user found difficult today"
    )
    confidence_rating: int = Field(
        default=3,
        description="Self-rated confidence 1-5"
    )


class CheckInResponse(BaseModel):
    """Response after check-in."""
    summary: str
    encouragement: str
    streak_days: int
    total_problems_solved: int


# ── Step 5: Plan Adjustment ──

class AdjustPlanRequest(BaseModel):
    """Request to adjust the study plan."""
    user_id: int
    reason: str = Field(
        default="",
        description="Why user wants to adjust the plan"
    )


class AdjustPlanResponse(BaseModel):
    """Response after plan adjustment."""
    old_plan_summary: str
    changes_made: list[str]
    new_plan: StudyPlan
