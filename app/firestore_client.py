from datetime import datetime, timezone
from google.cloud import firestore
from app.config import FIRESTORE_COLLECTION, FIRESTORE_DOCUMENT, DEFAULT_SETTINGS, FSU_ID


def _client() -> firestore.Client:
    return firestore.Client()


def _doc_ref():
    return _client().collection(FIRESTORE_COLLECTION).document(FIRESTORE_DOCUMENT)


def load_settings() -> dict:
    doc = _doc_ref().get()
    if doc.exists:
        return doc.to_dict()
    defaults = {
        "fsu_id": FSU_ID,
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "system",
        **DEFAULT_SETTINGS,
    }
    _doc_ref().set(defaults)
    return defaults


def save_settings(updates: dict, updated_by: str = "portal") -> dict:
    current = load_settings()
    current.update(updates)
    current["version"] = current.get("version", 0) + 1
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    current["updated_by"] = updated_by
    _doc_ref().set(current)
    return current
