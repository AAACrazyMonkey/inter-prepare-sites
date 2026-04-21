"""Database models for Intern Prep Agent."""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Boolean, Float, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    cv_base = Column(JSON, nullable=True)  # User's base CV as structured JSON
    target_roles = Column(JSON, nullable=True)  # e.g. ["swe", "ml"]
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    cvs = relationship("CV", back_populates="user")
    prep_plans = relationship("PrepPlan", back_populates="user")
    progress_logs = relationship("ProgressLog", back_populates="user")
    interview_sessions = relationship("InterviewSession", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    jd_text = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)  # {"required": [...], "preferred": [...]}
    source_url = Column(String(1024), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    dedup_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Relationships
    cvs = relationship("CV", back_populates="job")
    prep_plans = relationship("PrepPlan", back_populates="job")
    interview_sessions = relationship("InterviewSession", back_populates="job")


class CV(Base):
    __tablename__ = "cvs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    #job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    tailored_content = Column(Text, nullable=True)  # HTML content
    pdf_path = Column(String(512), nullable=True)
    variant = Column(String(10), nullable=False, default="swe")  # "swe" or "ml"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cvs")
    job = relationship("Job", back_populates="cvs")


class PrepPlan(Base):
    __tablename__ = "prep_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    plan_data = Column(JSON, nullable=True)  # State machine data
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="prep_plans")
    job = relationship("Job", back_populates="prep_plans")


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, default=date.today)
    topics = Column(JSON, nullable=True)  # ["arrays", "dp", "graphs"]
    lc_solved = Column(Integer, default=0)
    lc_correct = Column(Integer, default=0)
    hours_studied = Column(Float, default=0.0)

    # Relationships
    user = relationship("User", back_populates="progress_logs")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    questions = Column(JSON, nullable=True)
    answers = Column(JSON, nullable=True)
    scores = Column(JSON, nullable=True)  # {"clarity": 4, "correctness": 3, ...}
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="interview_sessions")
    job = relationship("Job", back_populates="interview_sessions")
