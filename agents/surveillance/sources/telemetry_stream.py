import os
import json
import random
import time
from google.cloud import pubsub_v1
import numpy as np
from datetime import datetime

# Google Cloud Project Info
PROJECT_ID = "YOUR_PROJECT_ID"
SUBSCRIPTION_ID = "sensor-data-sub"
PUBLISH_TOPIC_ID = "agent-results-topic"

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

# Stochastic kalibrasyon faktörü (Ortam ısısı vb. dış etkenler için)
ENVIRONMENT_NOISE_FACTOR = random.uniform(0.9, 1.1)

def detect_anomaly(sensor_id, value):
    """
    Stokastik anomali tespiti (>2σ sapma).
    Gerçek dünya belirsizliklerini (sensör gürültüsü vb.) hesaba katar.
    """
    if sensor_id not in SENSOR_PROFILES:
        return False
    
    mean, std = SENSOR_PROFILES[sensor_id]
    
    # Sensör gürültüsünü simüle et
    noise = np.random.normal(0, std * 0.1)
    adjusted_value = (value * ENVIRONMENT_NOISE_FACTOR) + noise
    
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
    
    # Risk skoru hesaplama (Stokastik varyans tabanlı)
    risk_variance = random.uniform(1.0, 1.5)
    
    report = {
        "source": "telemetry_stream",
        "type": "hardware_anomaly",
        "urgency_score": round(min(10, random.uniform(7, 10) * risk_variance), 2),
        "data": sensor_data,
        "timestamp": datetime.utcnow().isoformat(),
        "action_required": "IMMEDIATE_ANALYSIS"
    }
    
    publisher.publish(topic_path, json.dumps(report).encode("utf-8"))
    print(f"Acil rapor iletildi: {report['urgency_score']} aciliyet skoru.")

def start_listening():
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
