# FSU1E — Racing API Historic Data Ingest

A Python FastAPI Cloud Run service that downloads the complete historic results database from [The Racing API](https://theracingapi.com) and stores raw JSON in Google Cloud Storage.

## Current State

- **Status:** Deployed and live
- **URL:** https://fsu1e-991649774709.europe-west2.run.app
- **Region:** europe-west2 (London)
- **GCP Project:** chiops
- **Auth:** API key required (`X-API-Key` header) — key in Secret Manager as `fsu1e-api-key`
- **CI/CD:** Auto-deploys via Cloud Build on push to `main`

## Endpoints

### Operational (`/api/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/backfill` | Full historic download (background task) |
| POST | `/api/sync` | Daily incremental sync |
| GET | `/api/stats` | Bucket summary stats |

### Admin (`/admin/`) — CHI-ADR-010
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/health` | Health check |
| GET | `/admin/status` | Operational state & progress |
| GET | `/admin/settings` | Structured settings form |
| PUT | `/admin/settings` | Update settings |
| GET | `/admin/config` | Deployment reference |
| GET | `/admin/logs` | Paginated activity log |
| GET | `/admin/stream` | SSE live updates |

## Documentation

See [DOCS.md](DOCS.md) for comprehensive endpoint reference with request/response examples, architecture diagram, GCS storage structure, and deployment details.

## Authentication

All endpoints require an `X-API-Key` header except `GET /` and `GET /admin/health`.

```
X-API-Key: <key from Secret Manager: fsu1e-api-key>
```

- Key stored in GCP Secret Manager as `fsu1e-api-key` (version 1)
- Service account `991649774709-compute@developer.gserviceaccount.com` has `secretAccessor` role
- Key is fetched at runtime and cached in memory

## TODO — Next Session

- [ ] **Explore additional Racing API endpoints** — racecards, horses, courses, jockeys, trainers (if available on Pro Plan)

## Tech Stack

- Python 3.12 + FastAPI
- Google Cloud Run
- Google Cloud Storage (raw JSON)
- Google Cloud Firestore (settings persistence)
- Google Secret Manager (API credentials)
- SSE via sse-starlette

## Development

```bash
# Local dev
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Deploy
git push  # Cloud Build auto-deploys to Cloud Run
```
