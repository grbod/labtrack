"""In-process serial worker for result imports."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.database import SessionLocal
from app.services.result_import_service import ResultImportService
from app.utils.logger import logger

_queue: Optional[asyncio.Queue[int]] = None
_task: Optional[asyncio.Task] = None


async def start_result_import_worker() -> None:
    """Start the single import worker for this process."""
    global _queue, _task
    if _queue is None:
        _queue = asyncio.Queue()
    if _task is None or _task.done():
        _task = asyncio.create_task(_worker_loop())


async def stop_result_import_worker() -> None:
    """Stop the worker task."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


async def enqueue_result_import(import_id: int) -> None:
    """Queue an import for serial processing."""
    if _queue is None:
        await start_result_import_worker()
    await _queue.put(import_id)


async def _worker_loop() -> None:
    assert _queue is not None
    service = ResultImportService()
    while True:
        import_id = await _queue.get()
        try:
            db = SessionLocal()
            try:
                service.process_import(db, import_id)
            finally:
                db.close()
        except Exception:
            logger.opt(exception=True).error("Result import worker failed")
        finally:
            _queue.task_done()
