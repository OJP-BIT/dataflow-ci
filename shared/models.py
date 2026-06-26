from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    REASSIGNED = "reassigned"


class CheckCategory(str, Enum):
    STRUCTURAL = "structural"
    STATISTICAL = "statistical"
    REFERENTIAL = "referential"


class RunnerStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    DEAD = "dead"


# --- Requests ---

class DispatchRequest(BaseModel):
    commit_id: str
    repo_path: str
    committed_at: datetime


class RegisterRunnerRequest(BaseModel):
    runner_id: str


class HeartbeatRequest(BaseModel):
    runner_id: str
    job_id: Optional[str] = None


class JobResultRequest(BaseModel):
    job_id: str
    runner_id: str
    status: JobStatus
    results: list[dict]
    duration_seconds: float
    error_message: Optional[str] = None


# --- Responses ---

class JobResponse(BaseModel):
    job_id: str
    commit_id: str
    status: JobStatus
    assigned_runner: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    results: Optional[list[dict]]

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    active_runners: int
    pending_jobs: int


class AssignedJobResponse(BaseModel):
    job_id: str
    commit_id: str
    repo_path: str
    checks_to_run: list[CheckCategory]