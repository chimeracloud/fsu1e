# FSU1E — Racing API Historic Data Ingest

## Service Overview

FSU1E is a Python FastAPI microservice deployed on Google Cloud Run that downloads the complete historic results database from **The Racing API** and stores raw JSON files in Google Cloud Storage (GCS). It provides a one-time full backfill capability, daily incremental sync, and implements the **Chimera Admin Endpoint Contract (CHI-ADR-010)** for portal integration.

**Live URL:** https://fsu1e-991649774709.europe-west2.run.app

---

## Deployment Details

| Property | Value |
|---|---|
| **GCP Project** | `chiops` |
| **Region** | `europe-west2` (London) |
| **Cloud Run URL** | https://fsu1e-991649774709.europe-west2.run.app |
| **GCS Bucket** | `fsu1e-racingapi-historic-raw` |
| **Firestore Collection** | `fsu-admin-settings` (document: `fsu1e`) |
| **Secret Manager Secret** | `racingapi-credentials` |
| **Service Account** | `991649774709-compute@developer.gserviceaccount.com` |
| **GitHub Repo** | `chimeracloud/fsu1e` |
| **Port** | 8080 |
| **CPU** | 1 |
| **Memory** | 512 MiB |
| **Request Timeout** | 300 seconds |
| **Scaling** | Auto (min: 0, max: 20) |
| **Billing** | Request-based |
| **Cloud Run Logs** | [View Logs](https://console.cloud.google.com/run/detail/europe-west2/fsu1e/revisions?project=chiops) |

---

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Chimera     │────▶│  FSU1E           │────▶│  The Racing API  │
│  Portal      │◀────│  (Cloud Run)     │◀────│  api.theracingapi│
│              │ SSE │                  │     │  .com/v1         │
└──────────────┘     │  FastAPI 3.12    │     └──────────────────┘
                     │                  │
                     │  ┌────────────┐  │     ┌──────────────────┐
                     │  │ Background │  │────▶│  GCS Bucket      │
                     │  │ Tasks      │  │     │  fsu1e-racingapi │
                     │  └────────────┘  │     │  -historic-raw   │
                     │                  │     └──────────────────┘
                     │  ┌────────────┐  │
                     │  │ Settings   │──│────▶┌──────────────────┐
                     │  └────────────┘  │     │  Firestore       │
                     └──────────────────┘     │  fsu-admin-      │
                                              │  settings/fsu1e  │
                                              └──────────────────┘
```

### Tech Stack

- **Runtime:** Python 3.12
- **Framework:** FastAPI + Uvicorn
- **Storage:** Google Cloud Storage (raw JSON)
- **Settings:** Google Cloud Firestore
- **Secrets:** Google Secret Manager
- **Deployment:** Cloud Run via Cloud Build (triggered by GitHub push)
- **SSE:** sse-starlette

---

## Endpoint Reference

FSU1E exposes two sets of endpoints:

### Set 1: Operational Endpoints (`/api/`)

These are the core data ingestion endpoints — the FSU's actual job.

---

#### `POST /api/backfill`

Triggers a full historic download from The Racing API. Runs in a background task and returns immediately with a job ID.

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `start_date` | string (YYYY-MM-DD) | `2014-01-01` | First date to fetch |
| `end_date` | string (YYYY-MM-DD) | today | Last date to fetch |

**Response:**
```json
{
  "job_id": "a1b2c3d4",
  "start_date": "2014-01-01",
  "end_date": "2026-04-15",
  "total_days": 4489,
  "skip_existing": true,
  "message": "Backfill started in background"
}
```

**Behaviour:**
- Iterates day by day from `start_date` to `end_date`
- For each day, calls `GET /v1/results?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` on The Racing API
- Saves raw JSON to GCS at `results/{YYYY}/{MM}/{DD}/results.json`
- Empty result days get an empty marker file (`[]`) so we know they were processed
- If `skip_existing` is true (default), skips days already in GCS — makes the job resumable after interruption
- Respects rate limits: 1 req/sec (configurable), exponential backoff on 429 or 5xx
- Logs progress every 100 days
- Rejects the call if a backfill or sync is already running

---

#### `POST /api/sync`

Daily incremental sync. Finds the latest date already in GCS and fetches everything from `latest + 1` to today.

**Response:**
```json
{
  "job_id": "e5f6g7h8",
  "start_date": "2026-04-14",
  "end_date": "2026-04-15",
  "days_to_sync": 2,
  "message": "Sync started in background"
}
```

If already up to date:
```json
{
  "message": "Already up to date",
  "latest_date": "2026-04-15"
}
```

---

#### `GET /api/stats`

Returns summary statistics about data in the GCS bucket.

**Response:**
```json
{
  "total_files": 4489,
  "date_range": {
    "first": "2014-01-01",
    "last": "2026-04-15"
  },
  "gaps_count": 3,
  "gaps": ["2018-06-12", "2020-03-15", "2020-03-16"]
}
```

---

### Set 2: Admin Endpoints (`/admin/`) — CHI-ADR-010

These endpoints implement the **Chimera Admin Endpoint Contract**. They are consumed by the Chimera portal at chimerasportstrading.com to display monitoring, settings, and status. The portal is a generic renderer — it contains no FSU1E-specific code.

---

#### `GET /admin/health`

Read-only health status. Called by the portal for the dashboard health indicator.

**Response:**
```json
{
  "fsu_id": "fsu1e",
  "name": "Racing API Historic Ingest",
  "version": "1.0.0",
  "status": "healthy",
  "uptime_seconds": 3847,
  "last_error": null,
  "timestamp": "2026-04-15T09:42:18Z"
}
```

**Status values:** `healthy` | `degraded` (error rate > 5%) | `error` (mode is ERROR)

---

#### `GET /admin/status`

Read-only operational state. Shows current mode, progress, and error counts.

**Response:**
```json
{
  "mode": "BACKFILL",
  "progress": {
    "current": 1847,
    "total": 4489,
    "percentage": 41.1,
    "current_item": "2019-01-14",
    "eta_seconds": 2640
  },
  "last_activity": "2026-04-15T09:42:17Z",
  "records_processed": 142847,
  "errors_total": 6,
  "error_rate": 0.003
}
```

**Mode values:** `IDLE` | `BACKFILL` | `SYNC` | `ERROR`

---

#### `GET /admin/settings`

Returns a structured form definition for the portal to render dynamically. Each field includes key, label, type, current value, editability, and optional hint. Fields are organised into groups.

**Response:**
```json
{
  "fsu_id": "fsu1e",
  "version": 3,
  "updated_at": "2026-04-15T08:00:00Z",
  "groups": [
    {
      "id": "api_connection",
      "label": "API Connection",
      "fields": [
        {"key": "base_url", "label": "Base URL", "type": "text", "value": "https://api.theracingapi.com/v1", "editable": true, "hint": null},
        {"key": "username", "label": "Username", "type": "text", "value": "chimera-prod", "editable": false, "hint": "Managed via Google Secret Manager"},
        {"key": "password", "label": "Password", "type": "secret", "value": "********", "editable": false, "hint": "Managed via Google Secret Manager"}
      ]
    },
    {
      "id": "storage",
      "label": "Storage",
      "fields": [
        {"key": "gcs_bucket", "label": "GCS Bucket", "type": "text", "value": "fsu1e-racingapi-historic-raw", "editable": true, "hint": null},
        {"key": "gcp_project", "label": "GCP Project", "type": "text", "value": "chiops", "editable": false, "hint": null},
        {"key": "region", "label": "Region", "type": "text", "value": "europe-west2", "editable": false, "hint": null}
      ]
    },
    {
      "id": "rate_control",
      "label": "Rate Control",
      "fields": [
        {"key": "max_rps", "label": "Max Requests/Second", "type": "number", "value": 1.0, "editable": true, "hint": null},
        {"key": "max_retries", "label": "Max Retries", "type": "number", "value": 5, "editable": true, "hint": null},
        {"key": "backoff_strategy", "label": "Backoff Strategy", "type": "text", "value": "Exponential (2s, 4s, 8s, 16s)", "editable": false, "hint": null}
      ]
    },
    {
      "id": "backfill",
      "label": "Backfill Configuration",
      "fields": [
        {"key": "start_date", "label": "Start Date", "type": "date", "value": "2014-01-01", "editable": true, "hint": null},
        {"key": "end_date", "label": "End Date", "type": "date", "value": "2026-04-15", "editable": true, "hint": "Defaults to today if blank"},
        {"key": "skip_existing", "label": "Skip Existing", "type": "boolean", "value": true, "editable": true, "hint": "Resume where it left off if interrupted"}
      ]
    }
  ]
}
```

**Supported field types:** `text` | `number` | `boolean` | `secret` | `select` | `date` | `url`

---

#### `PUT /admin/settings`

Accepts a partial update from the portal. Validates input, persists to Firestore, returns full updated settings with applied/rejected breakdown.

**Request:**
```json
{
  "updates": {
    "max_rps": 0.5,
    "max_retries": 3
  }
}
```

**Response:**
```json
{
  "fsu_id": "fsu1e",
  "version": 4,
  "updated_at": "2026-04-15T09:50:00Z",
  "applied": ["max_rps", "max_retries"],
  "rejected": [],
  "settings": { "...full settings object..." }
}
```

**Validation rules:**
- Fields marked `editable: false` are rejected with reason `not_editable`
- `max_rps` must be between 0.1 and 10.0
- `max_retries` must be between 1 and 20
- Rejected fields returned with reason codes
- The FSU is the gatekeeper — the portal never writes to Firestore directly

---

#### `GET /admin/config`

Read-only deployment reference information.

**Response:**
```json
{
  "fsu_id": "fsu1e",
  "repo": "chimeracloud/fsu1e",
  "gcp_project": "chiops",
  "region": "europe-west2",
  "bucket": "fsu1e-racingapi-historic-raw",
  "firestore_collection": "fsu-admin-settings",
  "service_account": "991649774709-compute@developer.gserviceaccount.com",
  "cloud_run_url": "https://fsu1e-991649774709.europe-west2.run.app",
  "deployed_at": "2026-04-15T06:00:00Z"
}
```

---

#### `GET /admin/logs?limit=50&offset=0`

Paginated activity log. Returns the most recent log entries first.

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | Number of entries to return |
| `offset` | int | 0 | Starting offset |

**Response:**
```json
{
  "total": 1853,
  "entries": [
    {
      "timestamp": "2026-04-15T09:42:17Z",
      "action": "FETCH_AND_STORE",
      "detail": "2019-01-14",
      "records": 84,
      "size_bytes": 131072,
      "status": 200,
      "duration_ms": 342
    }
  ]
}
```

**Action types:** `FETCH_AND_STORE` | `FETCH_ERROR`

---

#### `GET /admin/stream`

Server-Sent Events (SSE) endpoint for live portal updates. The portal subscribes on page load and unsubscribes on navigation away.

**Content-Type:** `text/event-stream`

**Event types:**

| Event | Description | Data fields |
|---|---|---|
| `status` | Mode & progress updates | `mode`, `progress`, `current_item` |
| `log` | Individual activity entries as they happen | Same as `/admin/logs` entry |
| `error` | Rate limits, failures, retries | `message`, `timestamp` |
| `health` | Periodic health pings (every 15s as keepalive) | `status`, `uptime_seconds` |

**Example SSE stream:**
```
event: health
data: {"status": "healthy", "uptime_seconds": 120}

event: status
data: {"mode": "BACKFILL", "progress": 41.1, "current_item": "2019-01-14"}

event: log
data: {"timestamp": "2026-04-15T09:42:17Z", "action": "FETCH_AND_STORE", "detail": "2019-01-14", "records": 84, "size_bytes": 131072, "status": 200, "duration_ms": 342}
```

---

## GCS Storage Structure

```
fsu1e-racingapi-historic-raw/
└── results/
    └── {YYYY}/
        └── {MM}/
            └── {DD}/
                └── results.json
```

**Example paths:**
```
results/2014/01/01/results.json
results/2024/06/15/results.json
results/2026/04/15/results.json
```

- Each file contains the raw JSON response from The Racing API for that date
- Days with no racing get an empty marker file (`[]`) to track that they were processed
- This structure allows the backfill to resume by checking for existing files

---

## Settings Persistence (Firestore)

- **Collection:** `fsu-admin-settings`
- **Document ID:** `fsu1e`
- On first startup, if no document exists, default settings are written
- On each `GET /admin/settings`, settings are read from Firestore
- On each `PUT /admin/settings`, settings are validated, then written to Firestore
- Version number increments on each write
- `updated_by` records the source: `portal`, `system`, or `api`
- Settings survive Cloud Run instance restarts and scale-to-zero

---

## The Racing API Integration

| Property | Value |
|---|---|
| **Base URL** | `https://api.theracingapi.com/v1` |
| **Auth** | HTTP Basic Auth |
| **Credentials** | Stored in Google Secret Manager (`racingapi-credentials`) |
| **Key endpoint** | `GET /v1/results` |
| **Query params** | `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD) |
| **Rate limit** | 1 request/second (configurable via settings) |
| **Retry strategy** | Exponential backoff (2s, 4s, 8s, 16s) on 429 or 5xx |
| **Max retries** | 5 (configurable via settings) |
| **Timeout** | 30 seconds per request |

**Response data includes:** meeting details, race info, runners, positions, times, margins, going conditions, weather.

---

## CI/CD Pipeline

1. Develop in VSCode
2. Commit and push to GitHub (`chimeracloud/fsu1e`)
3. Cloud Build trigger fires automatically on push to `main`
4. Cloud Build builds the Docker image from `Dockerfile`
5. Image is deployed to Cloud Run in `europe-west2`

---

## Project File Structure

```
fsu1e/
├── Dockerfile              # Python 3.12-slim, pip install, uvicorn
├── requirements.txt        # Python dependencies
├── CLAUDE.md               # AI assistant context
├── DOCS.md                 # This file
└── app/
    ├── __init__.py
    ├── main.py             # FastAPI app, lifespan, router mounting
    ├── config.py           # Constants, defaults, validation rules
    ├── secrets.py          # Google Secret Manager client
    ├── storage.py          # GCS read/write, gap detection, stats
    ├── firestore_client.py # Firestore settings persistence
    ├── racing_api.py       # Racing API client with retry/backoff
    ├── state.py            # In-memory state, logs, SSE subscribers
    └── routers/
        ├── __init__.py
        ├── api.py          # POST /api/backfill, POST /api/sync, GET /api/stats
        └── admin.py        # All /admin/ endpoints (CHI-ADR-010)
```

---

## Quick Reference

| Action | Command / URL |
|---|---|
| **Health check** | `GET https://fsu1e-991649774709.europe-west2.run.app/admin/health` |
| **Start backfill** | `POST https://fsu1e-991649774709.europe-west2.run.app/api/backfill` |
| **Start daily sync** | `POST https://fsu1e-991649774709.europe-west2.run.app/api/sync` |
| **Check stats** | `GET https://fsu1e-991649774709.europe-west2.run.app/api/stats` |
| **View logs** | `GET https://fsu1e-991649774709.europe-west2.run.app/admin/logs` |
| **GCP Console** | [Cloud Run Revisions](https://console.cloud.google.com/run/detail/europe-west2/fsu1e/revisions?project=chiops) |
