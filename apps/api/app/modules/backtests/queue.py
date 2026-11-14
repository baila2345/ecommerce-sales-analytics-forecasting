from typing import Protocol

from redis import Redis
from rq import Queue

from app.core.config import get_settings


BACKTEST_QUEUE = "model-backtests"


class BacktestDispatcher(Protocol):
    def enqueue(self, run_id: int) -> str: ...


class RQBacktestDispatcher:
    def __init__(self) -> None:
        connection = Redis.from_url(get_settings().redis_url)
        self.queue = Queue(BACKTEST_QUEUE, connection=connection)

    def enqueue(self, run_id: int) -> str:
        from app.modules.backtests.jobs import execute_backtest_job

        job = self.queue.enqueue(
            execute_backtest_job,
            run_id,
            job_timeout=3600,
            result_ttl=86400,
            failure_ttl=604800,
        )
        return job.id


def get_backtest_dispatcher() -> BacktestDispatcher:
    return RQBacktestDispatcher()
