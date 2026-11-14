from app.core.database import SessionLocal
from app.modules.backtests.service import BacktestService


def execute_backtest_job(run_id: int) -> None:
    with SessionLocal() as session:
        BacktestService(session).execute_run(run_id)
