from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
from app.db import SessionLocal
from app.models import GameRun, ShopeeOrderGenerationLog
from app.services.shopee_order_cancellation import auto_cancel_overdue_orders_by_tick
from app.services.shopee_order_simulator import simulate_orders_for_run

logger = logging.getLogger(__name__)

REAL_SECONDS_PER_GAME_DAY = 30 * 60
REAL_SECONDS_PER_GAME_HOUR = REAL_SECONDS_PER_GAME_DAY / 24


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name, str(default)).strip().lower())
    return raw in {"1", "true", "yes", "on"}


AUTO_ORDER_TICK_ENABLED = _env_bool("AUTO_ORDER_TICK_ENABLED", True)
AUTO_ORDER_TICK_INTERVAL_SECONDS = max(5, int(os.getenv("AUTO_ORDER_TICK_INTERVAL_SECONDS", "15")))
AUTO_ORDER_TICK_MAX_TICKS_PER_RUN = max(1, int(os.getenv("AUTO_ORDER_TICK_MAX_TICKS_PER_RUN", "2")))
AUTO_ORDER_TICK_STEP_HOURS = max(1, int(os.getenv("AUTO_ORDER_TICK_STEP_HOURS", "8")))
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "cbec")
REDIS_LOCK_TTL_SEC = max(10, int(os.getenv("REDIS_LOCK_TTL_SEC", "45")))


def _resolve_target_game_tick(run: GameRun, now: datetime) -> datetime:
    if not run.created_at:
        return now
    elapsed_seconds = max(0, int((now - run.created_at).total_seconds()))
    elapsed_game_hours = int(elapsed_seconds // REAL_SECONDS_PER_GAME_HOUR)
    return run.created_at + timedelta(hours=elapsed_game_hours)


def _align_compare_time(ref: datetime, val: datetime) -> datetime:
    if ref.tzinfo is not None and val.tzinfo is None:
        return val.replace(tzinfo=ref.tzinfo)
    if ref.tzinfo is None and val.tzinfo is not None:
        return val.replace(tzinfo=None)
    return val


def _resolve_run_end_time(run: GameRun) -> datetime | None:
    if not run.created_at:
        return None
    return run.created_at + timedelta(days=max(1, int(run.duration_days or 1)))


def _mark_run_finished_if_reached(db: Session, run: GameRun, *, tick_time: datetime) -> bool:
    status_value = (run.status or "").strip()
    if status_value == "finished":
        return True
    if status_value != "running":
        return False
    run_end_time = _resolve_run_end_time(run)
    if not run_end_time:
        return False
    compare_tick = _align_compare_time(run_end_time, tick_time)
    if compare_tick < run_end_time:
        return False
    run.status = "finished"
    db.commit()
    db.refresh(run)
    return True


def _run_one_cycle(db: Session, now: datetime) -> tuple[int, int]:
    running_runs = db.query(GameRun).filter(GameRun.status == "running").all()
    simulated_run_count = 0
    simulated_tick_count = 0

    for run in running_runs:
        lock_key = f"{REDIS_PREFIX}:lock:shopee:auto_tick:{run.id}:{run.user_id}"
        lock_token = acquire_distributed_lock(lock_key, REDIS_LOCK_TTL_SEC)
        if lock_token is None:
            continue
        try:
            if _mark_run_finished_if_reached(db, run, tick_time=_resolve_target_game_tick(run, now)):
                continue
            latest_tick_time = (
                db.query(func.max(ShopeeOrderGenerationLog.tick_time))
                .filter(
                    ShopeeOrderGenerationLog.run_id == run.id,
                    ShopeeOrderGenerationLog.user_id == run.user_id,
                )
                .scalar()
            )
            base_tick = latest_tick_time or run.created_at
            if not base_tick:
                continue
            target_tick = _resolve_target_game_tick(run, now)
            step_seconds = 3600 * AUTO_ORDER_TICK_STEP_HOURS
            missing_steps = int((target_tick - base_tick).total_seconds() // step_seconds)
            if missing_steps <= 0:
                continue

            ticks_to_run = min(missing_steps, AUTO_ORDER_TICK_MAX_TICKS_PER_RUN)
            for step in range(1, ticks_to_run + 1):
                result = simulate_orders_for_run(
                    db,
                    run_id=run.id,
                    user_id=run.user_id,
                    tick_time=base_tick + timedelta(hours=step * AUTO_ORDER_TICK_STEP_HOURS),
                )
                auto_cancel_overdue_orders_by_tick(
                    db,
                    run_id=run.id,
                    user_id=run.user_id,
                    current_tick=result["tick_time"],
                    commit=True,
                )
                simulated_tick_count += 1
            simulated_run_count += 1
        finally:
            release_distributed_lock(lock_key, lock_token)

    return simulated_run_count, simulated_tick_count


async def run_auto_order_tick_worker(stop_event: asyncio.Event) -> None:
    logger.info(
        "Auto order tick worker started: interval=%ss, tick_step_hours=%s, max_ticks_per_run=%s",
        AUTO_ORDER_TICK_INTERVAL_SECONDS,
        AUTO_ORDER_TICK_STEP_HOURS,
        AUTO_ORDER_TICK_MAX_TICKS_PER_RUN,
    )
    while not stop_event.is_set():
        started = time.monotonic()
        db = SessionLocal()
        try:
            run_cnt, tick_cnt = _run_one_cycle(db, datetime.utcnow())
            if tick_cnt > 0:
                logger.info("Auto order tick simulated: runs=%s ticks=%s", run_cnt, tick_cnt)
        except Exception:
            logger.exception("Auto order tick worker cycle failed")
        finally:
            db.close()

        elapsed = time.monotonic() - started
        sleep_for = max(0.5, AUTO_ORDER_TICK_INTERVAL_SECONDS - elapsed)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
        except asyncio.TimeoutError:
            pass

    logger.info("Auto order tick worker stopped")
