# FSU1E — Racing API Historic Data Ingest

## Overview
Python FastAPI Cloud Run service that downloads historic results from The Racing API and stores raw JSON in GCS.

## Architecture
- Python 3.12 + FastAPI on Cloud Run
- GCP project: `chimera`, region: `europe-west1`
- GCS bucket: `fsu1e-racingapi-historic-raw`
- Firestore collection: `fsu-admin-settings`, document: `fsu1e`
- Credentials from Google Secret Manager (secret: `racingapi-credentials`)
- GitHub repo: `chimeracloud/fsu1e`

## Endpoints
- `POST /api/backfill` — full historic download (background task)
- `POST /api/sync` — daily incremental sync
- `GET /api/stats` — bucket summary stats
- `GET /admin/health` — health check (CHI-ADR-010)
- `GET /admin/status` — operational state
- `GET /admin/settings` — structured settings form
- `PUT /admin/settings` — update settings
- `GET /admin/config` — deployment reference
- `GET /admin/logs` — paginated activity log
- `GET /admin/stream` — SSE live updates

## CI/CD
Build in VSCode, commit & push to GitHub. Deploy to Cloud Run and Pages from GitHub.
