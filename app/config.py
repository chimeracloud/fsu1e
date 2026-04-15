FSU_ID = "fsu1e"
FSU_NAME = "Racing API Historic Ingest"
FSU_VERSION = "1.0.0"

GCP_PROJECT = "chimera"
GCP_REGION = "europe-west1"
GCS_BUCKET = "fsu1e-racingapi-historic-raw"
SECRET_NAME = "racingapi-credentials"

FIRESTORE_COLLECTION = "fsu-admin-settings"
FIRESTORE_DOCUMENT = "fsu1e"

RACING_API_BASE_URL = "https://api.theracingapi.com/v1"
BACKFILL_START_DATE = "2014-01-01"

DEFAULT_MAX_RPS = 1.0
DEFAULT_MAX_RETRIES = 5
BACKOFF_BASE = 2

SERVICE_ACCOUNT = "fsu1e@chimera.iam.gserviceaccount.com"

DEFAULT_SETTINGS = {
    "base_url": RACING_API_BASE_URL,
    "gcs_bucket": GCS_BUCKET,
    "gcp_project": GCP_PROJECT,
    "region": GCP_REGION,
    "max_rps": DEFAULT_MAX_RPS,
    "max_retries": DEFAULT_MAX_RETRIES,
    "start_date": BACKFILL_START_DATE,
    "end_date": "",
    "skip_existing": True,
}

EDITABLE_FIELDS = {"base_url", "gcs_bucket", "max_rps", "max_retries", "start_date", "end_date", "skip_existing"}

VALIDATION_RULES = {
    "max_rps": {"min": 0.1, "max": 10.0},
    "max_retries": {"min": 1, "max": 20},
}
