import logging
import time
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Query

from app import storage, racing_api
from app.config import BACKFILL_START_DATE
from app.secrets import get_racing_api_credentials
from app.firestore_client import load_settings
from app.state import state, LogEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["operational"])


def _run_backfill(start: date, end: date, skip_existing: bool, job_id: str):
    settings = load_settings()
    max_rps = settings.get("max_rps", 1.0)
    max_retries = int(settings.get("max_retries", 5))
    base_url = settings.get("base_url", "https://api.theracingapi.com/v1")
    username, password = get_racing_api_credentials()

    total_days = (end - start).days + 1
    state.mode = "BACKFILL"
    state.progress_total = total_days
    state.progress_current = 0
    state.notify_status()

    current = start
    delay = 1.0 / max_rps

    try:
        while current <= end:
            date_str = current.isoformat()
            state.current_item = date_str
            state.progress_current = (current - start).days + 1

            if state.progress_current % 100 == 0:
                logger.info("Backfill progress: %d/%d (%s)", state.progress_current, total_days, date_str)

            # Calculate ETA
            if state.progress_current > 0:
                elapsed = time.time() - state.start_time
                rate = state.progress_current / elapsed if elapsed > 0 else 1
                remaining = total_days - state.progress_current
                state.eta_seconds = int(remaining / rate) if rate > 0 else 0

            state.notify_status()

            if skip_existing and storage.file_exists("results", current):
                current += timedelta(days=1)
                continue

            t0 = time.time()
            try:
                data = racing_api.fetch_results(
                    username, password, date_str,
                    base_url=base_url, max_retries=max_retries,
                )
                duration_ms = int((time.time() - t0) * 1000)

                if data and (isinstance(data, list) and len(data) > 0 or isinstance(data, dict) and data):
                    size = storage.save_json("results", current, data)
                    record_count = len(data) if isinstance(data, list) else 1
                else:
                    storage.save_empty_marker("results", current)
                    size = 2
                    record_count = 0

                state.records_processed += 1
                state.add_log(LogEntry(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action="FETCH_AND_STORE",
                    detail=date_str,
                    records=record_count,
                    size_bytes=size,
                    status=200,
                    duration_ms=duration_ms,
                ))

            except Exception as e:
                state.errors_total += 1
                state.records_processed += 1
                state.add_log(LogEntry(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    action="FETCH_ERROR",
                    detail=f"{date_str}: {str(e)[:200]}",
                    status=500,
                    duration_ms=int((time.time() - t0) * 1000),
                ))
                state.last_error = str(e)[:500]
                state.notify_error(str(e)[:500])
                logger.error("Error fetching %s: %s", date_str, e)

            time.sleep(delay)
            current += timedelta(days=1)

        state.mode = "IDLE"
        state.notify_status()
        logger.info("Backfill complete: %d days processed", total_days)

    except Exception as e:
        state.mode = "ERROR"
        state.last_error = str(e)[:500]
        state.notify_error(str(e)[:500])
        logger.exception("Backfill failed")


@router.post("/backfill")
async def backfill(
    background_tasks: BackgroundTasks,
    start_date: str = Query(default=BACKFILL_START_DATE),
    end_date: str = Query(default=""),
):
    if state.mode in ("BACKFILL", "SYNC"):
        return {"error": f"Already running: {state.mode}", "job_id": state.active_job_id}

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date) if end_date else date.today()

    settings = load_settings()
    skip_existing = settings.get("skip_existing", True)

    job_id = state.new_job_id()
    background_tasks.add_task(_run_backfill, start, end, skip_existing, job_id)

    return {
        "job_id": job_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_days": (end - start).days + 1,
        "skip_existing": skip_existing,
        "message": "Backfill started in background",
    }


@router.post("/sync")
async def sync(background_tasks: BackgroundTasks):
    if state.mode in ("BACKFILL", "SYNC"):
        return {"error": f"Already running: {state.mode}", "job_id": state.active_job_id}

    latest = storage.get_latest_date("results")
    if latest is None:
        start = date.fromisoformat(BACKFILL_START_DATE)
    else:
        start = latest + timedelta(days=1)

    end = date.today()

    if start > end:
        return {"message": "Already up to date", "latest_date": latest.isoformat() if latest else None}

    job_id = state.new_job_id()
    state.mode = "SYNC"

    settings = load_settings()
    skip_existing = settings.get("skip_existing", True)

    background_tasks.add_task(_run_backfill, start, end, skip_existing, job_id)

    return {
        "job_id": job_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days_to_sync": (end - start).days + 1,
        "message": "Sync started in background",
    }


@router.get("/stats")
async def stats():
    total_files = storage.count_files("results")
    first_date, last_date = storage.get_date_range("results")
    gaps = storage.find_gaps("results")

    return {
        "total_files": total_files,
        "date_range": {
            "first": first_date,
            "last": last_date,
        },
        "gaps_count": len(gaps),
        "gaps": gaps[:100],
    }
