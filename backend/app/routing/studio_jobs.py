"""Visitor-scoped jobs survive browser disconnects; completed results remain in run storage.

Workers stay on this API process and use the existing private planning event loop.
Reloading a browser only polls again. An API process restart cannot resume provider
work; persisted unfinished rows are reported honestly instead of automatically rerun.
"""

import asyncio
import json
from dataclasses import dataclass, field
from time import monotonic

from fastapi import HTTPException
from pydantic import RootModel

from app.agent.progress_stream import stream_turn
from app.crud import lab_runs


async def stored_record(owner, key):
    try:
        return await asyncio.to_thread(lab_runs.record, owner, key)
    except Exception:
        raise HTTPException(503, "Saved runs are unavailable. Try reconnecting.") from None


@dataclass
class Job:
    owner: str
    payload: dict | None
    progress: dict = field(default_factory=dict)
    terminal: dict | None = None
    task: asyncio.Task | None = None
    finished: float | None = None

    def snapshot(self):
        return self.terminal or {"state": "running", "progress": list(self.progress.values())}


def saved_snapshot(row):
    if row["status"] == "running":
        return {
            "state": "interrupted",
            "message": "This run is no longer connected. Check History.",
        }
    saved = row.get("result") or {}
    return {
        "state": "complete",
        "result": {
            "schema_version": 1,
            "mode": row["mode"],
            "snapshot": {
                "id": str(row["id"]),
                "label": "Saved trip",
                "source": "Saved run history",
            },
            **saved,
            "stages": saved.get("stages") or [],
            "explanation": saved.get("explanation") or {},
            "input_snapshot": saved.get("input_snapshot") or row["input"],
            "run_record": {"id": str(row["id"]), "saved": True, "metrics": row.get("metrics")},
        },
    }


class StudioJobs:
    def __init__(self):
        self.jobs = {}
        self.lock = asyncio.Lock()

    def prune(self):
        finished = sorted(
            [(key, job) for key, job in self.jobs.items() if job.finished is not None],
            key=lambda pair: pair[1].finished,
        )
        for index, (key, job) in enumerate(finished):
            if index < len(finished) - 16 or monotonic() - job.finished > 3600:
                del self.jobs[key]  # Saved rows retain completed results after memory eviction.

    async def start(self, owner, job_id, payload, execute):
        key = str(job_id)
        async with self.lock:
            self.prune()
            if job := self.jobs.get(key):
                if job.owner != owner:
                    raise HTTPException(404, "Run not found.")
                if job.payload is None:
                    return job.snapshot()
                if job.payload != payload:
                    raise HTTPException(409, "This run already has different inputs.")
                return job.snapshot()
            if row := await stored_record(owner, key):
                return saved_snapshot(row)
            active = [job for job in self.jobs.values() if job.terminal is None]
            if any(job.owner == owner for job in active):
                raise HTTPException(409, "A trip is already running. Open History or reconnect.")
            if len(active) >= 4:
                raise HTTPException(429, "Studio is busy. Try again shortly.")
            job = Job(owner=owner, payload=payload)
            self.jobs[key] = job
            job.task = asyncio.create_task(self.execute(job, execute))
            return job.snapshot()

    async def execute(self, job, execute):
        async def run():
            return RootModel[dict](await execute())

        try:
            async for line in stream_turn(run, stage_name="studio.run"):
                event = json.loads(line)
                if event["type"] == "progress":
                    if len(job.progress) < 256 or event["stage"] in job.progress:
                        job.progress[event["stage"]] = event
                elif event["type"] == "result":
                    job.terminal = {"state": "complete", "result": event["response"]}
                elif event["type"] == "error":
                    job.terminal = {"state": "failed", "status": event["status"]}
        except asyncio.CancelledError:
            job.terminal = {"state": "cancelled", "status": 499}
            raise
        except Exception:
            job.terminal = {"state": "failed", "status": 503}
        finally:
            job.finished = monotonic()

    async def get(self, owner, job_id):
        key = str(job_id)
        if job := self.jobs.get(key):
            if job.owner != owner:
                raise HTTPException(404, "Run not found.")
            return job.snapshot()
        if row := await stored_record(owner, key):
            return saved_snapshot(row)
        raise HTTPException(404, "Run not found. Open History to see saved trips.")

    async def cancel(self, owner, job_id):
        key = str(job_id)
        async with self.lock:
            job = self.jobs.get(key)
            if job is None:
                row = await stored_record(owner, key)
                if row is not None:
                    if row["status"] == "running":
                        await asyncio.to_thread(lab_runs.cancel, owner, key)
                    return (
                        saved_snapshot(row)
                        if row["status"] != "running"
                        else {"state": "cancelled"}
                    )
                # Remember a cancellation that overtook its POST; a late POST must not start work.
                self.prune()
                self.jobs[key] = Job(
                    owner=owner,
                    payload=None,
                    terminal={"state": "cancelled", "status": 499},
                    finished=monotonic(),
                )
                return self.jobs[key].snapshot()
            if job.owner != owner:
                raise HTTPException(404, "Run not found.")
            if job.terminal is None:
                job.terminal = {"state": "cancelled", "status": 499}
                job.finished = monotonic()
                job.task.cancel()
                await asyncio.gather(job.task, return_exceptions=True)
            return job.snapshot()

    async def shutdown(self):
        tasks = [job.task for job in self.jobs.values() if job.task and not job.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


jobs = StudioJobs()
