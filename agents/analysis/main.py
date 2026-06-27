import json
import random
from datetime import datetime
from google.cloud import pubsub_v1
import os

PROJECT_ID = "YOUR_PROJECT_ID"
SUBSCRIBE_TOPIC_ID = "agent-results-topic"
DASHBOARD_URL = "http://dashboard-backend-url/api" # Mock url

class AnalysisAgent:
    def __init__(self):
        # Gerçekte bir NotebookLM API bağlantısı veya RAG sistemi olur.
        # Biz burada stochastic kararlar alacak kural motorunu (Rule Engine) simüle ediyoruz.
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
        """Stokastik kural motoruyla yeni bir konfigürasyon önerir."""
        
        # NotebookLM'den çekilen kurallara dayalı rastgele varyasyon (Stochastic behavior)
        speed_modifier = random.uniform(0.8, 1.2) if reason != "safety_mode" else 0.7
        power_limit_kw = round(random.uniform(70.0, 85.0) * (self.rules_base["lap_time_priority"]), 2)
        
        config = {
            "action": "digital_twin_test_required",
            "context": context,
            "proposed_parameters": {
                "max_speed_kph": round(120.0 * speed_modifier, 1),
                "power_limit_kw": power_limit_kw,
                "pid_p": round(random.uniform(0.5, 1.5), 2)
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
                # Gerçekte burada Digital Twin triggerlanır veya Dashboard'a onay için gönderilir
                self.forward_to_dashboard(result)
                
            message.ack()
        except Exception as e:
            print(f"Mesaj islenirken hata: {e}")
            message.nack()
            
    def forward_to_dashboard(self, config):
        """Dashboard'a onaya veya teste gönder (Mock)"""
        print(f"Dashboard'a iletiliyor... {config['context'][:30]}...")

def start_subscriber():
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
