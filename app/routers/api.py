import logging
import threading
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

STATIC_ENDPOINTS = [
    ("courses", "courses"),
    ("jockeys", "jockeys"),
    ("trainers", "trainers"),
]


def _run_backfill(start: date, end: date, skip_existing: bool, job_id: str, mode: str = "BACKFILL"):
    settings = load_settings()
    max_rps = settings.get("max_rps", 1.0)
    max_retries = int(settings.get("max_retries", 5))
    base_url = settings.get("base_url", "https://api.theracingapi.com/v1")
    username, password = get_racing_api_credentials()

    total_days = (end - start).days + 1
    state.mode = mode
    state.progress_total = total_days
    state.progress_current = 0
    state.notify_status()

    current = start
    delay = 1.0 / max_rps
    job_start = time.time()

    try:
        while current <= end:
            date_str = current.isoformat()
            state.current_item = date_str
            state.progress_current = (current - start).days + 1

            if state.progress_current % 100 == 0:
                logger.info("%s progress: %d/%d (%s)", mode, state.progress_current, total_days, date_str)

            if state.progress_current > 0:
                elapsed = time.time() - job_start
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
        logger.info("%s complete: %d days processed", mode, total_days)

    except Exception as e:
        state.mode = "ERROR"
        state.last_error = str(e)[:500]
        state.notify_error(str(e)[:500])
        logger.exception("%s failed", mode)


def _run_racecards_backfill(start: date, end: date, skip_existing: bool):
    settings = load_settings()
    max_rps = settings.get("max_rps", 1.0)
    max_retries = int(settings.get("max_retries", 5))
    base_url = settings.get("base_url", "https://api.theracingapi.com/v1")
    username, password = get_racing_api_credentials()
    delay = 1.0 / max_rps
    current = start

    logger.info("Racecards backfill starting: %s to %s", start, end)

    while current <= end:
        date_str = current.isoformat()

        if skip_existing and storage.file_exists("racecards", current):
            current += timedelta(days=1)
            continue

        t0 = time.time()
        try:
            data = racing_api.fetch_static(
                username, password, "racecards",
                params={"start_date": date_str, "end_date": date_str},
                base_url=base_url, max_retries=max_retries,
            )
            duration_ms = int((time.time() - t0) * 1000)

            if data is None:
                logger.info("Racecards not available on this plan — stopping racecards backfill")
                return

            if data and (isinstance(data, list) and len(data) > 0 or isinstance(data, dict) and data):
                size = storage.save_json("racecards", current, data)
                record_count = len(data) if isinstance(data, list) else 1
            else:
                storage.save_empty_marker("racecards", current)
                size = 2
                record_count = 0

            state.add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action="FETCH_AND_STORE",
                detail=f"racecards:{date_str}",
                records=record_count,
                size_bytes=size,
                status=200,
                duration_ms=duration_ms,
            ))

        except Exception as e:
            state.errors_total += 1
            state.add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action="FETCH_ERROR",
                detail=f"racecards:{date_str}: {str(e)[:200]}",
                status=500,
                duration_ms=int((time.time() - t0) * 1000),
            ))
            logger.error("Error fetching racecards %s: %s", date_str, e)

        time.sleep(delay)
        current += timedelta(days=1)

    logger.info("Racecards backfill complete")


def _fetch_static_endpoints():
    settings = load_settings()
    base_url = settings.get("base_url", "https://api.theracingapi.com/v1")
    max_retries = int(settings.get("max_retries", 5))
    username, password = get_racing_api_credentials()

    for prefix, path in STATIC_ENDPOINTS:
        t0 = time.time()
        try:
            data = racing_api.fetch_static(
                username, password, path,
                base_url=base_url, max_retries=max_retries,
            )
            duration_ms = int((time.time() - t0) * 1000)

            if data is None:
                logger.info("Static endpoint not available on this plan: %s", prefix)
                continue

            size = storage.save_blob(f"{prefix}/data.json", data)
            record_count = len(data) if isinstance(data, list) else 1
            state.add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action="FETCH_AND_STORE",
                detail=prefix,
                records=record_count,
                size_bytes=size,
                status=200,
                duration_ms=duration_ms,
            ))
            logger.info("Fetched static %s: %d records", prefix, record_count)

        except Exception as e:
            state.errors_total += 1
            state.add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action="FETCH_ERROR",
                detail=f"{prefix}: {str(e)[:200]}",
                status=500,
                duration_ms=int((time.time() - t0) * 1000),
            ))
            logger.error("Error fetching static %s: %s", prefix, e)


def _run_backfill_with_extended(start: date, end: date, skip_existing: bool, job_id: str):
    racecards_thread = threading.Thread(
        target=_run_racecards_backfill, args=(start, end, skip_existing), daemon=True,
    )
    static_thread = threading.Thread(
        target=_fetch_static_endpoints, daemon=True,
    )
    racecards_thread.start()
    static_thread.start()
    _run_backfill(start, end, skip_existing, job_id)
    racecards_thread.join()
    static_thread.join()


@router.post("/backfill")
async def backfill(
    background_tasks: BackgroundTasks,
    start_date: str = Query(default=BACKFILL_START_DATE),
    end_date: str = Query(default=""),
    extended: bool = Query(default=False, description="Also download racecards, courses, jockeys, trainers in parallel"),
):
    if state.mode in ("BACKFILL", "SYNC"):
        return {"error": f"Already running: {state.mode}", "job_id": state.active_job_id}

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date) if end_date else date.today()

    settings = load_settings()
    skip_existing = settings.get("skip_existing", True)

    job_id = state.new_job_id()
    state.mode = "BACKFILL"

    if extended:
        background_tasks.add_task(_run_backfill_with_extended, start, end, skip_existing, job_id)
    else:
        background_tasks.add_task(_run_backfill, start, end, skip_existing, job_id)

    return {
        "job_id": job_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_days": (end - start).days + 1,
        "skip_existing": skip_existing,
        "extended": extended,
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

    background_tasks.add_task(_run_backfill, start, end, skip_existing, job_id, "SYNC")

    return {
        "job_id": job_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days_to_sync": (end - start).days + 1,
        "message": "Sync started in background",
    }


@router.post("/probe")
async def probe():
    """Probe additional Racing API endpoints to check what's available on this plan."""
    settings = load_settings()
    base_url = settings.get("base_url", "https://api.theracingapi.com/v1")
    username, password = get_racing_api_credentials()
    today = date.today().isoformat()

    to_probe = [
        ("racecards", "racecards", {"start_date": today, "end_date": today}),
        ("courses", "courses", {}),
        ("jockeys", "jockeys", {}),
        ("trainers", "trainers", {}),
    ]

    results = {}
    for key, path, params in to_probe:
        available, data = racing_api.probe_endpoint(username, password, path, params, base_url)
        entry = {"available": available}
        if available:
            entry["record_count"] = len(data) if isinstance(data, list) else 1
        else:
            entry["detail"] = data
        results[key] = entry

    return {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "endpoints": results,
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
