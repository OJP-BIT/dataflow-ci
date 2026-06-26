from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, JSON, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase

import os 
import sys
sys.path.insert(0, "/app/shared")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from models import JobStatus, RunnerStatus


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    commit_id = Column(String, nullable=False)
    repo_path = Column(String, nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    assigned_runner = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    committed_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    results = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)


class Runner(Base):
    __tablename__ = "runners"

    runner_id = Column(String, primary_key=True)
    status = Column(SAEnum(RunnerStatus), default=RunnerStatus.IDLE, nullable=False)
    last_heartbeat = Column(DateTime, nullable=False)
    registered_at = Column(DateTime, nullable=False)
    current_job = Column(String, nullable=True)


def init_db(engine):
    Base.metadata.create_all(bind=engine)