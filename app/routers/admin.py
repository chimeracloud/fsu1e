import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import (
    FSU_ID, FSU_NAME, FSU_VERSION, GCP_PROJECT, GCP_REGION,
    GCS_BUCKET, FIRESTORE_COLLECTION, SERVICE_ACCOUNT, CLOUD_RUN_URL,
    EDITABLE_FIELDS, VALIDATION_RULES,
)
from app.firestore_client import load_settings, save_settings
from app.state import state

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
async def health():
    return {
        "fsu_id": FSU_ID,
        "name": FSU_NAME,
        "version": FSU_VERSION,
        "status": state.status,
        "uptime_seconds": state.uptime_seconds,
        "last_error": state.last_error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
async def status():
    return {
        "mode": state.mode,
        "progress": {
            "current": state.progress_current,
            "total": state.progress_total,
            "percentage": state.progress_percentage,
            "current_item": state.current_item,
            "eta_seconds": state.eta_seconds,
        },
        "last_activity": state.last_activity,
        "records_processed": state.records_processed,
        "errors_total": state.errors_total,
        "error_rate": round(state.error_rate, 4),
    }


def _build_settings_response(settings: dict) -> dict:
    return {
        "fsu_id": FSU_ID,
        "version": settings.get("version", 1),
        "updated_at": settings.get("updated_at", ""),
        "groups": [
            {
                "id": "api_connection",
                "label": "API Connection",
                "fields": [
                    {"key": "base_url", "label": "Base URL", "type": "text",
                     "value": settings.get("base_url", ""), "editable": True, "hint": None},
                    {"key": "username", "label": "Username", "type": "text",
                     "value": "chimera-prod", "editable": False,
                     "hint": "Managed via Google Secret Manager"},
                    {"key": "password", "label": "Password", "type": "secret",
                     "value": "********", "editable": False,
                     "hint": "Managed via Google Secret Manager"},
                ],
            },
            {
                "id": "storage",
                "label": "Storage",
                "fields": [
                    {"key": "gcs_bucket", "label": "GCS Bucket", "type": "text",
                     "value": settings.get("gcs_bucket", ""), "editable": True, "hint": None},
                    {"key": "gcp_project", "label": "GCP Project", "type": "text",
                     "value": settings.get("gcp_project", ""), "editable": False, "hint": None},
                    {"key": "region", "label": "Region", "type": "text",
                     "value": settings.get("region", ""), "editable": False, "hint": None},
                ],
            },
            {
                "id": "rate_control",
                "label": "Rate Control",
                "fields": [
                    {"key": "max_rps", "label": "Max Requests/Second", "type": "number",
                     "value": settings.get("max_rps", 1.0), "editable": True, "hint": None},
                    {"key": "max_retries", "label": "Max Retries", "type": "number",
                     "value": settings.get("max_retries", 5), "editable": True, "hint": None},
                    {"key": "backoff_strategy", "label": "Backoff Strategy", "type": "text",
                     "value": "Exponential (2s, 4s, 8s, 16s)", "editable": False, "hint": None},
                ],
            },
            {
                "id": "backfill",
                "label": "Backfill Configuration",
                "fields": [
                    {"key": "start_date", "label": "Start Date", "type": "date",
                     "value": settings.get("start_date", "2014-01-01"), "editable": True, "hint": None},
                    {"key": "end_date", "label": "End Date", "type": "date",
                     "value": settings.get("end_date", ""), "editable": True,
                     "hint": "Defaults to today if blank"},
                    {"key": "skip_existing", "label": "Skip Existing", "type": "boolean",
                     "value": settings.get("skip_existing", True), "editable": True,
                     "hint": "Resume where it left off if interrupted"},
                ],
            },
        ],
    }


@router.get("/settings")
async def get_settings():
    settings = load_settings()
    return _build_settings_response(settings)


class SettingsUpdate(BaseModel):
    updates: dict


@router.put("/settings")
async def put_settings(body: SettingsUpdate):
    applied = []
    rejected = []

    for key, value in body.updates.items():
        if key not in EDITABLE_FIELDS:
            rejected.append({"key": key, "reason": "not_editable"})
            continue

        if key in VALIDATION_RULES:
            rules = VALIDATION_RULES[key]
            if isinstance(value, (int, float)):
                if value < rules.get("min", float("-inf")):
                    rejected.append({"key": key, "reason": f"below_minimum ({rules['min']})"})
                    continue
                if value > rules.get("max", float("inf")):
                    rejected.append({"key": key, "reason": f"above_maximum ({rules['max']})"})
                    continue

        applied.append(key)

    if applied:
        valid_updates = {k: body.updates[k] for k in applied}
        settings = save_settings(valid_updates, updated_by="portal")
    else:
        settings = load_settings()

    return {
        "fsu_id": FSU_ID,
        "version": settings.get("version", 1),
        "updated_at": settings.get("updated_at", ""),
        "applied": applied,
        "rejected": rejected,
        "settings": _build_settings_response(settings),
    }


@router.get("/config")
async def config():
    return {
        "fsu_id": FSU_ID,
        "repo": "chimeracloud/fsu1e",
        "gcp_project": GCP_PROJECT,
        "region": GCP_REGION,
        "bucket": GCS_BUCKET,
        "firestore_collection": FIRESTORE_COLLECTION,
        "service_account": SERVICE_ACCOUNT,
        "cloud_run_url": CLOUD_RUN_URL,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/logs")
async def logs(limit: int = 50, offset: int = 0):
    all_logs = list(state.logs)
    total = len(all_logs)
    page = all_logs[offset:offset + limit]

    return {
        "total": total,
        "entries": [
            {
                "timestamp": e.timestamp,
                "action": e.action,
                "detail": e.detail,
                "records": e.records,
                "size_bytes": e.size_bytes,
                "status": e.status,
                "duration_ms": e.duration_ms,
            }
            for e in reversed(page)
        ],
    }


@router.get("/stream")
async def stream(request: Request):
    queue = state.subscribe()

    async def event_generator():
        try:
            # Send initial health ping
            yield {
                "event": "health",
                "data": json.dumps({
                    "status": state.status,
                    "uptime_seconds": state.uptime_seconds,
                }),
            }

            while True:
                if await request.is_disconnected():
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": msg["event"],
                        "data": json.dumps(msg["data"]),
                    }
                except asyncio.TimeoutError:
                    # Send periodic health ping as keepalive
                    yield {
                        "event": "health",
                        "data": json.dumps({
                            "status": state.status,
                            "uptime_seconds": state.uptime_seconds,
                        }),
                    }
        finally:
            state.unsubscribe(queue)

    return EventSourceResponse(event_generator())
