from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import json
import asyncio
from datetime import datetime

app = FastAPI(title="Formula Future - Human Approval Gate", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock in-memory DB for reports
reports_db = [
    {
        "id": "rep_1001",
        "title": "FSAE Kural Değişikliği: Enerji Limiti",
        "source": "NotebookLM_Rules",
        "impact_score": 8.5,
        "status": "PENDING",
        "created_at": "2026-06-25T10:00:00Z"
    },
    {
        "id": "rep_1002",
        "title": "Yeni YOLOv9 Mimarisi Optimizasyonu",
        "source": "arXiv",
        "impact_score": 6.2,
        "status": "PENDING",
        "created_at": "2026-06-26T08:15:00Z"
    }
]

class ApprovalAction(BaseModel):
    user_id: str
    comment: str = ""

@app.get("/reports")
def get_reports(limit: int = 10):
    """Son 10 analiz raporunu getirir."""
    return sorted(reports_db, key=lambda x: x["created_at"], reverse=True)[:limit]

@app.post("/approve/{report_id}")
def approve_report(report_id: str, action: ApprovalAction):
    """Raporu onaylar ve Deployment Agent'ı (Pub/Sub üzerinden) tetikler."""
    for rep in reports_db:
        if rep["id"] == report_id:
            rep["status"] = "APPROVED"
            rep["approved_by"] = action.user_id
            rep["approved_at"] = datetime.utcnow().isoformat()
            
            # Burada Deployment Agent Topic'ine mesaj atılır
            # publish_to_deployment_topic(report_id)
            
            return {"message": "Onaylandı. Deployment başlatılıyor.", "report": rep}
            
    raise HTTPException(status_code=404, detail="Rapor bulunamadı")

@app.post("/reject/{report_id}")
def reject_report(report_id: str, action: ApprovalAction):
    """Raporu reddeder ve arşivler."""
    for rep in reports_db:
        if rep["id"] == report_id:
            rep["status"] = "REJECTED"
            rep["rejected_by"] = action.user_id
            rep["rejected_at"] = datetime.utcnow().isoformat()
            rep["reason"] = action.comment
            
            return {"message": "Reddedildi ve arşivlendi.", "report": rep}
            
    raise HTTPException(status_code=404, detail="Rapor bulunamadı")

@app.get("/digital-twin/status")
def get_digital_twin_status():
    """Son simülasyon metriklerini döner."""
    return {
        "status": "IDLE",
        "last_run": "2026-06-26T09:00:00Z",
        "metrics": {
            "estimated_lap_time_s": random.uniform(72.0, 75.5),
            "max_lateral_g": random.uniform(1.2, 1.6),
            "energy_consumption_kwh": random.uniform(0.8, 1.2),
            "cone_hit_count": random.randint(0, 3)
        }
    }

# WebSocket for live telemetry
active_connections = []

@app.websocket("/telemetry/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Gerçekte Pub/Sub'dan okuyup buraya pushlamak gerekir.
            # Burada canlı stokastik veri üretiyoruz.
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "speed_kph": round(random.uniform(40, 110), 1),
                "motor_temp_c": round(random.uniform(50, 90), 1),
                "h2_tank_pressure": round(random.uniform(200, 350), 1)
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.5) # 500ms update rate
    except WebSocketDisconnect:
        active_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
