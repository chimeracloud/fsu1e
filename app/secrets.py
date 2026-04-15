import json
from google.cloud import secretmanager
from app.config import GCP_PROJECT, SECRET_NAME


_cached_credentials: dict | None = None


def get_racing_api_credentials() -> tuple[str, str]:
    global _cached_credentials
    if _cached_credentials:
        return _cached_credentials["username"], _cached_credentials["password"]

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    payload = json.loads(response.payload.data.decode("utf-8"))
    _cached_credentials = payload
    return payload["username"], payload["password"]
