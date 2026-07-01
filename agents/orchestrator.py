import argparse
import time
import datetime
import os
import json
from agents.integrations.gcp_clients import GCP_PROJECT

# ── Pillar 1 ──────────────────────────────────────────────────
from agents.sponsor.outreach_agent import batch_outreach
from agents.sponsor.response_tracker import check_responses

# ── Pillar 2 ──────────────────────────────────────────────────
from agents.social_media.scheduler import schedule_weekly_content, check_github_for_milestone

# ── Pillar 3 ──────────────────────────────────────────────────
from agents.analysis.code_improvement_agent import analyze_autonomous_code

# ── Sprint 3: Event Bus + Chief Engineer ──────────────────────
try:
    from agents.event_bus.event_definitions import FCEVEvent
    from agents.event_bus.event_router import route_event
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False

try:
    from agents.chief_engineer.main import ChiefEngineerAgent
    from agents.ml.lstm_anomaly_detector import SensorLSTM
    CHIEF_AVAILABLE = True
except ImportError:
    CHIEF_AVAILABLE = False

# ──────────────────────────────────────────────────────────────
# Mevcut 3-Pillar döngüleri
# ──────────────────────────────────────────────────────────────

def run_sponsor_cycle(mock: bool = True):
    """Sponsor outreach, inbox scan ve toplantı planlaması."""
    print("--- Starting Sponsor Cycle ---")
    if not mock and os.getenv("ALLOW_SPONSOR_EMAIL_SEND", "").lower() not in {"1", "true", "yes"}:
        print("[SAFETY] Sponsor outreach atlandi; ALLOW_SPONSOR_EMAIL_SEND=1 olmadan mail atilmaz.")
    else:
        batch_outreach("data/sponsors/target_companies.csv", mock=mock)
    check_responses(mock=mock)
    print("--- Completed Sponsor Cycle ---")

def run_social_cycle(mock: bool = True):
    """Haftalık sosyal medya içerik üretimi ve paylaşımı."""
    print("--- Starting Social Media Cycle ---")
    schedule_weekly_content(mock=mock)
    check_github_for_milestone(mock=mock)
    print("--- Completed Social Media Cycle ---")

def run_code_cycle(mock: bool = True):
    """AST tabanlı kod kalite analizi ve GitHub Issue."""
    print("--- Starting Code Analysis Cycle ---")
    analyze_autonomous_code(mock=mock)
    print("--- Completed Code Analysis Cycle ---")

# ──────────────────────────────────────────────────────────────
# Sprint 3: Event Loop
# ──────────────────────────────────────────────────────────────

def event_loop(mock: bool = True, max_iterations: int = None):
    """
    Sürekli çalışan event döngüsü.
    Pub/Sub'dan event okur, route eder, Chief Engineer state günceller.

    KRİTİK: Güvenlik kritik kararlar (EBS, stop) ASLA otomatik uygulanmaz.
    confidence < 0.6 ise insan onayı beklenir.
    """
    if not EVENT_BUS_AVAILABLE:
        print("[ORCHESTRATOR] Event Bus modülleri bulunamadı, atlıyor.")
        return

    print("[ORCHESTRATOR] Event döngüsü başlatıldı.")

    # Chief Engineer ve LSTM başlat
    chief = ChiefEngineerAgent() if CHIEF_AVAILABLE else None
    lstm  = SensorLSTM() if CHIEF_AVAILABLE else None
    if lstm:
        lstm.load_model()

    iteration = 0
    subscriber = None
    sub_path = None
    try:
        from google.cloud import pubsub_v1
        subscriber = pubsub_v1.SubscriberClient()
        sub_path = subscriber.subscription_path(
            GCP_PROJECT,
            'fcev-events-sub'
        )
        use_pubsub = not mock
    except Exception:
        use_pubsub = False

    events_to_process = []
    ack_ids = []

    if use_pubsub and subscriber and sub_path:
        max_messages = max_iterations or 10
        try:
            response = subscriber.pull(
                request={"subscription": sub_path, "max_messages": max_messages},
                timeout=10,
            )
            for received in response.received_messages:
                raw = json.loads(received.message.data.decode("utf-8"))
                event_value = raw.get("event_type") or raw.get("event") or raw.get("type")
                payload = raw.get("data") or raw.get("payload") or raw
                events_to_process.append((FCEVEvent(event_value), payload))
                ack_ids.append(received.ack_id)
            if not events_to_process:
                print("[ORCHESTRATOR] Pub/Sub mesajı yok.")
        except Exception as exc:
            print(f"[ORCHESTRATOR] Pub/Sub pull hatasi: {exc}")

    # Mock event kuyruğu (Pub/Sub yoksa)
    if mock:
        events_to_process = [
        (FCEVEvent.NEW_COMMIT_MAIN,     {'commit_sha': 'abc1234', 'message': 'LiDAR entegrasyonu'}),
        (FCEVEvent.SENSOR_ANOMALY,      {'sensor': 'FC_TEMP', 'value': 76.2, 'threshold': 75}),
        (FCEVEvent.LAP_COMPLETED,       {'lap_number': 1, 'lap_time_s': 84.5}),
        ]

    for event, payload in events_to_process:
        iteration += 1
        print(f"\n[ORCHESTRATOR] [{iteration}] Event: {event.name}")

        # 1. Event route et
        actions = route_event(event, payload, mock=mock)
        print(f"[ORCHESTRATOR] Aksiyonlar: {actions}")

        # 2. LSTM anomali skoru
        if lstm and event in (FCEVEvent.SENSOR_ANOMALY, FCEVEvent.SENSOR_CRITICAL):
            dummy_window = [{'speed_kmh': 50, 'fc_temp_c': payload.get('value', 70),
                             'battery_soc': 0.5, 'motor_power_w': 8000,
                             'h2_pressure_bar': 500, 'battery_temp_c': 30}] * 50
            pred = lstm.predict(dummy_window)
            print(f"[LSTM] Anomali skoru: {pred['anomaly_score']:.3f} | Tip: {pred['anomaly_type']}")

            # Pub/Sub'a yayınla (Firestore log ile birlikte)
            if pred['anomaly_score'] > 0.7:
                print("[LSTM] ⚠️ Yüksek anomali skoru → FCEVEvent.SENSOR_CRITICAL tetikleniyor")

        # 3. Chief Engineer state güncelle
        if chief:
            if event == FCEVEvent.LAP_COMPLETED:
                decision = chief.synthesize_decision('power_optimization')
                conf = decision.get('confidence', 0)
                print(f"[CHIEF] Karar confidence: {conf:.2f}")
                if conf < 0.6:
                    print("[CHIEF] ⚠️ İnsan onayı bekleniyor — otomatik uygulama durduruldu")

        # 4. Tüm kararları logla (Firestore)
        # Zaten agent içlerinde yapılıyor

        if max_iterations and iteration >= max_iterations:
            break

    if use_pubsub and subscriber and sub_path and ack_ids:
        subscriber.acknowledge(request={"subscription": sub_path, "ack_ids": ack_ids})
        print(f"[ORCHESTRATOR] {len(ack_ids)} Pub/Sub mesajı ack edildi.")

    print(f"\n[ORCHESTRATOR] Event döngüsü tamamlandı. {iteration} event işlendi.")

# ──────────────────────────────────────────────────────────────
# Sprint 3: Health Check
# ──────────────────────────────────────────────────────────────

_agent_heartbeats: dict = {}

def register_heartbeat(agent_name: str):
    """Agent'ların son aktif zamanını kaydeder."""
    _agent_heartbeats[agent_name] = datetime.datetime.now()

def _run_cycle_safely(name: str, fn, *args, **kwargs) -> bool:
    """Bir cycle hata verse bile orchestrator'in diger cycle'lari denemesini saglar."""
    try:
        fn(*args, **kwargs)
        return True
    except Exception as exc:
        print(f"[ORCHESTRATOR] {name} cycle hata verdi: {exc}")
        return False

def health_check(mock: bool = True) -> dict:
    """
    Her 5 dakikada çalışır.
    Tüm agent'ların son heartbeat'ini kontrol eder.
    10 dakika sessiz agent varsa uyarı üretir.
    """
    now = datetime.datetime.now()
    status = {}
    alerts = []

    expected_agents = [
        'sponsor_outreach', 'response_tracker',
        'social_scheduler', 'content_generator',
        'code_improvement', 'chief_engineer', 'lstm_detector'
    ]

    for agent in expected_agents:
        last = _agent_heartbeats.get(agent)
        if last is None:
            status[agent] = 'never_seen'
        else:
            elapsed_min = (now - last).total_seconds() / 60
            status[agent] = f'ok ({elapsed_min:.1f}m önce)' if elapsed_min < 10 else 'TIMEOUT'
            if elapsed_min >= 10:
                alerts.append(f'{agent}: {elapsed_min:.0f} dakikadır sessiz')

    result = {
        'timestamp': now.isoformat(),
        'agents': status,
        'alerts': alerts,
        'healthy': len(alerts) == 0
    }

    print(f"\n[HEALTH] {'✅ Tüm sistemler normal' if result['healthy'] else f'⚠️ {len(alerts)} uyarı'}")
    for a in alerts:
        print(f"  [HEALTH] {a}")

    # Slack bildirimi
    if alerts:
        print(f"[SLACK] #fcev-alerts: 🔴 Agent timeout: {', '.join(alerts)}")

    return result

# ──────────────────────────────────────────────────────────────
# Ana Giriş
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AGÜ FCEV Multi-Agent Orchestrator v2")
    parser.add_argument(
        "--cycle",
        type=str,
        choices=["sponsor", "social", "code", "all", "event_loop", "health"],
        default="all",
        help="Çalıştırılacak döngü"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Mock modda çalıştır (gerçek API çağrısı yok)"
    )
    parser.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="Gerçek modda çalıştır"
    )

    args = parser.parse_args()

    print(f"[ORCHESTRATOR] Mod: {'MOCK' if args.mock else 'GERÇEK'} | Döngü: {args.cycle}")
    print("=" * 60)

    failures = []

    if args.cycle in ("sponsor", "all"):
        if not _run_cycle_safely("sponsor", run_sponsor_cycle, mock=args.mock):
            failures.append("sponsor")

    if args.cycle in ("social", "all"):
        if not _run_cycle_safely("social", run_social_cycle, mock=args.mock):
            failures.append("social")

    if args.cycle in ("code", "all"):
        if not _run_cycle_safely("code", run_code_cycle, mock=args.mock):
            failures.append("code")

    if args.cycle in ("event_loop", "all"):
        if not _run_cycle_safely("event_loop", event_loop, mock=args.mock, max_iterations=5):
            failures.append("event_loop")

    if args.cycle == "health":
        if not _run_cycle_safely("health", health_check, mock=args.mock):
            failures.append("health")

    if failures:
        print(f"\n[ORCHESTRATOR] Tamamlandi, hata veren cycle'lar: {', '.join(failures)}")
    else:
        print("\n[ORCHESTRATOR] Tüm döngüler tamamlandı.")

if __name__ == "__main__":
    main()
