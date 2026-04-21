import time
import logging
import requests
from requests.auth import HTTPBasicAuth
from app.config import RACING_API_BASE_URL, DEFAULT_MAX_RETRIES, BACKOFF_BASE

logger = logging.getLogger(__name__)


def probe_endpoint(
    username: str,
    password: str,
    path: str,
    params: dict | None = None,
    base_url: str = RACING_API_BASE_URL,
) -> tuple[bool, any]:
    """Try an endpoint once. Returns (available, data_or_error_detail)."""
    url = f"{base_url}/{path.lstrip('/')}"
    try:
        response = requests.get(
            url, auth=HTTPBasicAuth(username, password),
            params=params or {}, timeout=10,
        )
        if response.status_code == 200:
            return True, response.json()
        return False, {"status_code": response.status_code}
    except Exception as e:
        return False, {"error": str(e)}


def fetch_static(
    username: str,
    password: str,
    path: str,
    params: dict | None = None,
    base_url: str = RACING_API_BASE_URL,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict | list | None:
    """Fetch any endpoint with retry/backoff. Returns None if 403/404 (not on plan)."""
    url = f"{base_url}/{path.lstrip('/')}"
    auth = HTTPBasicAuth(username, password)
    params = params or {}

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, auth=auth, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()

            if response.status_code in (403, 404):
                return None

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Got %d for %s, retrying in %ds (attempt %d/%d)",
                        response.status_code, path, wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    continue
                raise Exception(f"Max retries exceeded for {path}: HTTP {response.status_code}")

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait = BACKOFF_BASE ** (attempt + 1)
                time.sleep(wait)
                continue
            raise

    return None


def fetch_results(
    username: str,
    password: str,
    date_str: str,
    base_url: str = RACING_API_BASE_URL,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict | list | None:
    url = f"{base_url}/results"
    params = {"start_date": date_str, "end_date": date_str}
    auth = HTTPBasicAuth(username, password)

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, auth=auth, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Got %d for %s, retrying in %ds (attempt %d/%d)",
                        response.status_code, date_str, wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    continue
                else:
                    logger.error("Max retries exceeded for %s (last status: %d)", date_str, response.status_code)
                    raise Exception(f"Max retries exceeded for {date_str}: HTTP {response.status_code}")

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait = BACKOFF_BASE ** (attempt + 1)
                logger.warning("Request error for %s: %s, retrying in %ds", date_str, e, wait)
                time.sleep(wait)
                continue
            raise

    return None
