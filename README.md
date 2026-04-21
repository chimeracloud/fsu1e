# FSU1E — Racing API Historic Data Ingest

A Python FastAPI Cloud Run service that downloads the complete historic results database from [The Racing API](https://theracingapi.com) and stores raw JSON in Google Cloud Storage.

## Live Service

| Property | Value |
|---|---|
| **URL** | https://fsu1e-991649774709.europe-west2.run.app |
| **GCP Project** | `chiops` |
| **Region** | `europe-west2` (London) |
| **GCS Bucket** | `fsu1e-racingapi-historic-raw` |
| **Firestore** | `fsu-admin-settings` / doc `fsu1e` |
| **Secret Manager** | `racingapi-credentials`, `fsu1e-api-key` |
| **Service Account** | `991649774709-compute@developer.gserviceaccount.com` |
| **GitHub Repo** | `chimeracloud/fsu1e` |

---

## Authentication

All endpoints require an `X-API-Key` header **except** `GET /` and `GET /admin/health`.

```
X-API-Key: <key>
```

The key is stored in Secret Manager as `fsu1e-api-key`. Fetch it with:

```bash
gcloud secrets versions access latest --secret=fsu1e-api-key --project=chiops
```

---

## Endpoints

### Operational (`/api/`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/backfill` | Full historic download (background task) |
| `POST` | `/api/sync` | Daily incremental sync (background task) |
| `GET` | `/api/stats` | Bucket summary: total files, date range, gaps |
| `POST` | `/api/probe` | Check which additional API endpoints are on your plan |

#### `POST /api/backfill`

Query params:

| Param | Default | Description |
|---|---|---|
| `start_date` | `2014-01-01` | First date to fetch |
| `end_date` | today | Last date to fetch |
| `extended` | `false` | Also download racecards, courses, jockeys, trainers in parallel |

- Runs day-by-day in a background task, returns immediately with a job ID
- Skips dates already in GCS by default (`skip_existing` setting)
- Fully resumable — safe to re-run after interruption
- When `extended=true`, spawns parallel threads for racecards (date-by-date) and static data (courses, jockeys, trainers fetched once each)

```bash
# Basic results-only backfill
curl -X POST "https://fsu1e-991649774709.europe-west2.run.app/api/backfill" \
  -H "X-API-Key: YOUR_KEY"

# Full backfill including all additional endpoints
curl -X POST "https://fsu1e-991649774709.europe-west2.run.app/api/backfill?extended=true" \
  -H "X-API-Key: YOUR_KEY"
```

#### `POST /api/sync`

Finds the latest date in GCS and fetches everything from `latest + 1` to today.

```bash
curl -X POST "https://fsu1e-991649774709.europe-west2.run.app/api/sync" \
  -H "X-API-Key: YOUR_KEY"
```

#### `POST /api/probe`

Tests which additional Racing API endpoints are accessible on your plan (racecards, courses, jockeys, trainers). Run this before using `extended=true` on backfill.

```bash
curl -X POST "https://fsu1e-991649774709.europe-west2.run.app/api/probe" \
  -H "X-API-Key: YOUR_KEY"
```

Example response:
```json
{
  "probed_at": "2026-04-21T10:00:00Z",
  "endpoints": {
    "racecards": {"available": true, "record_count": 8},
    "courses":   {"available": false, "detail": {"status_code": 403}},
    "jockeys":   {"available": false, "detail": {"status_code": 403}},
    "trainers":  {"available": false, "detail": {"status_code": 403}}
  }
}
```

---

### Admin (`/admin/`) — CHI-ADR-010

These endpoints implement the Chimera Admin Endpoint Contract, consumed by the portal at chimerasportstrading.com.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/health` | Health status — **no auth required** |
| `GET` | `/admin/status` | Mode, progress, ETA, error counts |
| `GET` | `/admin/settings` | Structured settings form for portal rendering |
| `PUT` | `/admin/settings` | Update editable settings (persisted to Firestore) |
| `GET` | `/admin/config` | Read-only deployment reference |
| `GET` | `/admin/logs` | Paginated activity log (`?limit=50&offset=0`) |
| `GET` | `/admin/stream` | SSE live updates (status, log, error, health) |

#### Settings — editable fields

| Key | Type | Default | Bounds |
|---|---|---|---|
| `base_url` | text | `https://api.theracingapi.com/v1` | — |
| `gcs_bucket` | text | `fsu1e-racingapi-historic-raw` | — |
| `max_rps` | number | `1.0` | 0.1 – 10.0 |
| `max_retries` | number | `5` | 1 – 20 |
| `start_date` | date | `2014-01-01` | — |
| `end_date` | date | _(today)_ | — |
| `skip_existing` | boolean | `true` | — |

```bash
curl -X PUT "https://fsu1e-991649774709.europe-west2.run.app/admin/settings" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"updates": {"max_rps": 0.5, "max_retries": 3}}'
```

---

## GCS Storage Structure

```
fsu1e-racingapi-historic-raw/
├── results/
│   └── {YYYY}/{MM}/{DD}/results.json      # Racing results (day-by-day)
├── racecards/
│   └── {YYYY}/{MM}/{DD}/results.json      # Racecards if on Pro Plan
├── courses/
│   └── data.json                           # Static — fetched once
├── jockeys/
│   └── data.json                           # Static — fetched once
└── trainers/
    └── data.json                           # Static — fetched once
```

Days with no racing get an empty marker file (`[]`) so they're not re-fetched on resume.

---

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Chimera     │────▶│  FSU1E           │────▶│  The Racing API  │
│  Portal      │◀────│  (Cloud Run)     │◀────│  theracingapi.com│
│              │ SSE │  FastAPI 3.12    │     └──────────────────┘
└──────────────┘     │                  │
                     │  Background      │────▶ GCS Bucket
                     │  Tasks +         │
                     │  Threads         │────▶ Firestore (settings)
                     └──────────────────┘
                              │
                              └──────────────▶ Secret Manager (credentials)
```

### Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Framework | FastAPI + Uvicorn |
| Deployment | Google Cloud Run |
| Storage | Google Cloud Storage |
| Settings | Google Cloud Firestore |
| Secrets | Google Secret Manager |
| SSE | sse-starlette |
| HTTP client | requests |

---

## CI/CD

1. Develop in VSCode
2. Commit and push to `main` on `chimeracloud/fsu1e`
3. Cloud Build trigger fires automatically
4. Docker image built and deployed to Cloud Run `europe-west2`

No manual deploy steps required.

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires GCP credentials with access to Secret Manager + Firestore)
uvicorn app.main:app --reload --port 8080
```

For local GCP auth:
```bash
gcloud auth application-default login
```

---

## Project Structure

```
fsu1e/
├── Dockerfile
├── requirements.txt
├── CLAUDE.md
├── README.md
├── docs/
│   └── DOCS.md                    # Full endpoint reference
└── app/
    ├── main.py                    # FastAPI app, lifespan, middleware
    ├── config.py                  # Constants, defaults, validation rules
    ├── auth.py                    # API key middleware (Secret Manager)
    ├── secrets.py                 # Racing API credentials (Secret Manager)
    ├── storage.py                 # GCS read/write, gap detection, stats
    ├── firestore_client.py        # Firestore settings persistence
    ├── racing_api.py              # Racing API client (fetch, probe, retry/backoff)
    ├── state.py                   # In-memory state, logs, SSE subscribers
    └── routers/
        ├── api.py                 # /api/* endpoints + backfill logic
        └── admin.py               # /admin/* endpoints (CHI-ADR-010)
```

---

## Quick Reference

```bash
# Get your API key
gcloud secrets versions access latest --secret=fsu1e-api-key --project=chiops

# Health check (no auth)
curl https://fsu1e-991649774709.europe-west2.run.app/admin/health

# Probe additional endpoints
curl -X POST https://fsu1e-991649774709.europe-west2.run.app/api/probe \
  -H "X-API-Key: YOUR_KEY"

# Start full backfill (results only)
curl -X POST https://fsu1e-991649774709.europe-west2.run.app/api/backfill \
  -H "X-API-Key: YOUR_KEY"

# Start full backfill (everything in parallel)
curl -X POST "https://fsu1e-991649774709.europe-west2.run.app/api/backfill?extended=true" \
  -H "X-API-Key: YOUR_KEY"

# Check progress
curl https://fsu1e-991649774709.europe-west2.run.app/admin/status \
  -H "X-API-Key: YOUR_KEY"

# View recent activity log
curl https://fsu1e-991649774709.europe-west2.run.app/admin/logs \
  -H "X-API-Key: YOUR_KEY"

# Daily sync
curl -X POST https://fsu1e-991649774709.europe-west2.run.app/api/sync \
  -H "X-API-Key: YOUR_KEY"
```
