import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os 
import sys
sys.path.insert(0, "/app/shared")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from models import (
    DispatchRequest, RegisterRunnerRequest, HeartbeatRequest,
    JobResultRequest, JobResponse, HealthResponse, AssignedJobResponse,
    JobStatus, RunnerStatus, CheckCategory
)
from database import Base, Job, Runner, init_db
from heartbeat import monitor_runners


DATABASE_URL = "sqlite:///./data/dataflow.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(engine)
    asyncio.create_task(monitor_runners(SessionLocal))
    yield


app = FastAPI(
    title="DataFlow CI Dispatcher",
    description="Distributes pipeline validation jobs to registered runners",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
def health():
    db = SessionLocal()
    try:
        active_runners = db.query(Runner).filter(
            Runner.status != RunnerStatus.DEAD
        ).count()
        pending_jobs = db.query(Job).filter(
            Job.status == JobStatus.PENDING
        ).count()
        return HealthResponse(
            status="ok",
            active_runners=active_runners,
            pending_jobs=pending_jobs
        )
    finally:
        db.close()


@app.post("/dispatch", status_code=202)
def dispatch_job(request: DispatchRequest, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        job = Job(
            job_id=str(uuid.uuid4()),
            commit_id=request.commit_id,
            repo_path=request.repo_path,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            committed_at=request.committed_at,
        )
        db.add(job)
        db.commit()
        background_tasks.add_task(assign_job, job.job_id)
        return {"job_id": job.job_id, "status": "queued"}
    finally:
        db.close()


@app.post("/runners/register")
def register_runner(request: RegisterRunnerRequest):
    db = SessionLocal()
    try:
        existing = db.query(Runner).filter(
            Runner.runner_id == request.runner_id
        ).first()
        if existing:
            existing.status = RunnerStatus.IDLE
            existing.last_heartbeat = datetime.now(timezone.utc)
        else:
            runner = Runner(
                runner_id=request.runner_id,
                status=RunnerStatus.IDLE,
                last_heartbeat=datetime.now(timezone.utc),
                registered_at=datetime.now(timezone.utc),
            )
            db.add(runner)
        db.commit()
        return {"registered": request.runner_id}
    finally:
        db.close()


@app.post("/runners/heartbeat")
def heartbeat(request: HeartbeatRequest):
    db = SessionLocal()
    try:
        runner = db.query(Runner).filter(
            Runner.runner_id == request.runner_id
        ).first()
        if not runner:
            raise HTTPException(status_code=404, detail="Runner not registered")
        runner.last_heartbeat = datetime.now(timezone.utc)
        db.commit()
        return {"acknowledged": True}
    finally:
        db.close()


@app.get("/runners/job/{runner_id}", response_model=Optional[AssignedJobResponse])
def get_assigned_job(runner_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(
            Job.assigned_runner == runner_id,
            Job.status == JobStatus.ASSIGNED
        ).first()
        if not job:
            return None
        return AssignedJobResponse(
            job_id=job.job_id,
            commit_id=job.commit_id,
            repo_path=job.repo_path,
            checks_to_run=[
                CheckCategory.STRUCTURAL,
                CheckCategory.STATISTICAL,
                CheckCategory.REFERENTIAL
            ]
        )
    finally:
        db.close()


@app.post("/jobs/result")
def submit_result(request: JobResultRequest):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == request.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job.status = request.status
        job.completed_at = datetime.now(timezone.utc)
        job.results = request.results
        job.duration_seconds = request.duration_seconds
        job.error_message = request.error_message

        runner = db.query(Runner).filter(
            Runner.runner_id == request.runner_id
        ).first()
        if runner:
            runner.status = RunnerStatus.IDLE
            runner.current_job = None

        db.commit()
        return {"received": True}
    finally:
        db.close()


@app.get("/jobs", response_model=list[JobResponse])
def list_jobs(limit: int = 50):
    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(
            Job.created_at.desc()
        ).limit(limit).all()
        return jobs
    finally:
        db.close()


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    finally:
        db.close()


def assign_job(job_id: str):
    db = SessionLocal()
    try:
        idle_runner = db.query(Runner).filter(
            Runner.status == RunnerStatus.IDLE
        ).first()
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return
        if not idle_runner:
            return
        job.status = JobStatus.ASSIGNED
        job.assigned_runner = idle_runner.runner_id
        idle_runner.status = RunnerStatus.BUSY
        idle_runner.current_job = job_id
        db.commit()
    finally:
        db.close()