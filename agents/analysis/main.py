import json
import urllib.request
from datetime import datetime
import os
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None
from agents.integrations.gcp_clients import GCP_PROJECT

PROJECT_ID = GCP_PROJECT
SUBSCRIBE_TOPIC_ID = "agent-results-topic"
DASHBOARD_URL = os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8000")

class AnalysisAgent:
    def __init__(self):
        self.rules_base = {
            "energy_efficiency": "High",
            "lap_time_priority": 0.7,  # 0.0 - 1.0 (1.0 = Max agresiflik)
            "safety_margin": 0.8
        }
        
    def analyze_arxiv_data(self, data, importance_score):
        """arXiv verisini işler."""
        if importance_score > 0.8:
            # Önemli bir makale, yeni bir A/B testi konfigürasyonu üret
            return self.generate_ab_test_config("algorithm_update", data["title"])
        return {"action": "monitor", "reason": "Low impact score"}

    def analyze_telemetry_anomaly(self, data, urgency_score):
        """Telemetri anomalisini işler."""
        if urgency_score > 8.0:
            # Acil durum, konfigürasyonu güvenli moda al
            return self.generate_ab_test_config("safety_mode", "High telemetry anomaly detected")
        return {"action": "monitor", "reason": "Anomaly within acceptable threshold"}

    def generate_ab_test_config(self, reason, context):
        """Rule-base ile tekrarlanabilir yeni bir konfigürasyon önerir."""
        if reason == "safety_mode":
            speed_modifier = 0.70
            power_limit_kw = 45.0
            pid_p = 0.8
        elif reason == "algorithm_update":
            speed_modifier = 1.05
            power_limit_kw = round(80.0 * self.rules_base["lap_time_priority"], 2)
            pid_p = 1.1
        else:
            speed_modifier = 1.0
            power_limit_kw = round(72.0 * self.rules_base["lap_time_priority"], 2)
            pid_p = 1.0

        config = {
            "action": "digital_twin_test_required",
            "context": context,
            "proposed_parameters": {
                "max_speed_kph": round(120.0 * speed_modifier, 1),
                "power_limit_kw": power_limit_kw,
                "pid_p": pid_p
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        return config

    def process_message(self, message):
        """Gelen Pub/Sub mesajını işler."""
        try:
            payload = json.loads(message.data.decode("utf-8"))
            source = payload.get("source")
            
            result = None
            if source == "arxiv":
                result = self.analyze_arxiv_data(payload.get("data", {}), payload.get("importance_score", 0))
            elif source == "telemetry_stream":
                result = self.analyze_telemetry_anomaly(payload.get("data", {}), payload.get("urgency_score", 0))
            
            if result and result.get("action") == "digital_twin_test_required":
                print(f"[ANALYSIS] Yeni konfigürasyon üretildi: {result}")
                self.forward_to_dashboard(result)
                
            message.ack()
        except Exception as e:
            print(f"Mesaj islenirken hata: {e}")
            message.nack()
            
    def forward_to_dashboard(self, config):
        """Dashboard onay kuyruğuna gerçek HTTP isteğiyle gönderir."""
        payload = json.dumps({
            "title": f"Analysis proposal: {config['context'][:80]}",
            "source": "analysis_agent",
            "impact_score": 9.0 if config.get("proposed_parameters", {}).get("max_speed_kph", 0) < 90 else 7.0,
            "status": "PENDING",
            "payload": config,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{DASHBOARD_URL.rstrip('/')}/reports",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"[DASHBOARD] Proposal iletildi: HTTP {resp.status}")
                return True
        except Exception as exc:
            print(f"[DASHBOARD] Proposal iletilemedi: {exc}")
            return False

def start_subscriber():
    if not pubsub_v1:
        raise RuntimeError("google-cloud-pubsub kurulu degil.")
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIBE_TOPIC_ID + "-sub")
    
    agent = AnalysisAgent()
    print("Analysis Agent dinlemeye basladi...")
    
    future = subscriber.subscribe(subscription_path, callback=agent.process_message)
    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()

if __name__ == "__main__":
    start_subscriber()
