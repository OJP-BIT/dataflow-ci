import asyncio
import logging
from datetime import datetime, timezone, timedelta

from database import Job, Runner
from models import RunnerStatus, JobStatus
import sys
import os
sys.path.insert(0, "/app/shared")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

logger = logging.getLogger(__name__)

RUNNER_TIMEOUT_SECONDS = 30
CHECK_INTERVAL_SECONDS = 10


async def monitor_runners(SessionLocal):
    """
    Runs forever in the background.
    Marks runners dead if they stop sending heartbeats.
    Reassigns their jobs back to pending so another runner picks them up.
    """
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(
                seconds=RUNNER_TIMEOUT_SECONDS
            )

            stale_runners = db.query(Runner).filter(
                Runner.last_heartbeat < cutoff,
                Runner.status != RunnerStatus.DEAD
            ).all()

            for runner in stale_runners:
                logger.warning(
                    f"Runner {runner.runner_id} missed heartbeat. Marking dead."
                )
                runner.status = RunnerStatus.DEAD

                if runner.current_job:
                    job = db.query(Job).filter(
                        Job.job_id == runner.current_job
                    ).first()
                    if job and job.status in (JobStatus.ASSIGNED, JobStatus.RUNNING):
                        logger.warning(
                            f"Reassigning job {job.job_id} from dead runner "
                            f"{runner.runner_id}"
                        )
                        job.status = JobStatus.PENDING
                        job.assigned_runner = None

                runner.current_job = None

            db.commit()

        except Exception as e:
            logger.error(f"Error in heartbeat monitor: {e}")
        finally:
            db.close()