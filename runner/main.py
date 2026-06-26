import asyncio
import logging
import os
import time

import httpx

from checks.structural import run_structural_checks
from checks.statistical import run_statistical_checks
from checks.referential import run_referential_checks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISPATCHER_URL = os.getenv("DISPATCHER_URL", "http://localhost:8000")
RUNNER_ID = os.getenv("RUNNER_ID", "runner-1")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "5"))
POLL_INTERVAL = 3


async def register():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DISPATCHER_URL}/runners/register",
            json={"runner_id": RUNNER_ID},
            timeout=10.0
        )
        response.raise_for_status()
        logger.info(f"Runner {RUNNER_ID} registered with dispatcher")


async def send_heartbeat(current_job_id: str | None = None):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{DISPATCHER_URL}/runners/heartbeat",
            json={"runner_id": RUNNER_ID, "job_id": current_job_id},
            timeout=5.0
        )


async def poll_for_job() -> dict | None:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{DISPATCHER_URL}/runners/job/{RUNNER_ID}",
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()


async def submit_result(payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DISPATCHER_URL}/jobs/result",
            json=payload,
            timeout=10.0
        )
        response.raise_for_status()


def execute_checks(job: dict) -> tuple[list[dict], str]:
    repo_path = job["repo_path"]
    results = []

    check_map = {
        "structural": run_structural_checks,
        "statistical": run_statistical_checks,
        "referential": run_referential_checks,
    }

    for category in job.get("checks_to_run", []):
        fn = check_map.get(category)
        if not fn:
            continue
        category_results = fn(repo_path)
        results.extend(category_results)

    overall = "passed" if all(r["passed"] for r in results) else "failed"
    return results, overall


async def run():
    await register()

    heartbeat_counter = 0
    current_job_id = None

    while True:
        heartbeat_counter += 1
        if heartbeat_counter >= (HEARTBEAT_INTERVAL // POLL_INTERVAL):
            try:
                await send_heartbeat(current_job_id)
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            heartbeat_counter = 0

        try:
            job = await poll_for_job()
        except Exception as e:
            logger.warning(f"Could not poll for job: {e}")
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if not job:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        current_job_id = job["job_id"]
        logger.info(
            f"Picked up job {current_job_id} for commit {job['commit_id'][:8]}"
        )

        start = time.time()
        error_message = None

        try:
            results, status = execute_checks(job)
        except Exception as e:
            logger.error(f"Check execution error: {e}")
            results = []
            status = "failed"
            error_message = str(e)

        duration = round(time.time() - start, 2)

        try:
            await submit_result({
                "job_id": current_job_id,
                "runner_id": RUNNER_ID,
                "status": status,
                "results": results,
                "duration_seconds": duration,
                "error_message": error_message,
            })
            logger.info(f"Job {current_job_id} completed: {status} in {duration}s")
        except Exception as e:
            logger.error(f"Failed to submit result: {e}")

        current_job_id = None
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())