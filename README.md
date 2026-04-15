# FSU1E — Racing API Historic Data Ingest

A Python FastAPI Cloud Run service that downloads the complete historic results database from [The Racing API](https://theracingapi.com) and stores raw JSON in Google Cloud Storage.

## Current State

- **Status:** Deployed and live
- **URL:** https://fsu1e-991649774709.europe-west2.run.app
- **Region:** europe-west2 (London)
- **GCP Project:** chiops
- **Auth:** Public access (no authentication)
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

## TODO — Next Session

- [ ] **Add API key authentication** — All endpoints are currently public. Need to:
  - Generate an API key and store in Google Secret Manager (e.g. `fsu1e-api-key`)
  - Add middleware requiring `X-API-Key` header on `/api/` and `/admin/` endpoints
  - Provide the key to the Chimera portal for authenticated requests
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
