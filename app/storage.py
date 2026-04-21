import json
from datetime import date
from google.cloud import storage as gcs
from app.config import GCS_BUCKET


def _client() -> gcs.Client:
    return gcs.Client()


def _bucket():
    return _client().bucket(GCS_BUCKET)


def blob_path(prefix: str, d: date) -> str:
    return f"{prefix}/{d.strftime('%Y/%m/%d')}/results.json"


def file_exists(prefix: str, d: date) -> bool:
    return _bucket().blob(blob_path(prefix, d)).exists()


def save_json(prefix: str, d: date, data: dict | list) -> int:
    blob = _bucket().blob(blob_path(prefix, d))
    payload = json.dumps(data, default=str)
    blob.upload_from_string(payload, content_type="application/json")
    return len(payload)


def save_empty_marker(prefix: str, d: date) -> None:
    blob = _bucket().blob(blob_path(prefix, d))
    blob.upload_from_string("[]", content_type="application/json")


def list_result_dates(prefix: str = "results") -> list[str]:
    blobs = _client().list_blobs(GCS_BUCKET, prefix=f"{prefix}/")
    dates = []
    for b in blobs:
        parts = b.name.split("/")
        if len(parts) >= 4:
            try:
                dates.append(f"{parts[1]}-{parts[2]}-{parts[3]}")
            except (IndexError, ValueError):
                pass
    return sorted(dates)


def get_latest_date(prefix: str = "results") -> date | None:
    dates = list_result_dates(prefix)
    if not dates:
        return None
    return date.fromisoformat(dates[-1])


def count_files(prefix: str = "results") -> int:
    blobs = _client().list_blobs(GCS_BUCKET, prefix=f"{prefix}/")
    return sum(1 for _ in blobs)


def get_date_range(prefix: str = "results") -> tuple[str | None, str | None]:
    dates = list_result_dates(prefix)
    if not dates:
        return None, None
    return dates[0], dates[-1]


def save_blob(blob_name: str, data: dict | list) -> int:
    """Save data to an arbitrary GCS path (not date-keyed)."""
    blob = _bucket().blob(blob_name)
    payload = json.dumps(data, default=str)
    blob.upload_from_string(payload, content_type="application/json")
    return len(payload)


def find_gaps(prefix: str = "results") -> list[str]:
    dates = list_result_dates(prefix)
    if len(dates) < 2:
        return []
    gaps = []
    from datetime import timedelta
    prev = date.fromisoformat(dates[0])
    for d_str in dates[1:]:
        curr = date.fromisoformat(d_str)
        diff = (curr - prev).days
        if diff > 1:
            gap_date = prev + timedelta(days=1)
            while gap_date < curr:
                gaps.append(gap_date.isoformat())
                gap_date += timedelta(days=1)
        prev = curr
    return gaps
