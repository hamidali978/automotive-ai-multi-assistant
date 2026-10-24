import asyncio
import logging

from app.crm.service import CRMService

log = logging.getLogger(__name__)


class QueueWorker:
    """Background loop that replays queued CRM writes once Zoho is reachable again."""

    def __init__(self, crm: CRMService, interval_s: float):
        self._crm, self._interval = crm, interval_s
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="crm-retry-queue")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                stats = await self._crm.process_queue()
                if any(stats.values()):
                    log.info("retry queue processed: %s", stats)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("retry queue iteration failed")
