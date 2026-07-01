import os
from datetime import UTC, datetime, timedelta

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "fsstudents")
FIRESTORE_DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "fsstudents")
DEFAULT_TTL_DAYS = int(os.getenv("FIRESTORE_LOG_TTL_DAYS", "30"))


def get_firestore_client():
    if not firestore:
        raise RuntimeError("google-cloud-firestore paketi kurulu degil.")
    return firestore.Client(project=GCP_PROJECT, database=FIRESTORE_DATABASE_ID)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ttl_timestamp(days: int = DEFAULT_TTL_DAYS):
    return datetime.now(UTC) + timedelta(days=days)


def add_document(collection: str, payload: dict, doc_id: str | None = None):
    db = get_firestore_client()
    enriched = {
        **payload,
        "created_at": payload.get("created_at") or utc_now_iso(),
        "expires_at": payload.get("expires_at") or ttl_timestamp(),
    }
    if doc_id:
        ref = db.collection(collection).document(doc_id)
        ref.set(enriched, merge=True)
        return ref.id
    _, ref = db.collection(collection).add(enriched)
    return ref.id


def log_event(event_type: str, payload: dict, source: str = "unknown", severity: str = "info") -> str | None:
    try:
        return add_document("event_logs", {
            "event_type": event_type,
            "source": source,
            "severity": severity,
            "payload": payload,
        })
    except Exception as exc:
        print(f"[FIRESTORE] event_logs yazilamadi: {exc}")
        return None


def log_critical_event(event_type: str, payload: dict, source: str = "unknown") -> str | None:
    try:
        return add_document("critical_events", {
            "event_type": event_type,
            "source": source,
            "severity": "critical",
            "payload": payload,
            "requires_human_review": True,
        })
    except Exception as exc:
        print(f"[FIRESTORE] critical_events yazilamadi: {exc}")
        return None
