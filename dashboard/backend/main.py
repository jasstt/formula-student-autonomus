from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import asyncio
from datetime import datetime
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None
try:
    from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client, utc_now_iso
except Exception:
    GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "fsstudents")
    get_firestore_client = None
    utc_now_iso = None

app = FastAPI(title="Formula Future - Human Approval Gate", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ID = GCP_PROJECT
DEPLOYMENT_TOPIC_ID = os.getenv("DEPLOYMENT_TOPIC_ID", "deployment-topic")
REPORTS_PATH = os.getenv("DASHBOARD_REPORTS_PATH", os.path.join("data", "dashboard", "reports.json"))
REPORTS_COLLECTION = os.getenv("DASHBOARD_REPORTS_COLLECTION", "dashboard_reports")

def _firestore_db():
    if not get_firestore_client:
        return None
    try:
        return get_firestore_client()
    except Exception as exc:
        print(f"[FIRESTORE] Dashboard Firestore kullanilamiyor: {exc}")
        return None

def _load_reports() -> list[dict]:
    db = _firestore_db()
    if db:
        try:
            docs = db.collection(REPORTS_COLLECTION).order_by("created_at").limit(100).stream()
            reports = []
            for doc in docs:
                item = doc.to_dict()
                item["id"] = doc.id
                reports.append(item)
            return reports
        except Exception as exc:
            print(f"[FIRESTORE] Dashboard raporlari okunamadi, JSON fallback: {exc}")

    if not os.path.exists(REPORTS_PATH):
        return []
    with open(REPORTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_reports(reports: list[dict]) -> None:
    os.makedirs(os.path.dirname(REPORTS_PATH), exist_ok=True)
    with open(REPORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

def _save_report(report: dict) -> dict:
    db = _firestore_db()
    if db:
        doc_id = report["id"]
        db.collection(REPORTS_COLLECTION).document(doc_id).set(report, merge=True)
        return report
    reports = _load_reports()
    reports = [r for r in reports if r.get("id") != report["id"]]
    reports.append(report)
    _save_reports(reports)
    return report

def _publish_deployment(report: dict) -> bool:
    if not pubsub_v1:
        print("[PUBSUB] google-cloud-pubsub kurulu degil; deployment mesaji gonderilmedi.")
        return False
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, DEPLOYMENT_TOPIC_ID)
        future = publisher.publish(topic_path, json.dumps(report, ensure_ascii=False).encode("utf-8"))
        print(f"[PUBSUB] Deployment trigger yayinlandi: {future.result()}")
        return True
    except Exception as exc:
        print(f"[PUBSUB] Deployment trigger yayinlanamadi: {exc}")
        return False

class ApprovalAction(BaseModel):
    user_id: str
    comment: str = ""

class ReportCreate(BaseModel):
    title: str
    source: str
    impact_score: float = 0.0
    status: str = "PENDING"
    payload: dict = {}

@app.get("/reports")
def get_reports(limit: int = 10):
    """Son 10 analiz raporunu getirir."""
    reports_db = _load_reports()
    return sorted(reports_db, key=lambda x: x["created_at"], reverse=True)[:limit]

@app.post("/reports")
def create_report(report: ReportCreate):
    item = report.dict()
    item["id"] = f"rep_{int(datetime.utcnow().timestamp() * 1000)}"
    item["created_at"] = utc_now_iso() if utc_now_iso else datetime.utcnow().isoformat()
    _save_report(item)
    return item

@app.post("/approve/{report_id}")
def approve_report(report_id: str, action: ApprovalAction):
    """Raporu onaylar ve Deployment Agent'ı (Pub/Sub üzerinden) tetikler."""
    reports_db = _load_reports()
    for rep in reports_db:
        if rep["id"] == report_id:
            rep["status"] = "APPROVED"
            rep["approved_by"] = action.user_id
            rep["approved_at"] = utc_now_iso() if utc_now_iso else datetime.utcnow().isoformat()
            rep["deployment_triggered"] = _publish_deployment(rep)
            _save_report(rep)
            
            return {"message": "Onaylandı. Deployment başlatılıyor.", "report": rep}
            
    raise HTTPException(status_code=404, detail="Rapor bulunamadı")

@app.post("/reject/{report_id}")
def reject_report(report_id: str, action: ApprovalAction):
    """Raporu reddeder ve arşivler."""
    reports_db = _load_reports()
    for rep in reports_db:
        if rep["id"] == report_id:
            rep["status"] = "REJECTED"
            rep["rejected_by"] = action.user_id
            rep["rejected_at"] = utc_now_iso() if utc_now_iso else datetime.utcnow().isoformat()
            rep["reason"] = action.comment
            _save_report(rep)
            
            return {"message": "Reddedildi ve arşivlendi.", "report": rep}
            
    raise HTTPException(status_code=404, detail="Rapor bulunamadı")

@app.get("/digital-twin/status")
def get_digital_twin_status():
    """Son simülasyon metriklerini döner."""
    reports_db = _load_reports()
    latest = reports_db[-1] if reports_db else {}
    return {
        "status": "WAITING_FOR_REAL_SIMULATION",
        "last_run": latest.get("created_at"),
        "metrics": latest.get("payload", {}).get("simulation_metrics", {})
    }

# WebSocket for live telemetry
active_connections = []

@app.websocket("/telemetry/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            reports = _load_reports()
            await websocket.send_json({
                "timestamp": datetime.utcnow().isoformat(),
                "source": "dashboard_reports_store",
                "latest_report": reports[-1] if reports else None,
            })
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        active_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
