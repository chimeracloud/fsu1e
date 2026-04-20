# Claude Code Prompt — Portal: FSU1E API Key Integration

## Context

We have a backend microservice called **FSU1E** (Racing API Historic Data Ingest) deployed on Google Cloud Run. The Chimera portal at chimerasportstrading.com makes HTTP requests to FSU1E to display monitoring dashboards, settings, and live status updates.

FSU1E has just had API key authentication added. All requests from the portal to FSU1E must now include an `X-API-Key` header, otherwise they will receive a `401 Unauthorized` response.

## FSU1E Details

- **Base URL:** `https://fsu1e-991649774709.europe-west2.run.app`
- **Auth header:** `X-API-Key: <key>`
- **Key location:** The key should be stored as an environment variable or secret in the portal — do NOT hardcode it. The key value itself will be provided separately and stored securely.
- **Public endpoints (no key needed):**
  - `GET /` — root
  - `GET /admin/health` — health check

## Endpoints the Portal Calls

### Admin endpoints (all require X-API-Key)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/health` | Health status — PUBLIC, no key needed |
| GET | `/admin/status` | Operational mode, progress, error counts |
| GET | `/admin/settings` | Structured settings form definition |
| PUT | `/admin/settings` | Update settings (partial update) |
| GET | `/admin/config` | Deployment reference info |
| GET | `/admin/logs?limit=50&offset=0` | Paginated activity log |
| GET | `/admin/stream` | SSE live updates (event-stream) |

### Operational endpoints (all require X-API-Key)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/backfill` | Trigger full historic download |
| POST | `/api/sync` | Trigger daily incremental sync |
| GET | `/api/stats` | Bucket stats and gap report |

## What To Do

1. **Find all places in the portal codebase that make HTTP requests to the FSU1E base URL** (`https://fsu1e-991649774709.europe-west2.run.app`)

2. **Add the `X-API-Key` header to every request**, reading the key from an environment variable (suggest `FSU1E_API_KEY`)

3. **Do not add the key to `GET /admin/health` requests** — that endpoint is intentionally public and used for uptime monitoring

4. **For the SSE stream (`GET /admin/stream`)**, ensure the key is passed. If using `EventSource` in the browser, native `EventSource` does not support custom headers — if that's the case, switch to `fetch` with a `ReadableStream` or use a library like `@microsoft/fetch-event-source` that supports headers

5. **Store the key securely:**
   - If the portal is a Next.js / server-rendered app: store in `.env.local` as `FSU1E_API_KEY` and access server-side only, never expose to the browser
   - If calls are made client-side: route them through a portal API proxy endpoint that adds the key server-side

6. **Handle auth errors gracefully** — if FSU1E returns `401` or `403`, display a meaningful error in the portal UI rather than a silent failure

## Settings PUT request format (reminder)

```json
{
  "updates": {
    "max_rps": 0.5,
    "max_retries": 3
  }
}
```

Only editable fields will be accepted. Non-editable fields will be returned in the `rejected` array.

## SSE stream event types

```
event: health   → { status, uptime_seconds }
event: status   → { mode, progress, current_item }
event: log      → { timestamp, action, detail, records, size_bytes, status, duration_ms }
event: error    → { message, timestamp }
```
