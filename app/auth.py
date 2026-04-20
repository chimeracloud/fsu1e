import json
import secrets
from functools import lru_cache

from fastapi import Request
from fastapi.responses import JSONResponse
from google.cloud import secretmanager
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import GCP_PROJECT

API_KEY_SECRET_NAME = "fsu1e-api-key"

# Paths that don't require authentication
PUBLIC_PATHS = {"/", "/admin/health"}


@lru_cache(maxsize=1)
def _get_api_key() -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{GCP_PROJECT}/secrets/{API_KEY_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8").strip()


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Missing X-API-Key header"},
            )

        try:
            expected = _get_api_key()
        except Exception:
            # If Secret Manager is unreachable, fail open in dev but log it
            return JSONResponse(
                status_code=503,
                content={"error": "Unable to verify API key"},
            )

        if not secrets.compare_digest(api_key, expected):
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid API key"},
            )

        return await call_next(request)
