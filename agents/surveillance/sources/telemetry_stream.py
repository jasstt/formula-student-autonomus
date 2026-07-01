import os
import json
import time
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None
from datetime import datetime
from agents.integrations.gcp_clients import GCP_PROJECT

# Google Cloud Project Info
PROJECT_ID = GCP_PROJECT
SUBSCRIPTION_ID = os.getenv("SENSOR_SUBSCRIPTION_ID", "sensor-data-sub")
PUBLISH_TOPIC_ID = os.getenv("AGENT_RESULTS_TOPIC_ID", "agent-results-topic")

# Anomaly detection thresholds for stochastic simulation
# Sensor_id: (mean, std_dev)
SENSOR_PROFILES = {
    "fuel_cell_temp_c": (65.0, 5.0),
    "fuel_cell_voltage_v": (120.0, 10.0),
    "h2_pressure_bar": (350.0, 15.0),
    "motor_rpm": (8000.0, 500.0),
    "battery_soc_pct": (85.0, 2.0),
    "imu_accel_x_g": (0.0, 0.5),
    "imu_accel_y_g": (0.0, 0.8),
    "brake_pressure_front_bar": (10.0, 2.0),
    "steering_angle_deg": (0.0, 15.0),
}

ENVIRONMENT_CALIBRATION_FACTOR = float(os.getenv("TELEMETRY_CALIBRATION_FACTOR", "1.0"))

def detect_anomaly(sensor_id, value):
    """
    Deterministik anomali tespiti (>2σ sapma).
    """
    if sensor_id not in SENSOR_PROFILES:
        return False
    
    mean, std = SENSOR_PROFILES[sensor_id]
    
    adjusted_value = value * ENVIRONMENT_CALIBRATION_FACTOR
    
    z_score = abs(adjusted_value - mean) / std
    
    # 2-sigma kuralı, %95 güven aralığı
    if z_score > 2.0:
        return True
    return False

def process_telemetry_message(message):
    """
    Pub/Sub'dan gelen json formatındaki mesajı işler.
    """
    try:
        data = json.loads(message.data.decode("utf-8"))
        sensor_id = data.get("sensor_id")
        value = float(data.get("value", 0))
        
        is_anomalous = detect_anomaly(sensor_id, value)
        
        if is_anomalous:
            print(f"[ANOMALİ TESPİT EDİLDİ] Sensör: {sensor_id}, Değer: {value:.2f}")
            report_anomaly(data)
            
        message.ack()
    except Exception as e:
        print(f"Mesaj işlenirken hata: {e}")
        message.nack()

def report_anomaly(sensor_data):
    """
    Acil durum anomalisini agent-results-topic üzerinden Analysis Agent'a raporlar.
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, PUBLISH_TOPIC_ID)
    
    sensor_id = sensor_data.get("sensor_id")
    value = float(sensor_data.get("value", 0))
    mean, std = SENSOR_PROFILES.get(sensor_id, (value, 1.0))
    z_score = abs((value * ENVIRONMENT_CALIBRATION_FACTOR) - mean) / max(std, 1e-6)
    
    report = {
        "source": "telemetry_stream",
        "type": "hardware_anomaly",
        "urgency_score": round(min(10, 5 + z_score), 2),
        "data": sensor_data,
        "timestamp": datetime.utcnow().isoformat(),
        "action_required": "IMMEDIATE_ANALYSIS"
    }
    
    publisher.publish(topic_path, json.dumps(report).encode("utf-8"))
    print(f"Acil rapor iletildi: {report['urgency_score']} aciliyet skoru.")

def start_listening():
    if not pubsub_v1:
        raise RuntimeError("google-cloud-pubsub kurulu degil.")
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    
    print(f"Dinleniyor: {subscription_path}")
    
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=process_telemetry_message)
    
    try:
        # Bloklanarak dinleme
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()

if __name__ == "__main__":
    # Sadece demo/test amaçlı rastgele veri üreteci bloğu (Eğer publisher yoksa)
    # Gerçek sistemde pub/sub subscribe mantığı çalışacak
    start_listening()
