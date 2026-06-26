import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from git import Repo, InvalidGitRepositoryError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISPATCHER_URL = os.getenv("DISPATCHER_URL", "http://localhost:8000")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
REPO_PATH = os.getenv("REPO_PATH", "../tests/sample_pipeline")


class RepoObserver:
    def __init__(self, repo_path: str, dispatcher_url: str):
        self.repo_path = repo_path
        self.dispatcher_url = dispatcher_url
        self.last_seen_commit: str | None = None

        try:
            self.repo = Repo(repo_path)
        except InvalidGitRepositoryError:
            raise RuntimeError(f"No valid Git repo found at {repo_path}")

    def get_latest_commit(self) -> tuple[str, datetime]:
        commit = self.repo.commit("HEAD")
        committed_at = datetime.fromtimestamp(
            commit.committed_date, tz=timezone.utc
        )
        return commit.hexsha, committed_at

    async def dispatch(self, commit_id: str, committed_at: datetime):
        payload = {
            "commit_id": commit_id,
            "repo_path": os.path.abspath(self.repo_path),
            "committed_at": committed_at.isoformat(),
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.dispatcher_url}/dispatch",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Dispatched commit {commit_id[:8]} → job {data['job_id']}")

    async def poll(self):
        logger.info(f"Observer watching {self.repo_path} every {POLL_INTERVAL}s")
        while True:
            try:
                commit_id, committed_at = self.get_latest_commit()

                if commit_id != self.last_seen_commit:
                    logger.info(f"New commit detected: {commit_id[:8]}")
                    await self.dispatch(commit_id, committed_at)
                    self.last_seen_commit = commit_id
                else:
                    logger.debug(f"No new commits. Latest: {commit_id[:8]}")

            except httpx.HTTPError as e:
                logger.error(f"Could not reach dispatcher: {e}")
            except Exception as e:
                logger.error(f"Observer error: {e}")

            await asyncio.sleep(POLL_INTERVAL)


async def main():
    observer = RepoObserver(
        repo_path=REPO_PATH,
        dispatcher_url=DISPATCHER_URL,
    )
    await observer.poll()


if __name__ == "__main__":
    asyncio.run(main())