"""Transport progress even while legacy provider functions block their worker.

The turn runs in a private worker event loop. Disconnect cancels that loop's
turn at its next async boundary; bounded synchronous I/O may finish first.
"""

import asyncio
import json
import threading

from fastapi import HTTPException

from app.agent.progress import reporting, stage

HEARTBEAT_SECONDS = 10


async def stream_turn(run):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=256)
    stopped = threading.Event()
    active = {}

    def enqueue(event):
        if stopped.is_set():
            return
        if queue.full():
            queue.get_nowait()  # Keep newest progress and always retain final result.
        queue.put_nowait(event)

    def publish(event):
        if not stopped.is_set():
            loop.call_soon_threadsafe(enqueue, event)

    async def execute():
        active.update(loop=asyncio.get_running_loop(), task=asyncio.current_task())
        if stopped.is_set():
            return
        try:
            with reporting(publish), stage("agent.turn"):
                result = await run()
            publish({"type": "result", "response": result.model_dump(mode="json")})
        except HTTPException as exc:
            publish({"type": "error", "status": exc.status_code})
        except Exception:
            publish({"type": "error", "status": 503})

    worker = asyncio.create_task(asyncio.to_thread(lambda: asyncio.run(execute())))
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), HEARTBEAT_SECONDS)
            except TimeoutError:
                event = {"type": "heartbeat"}
            yield json.dumps(event, separators=(",", ":")) + "\n"
            if event["type"] in {"result", "error"}:
                break
    finally:
        stopped.set()
        worker_loop = active.get("loop")
        if worker_loop and not worker_loop.is_closed():
            try:
                worker_loop.call_soon_threadsafe(active["task"].cancel)
            except RuntimeError:
                pass  # Worker completed between the close check and cancellation.
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
