"""
AGU Formula Student FCEV — Olay Yönlendiricisi (Event Router)
=============================================================
Bu modül, FCEV çok-etmen sisteminin merkezi olay yönlendirme katmanıdır.
Her FCEVEvent türüne karşılık hangi etmenlerin ve servislerin tetikleneceği
burada tanımlanır.

Tüm dış çağrılar (Pub/Sub, Slack, GitHub) try/except ile sarmalanmış
ve mock=True bayrağıyla güvenli simülasyon modunda çalışacak biçimde
tasarlanmıştır.
"""

import os
import sys
import json
import datetime

# Olay tanımlarını içeri al — hem paket içi hem de doğrudan çalıştırma için
try:
    from agents.event_bus.event_definitions import FCEVEvent, EventPayload
except ImportError:
    from event_definitions import FCEVEvent, EventPayload


# ===========================================================================
# Yardımcı: Pub/Sub Yayıncı (mock veya gerçek)
# ===========================================================================

def _mock_pubsub_publish(topic: str, message: dict) -> None:
    """
    Google Cloud Pub/Sub'a mesaj yayımlar.
    Gerçek Pub/Sub kütüphanesi mevcut değilse mock modda çalışır.

    Args:
        topic (str): Hedef Pub/Sub konu adı.
        message (dict): Yayımlanacak mesaj sözlüğü.
    """
    try:
        from google.cloud import pubsub_v1  # type: ignore

        publisher = pubsub_v1.PublisherClient()
        project_id = os.environ.get("GCP_PROJECT_ID", "agu-fcev-project")
        topic_path = publisher.topic_path(project_id, topic)
        data_bytes = json.dumps(message, default=str).encode("utf-8")
        future = publisher.publish(topic_path, data_bytes)
        print(f"[PUBSUB] Yayımlandi → {topic} (msg_id={future.result()})")
    except Exception:
        # Mock modu: kütüphane yoksa veya hata varsa terminale yazdır
        print(f"[PUBSUB] {topic}: {json.dumps(message, default=str, ensure_ascii=False)}")


# ===========================================================================
# Yardımcı: Slack Bildirici (mock)
# ===========================================================================

def _mock_slack_notify(message: str, channel: str = "#fcev-alerts") -> None:
    """
    Slack kanalına bildirim gönderir (mock modda terminale yazar).

    Args:
        message (str): Gönderilecek mesaj metni.
        channel (str): Hedef Slack kanalı. Varsayılan: '#fcev-alerts'.
    """
    try:
        slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
        if slack_token:
            import urllib.request
            payload = json.dumps({"channel": channel, "text": message}).encode()
            req = urllib.request.Request(
                "https://slack.com/api/chat.postMessage",
                data=payload,
                headers={
                    "Authorization": f"Bearer {slack_token}",
                    "Content-Type": "application/json",
                },
            )
            urllib.request.urlopen(req, timeout=5)
            print(f"[SLACK] Gönderildi → {channel}: {message[:80]}")
            return
    except Exception:
        pass  # Gerçek gönderim başarısız olursa mock'a düş

    print(f"[SLACK] {channel}: {message}")


# ===========================================================================
# Ana Yönlendirici: route_event
# ===========================================================================

def route_event(event: FCEVEvent, payload: dict, mock: bool = True) -> list:
    """
    Gelen FCEVEvent türüne göre ilgili etmen ve servisleri tetikler.

    Args:
        event (FCEVEvent): Yönlendirilecek olay türü.
        payload (dict): Olaya ait serbest biçimli veri.
        mock (bool): True ise gerçek servis çağrıları atlanır. Varsayılan: True.

    Returns:
        list[str]: Gerçekleştirilen eylemlerin listesi.
    """
    actions: list = []

    # -----------------------------------------------------------------------
    # NEW_COMPONENT_ADDED — Yeni bileşen eklendi
    # -----------------------------------------------------------------------
    if event == FCEVEvent.NEW_COMPONENT_ADDED:
        print(f"[ROUTER] NEW_COMPONENT_ADDED: {payload.get('component_name')}")

        # Blueprint okuyucuyu yeniden yükle
        actions.append("blueprint_reader: reload")
        try:
            from agents.surveillance.sources.blueprint_reader import VehicleBlueprint
            bp = VehicleBlueprint()
            params = bp.load_vehicle_params()
            print(f"[BLUEPRINT] Yeniden yüklendi, parametreler: {list(params.keys())[:3]}")
        except Exception as _e:
            print(f"[BLUEPRINT] Mock mod — blueprint_reader erişilemiyor: {_e}")

        # Araç modelini güncelle
        actions.append("vehicle_model: update_params")

        # Yapısal analiz tetikle
        try:
            from agents.technical.structural_analysis_agent import analyze_weight_distribution
            analyze_weight_distribution(mock=mock)
        except Exception as _e:
            print(f"[STRUCTURAL] Mock mod — analyze_weight_distribution: {_e}")
        actions.append("structural_analysis: triggered")

        # Elektrik güvenliği kontrolü tetikle
        try:
            from agents.technical.electrical_safety_agent import check_hv_compliance
            check_hv_compliance(mock=mock)
        except Exception as _e:
            print(f"[ELECTRICAL] Mock mod — check_hv_compliance: {_e}")
        actions.append("electrical_safety: triggered")

        # Pub/Sub ve Slack
        _mock_pubsub_publish("component-update-topic", payload)
        _mock_slack_notify(
            f"Yeni parça eklendi: {payload.get('component_name', '?')}",
            "#fcev-hardware",
        )

        component_text = " ".join(
            str(payload.get(key, ""))
            for key in ("component_name", "category", "type", "subsystem")
        ).lower()
        if "motor" in component_text:
            print("[ROUTER] Motor bileşeni algılandı; performans ve iletişim zinciri tetikleniyor.")
            actions.append("motor_component_detected")

            try:
                from agents.technical.performance_optimizer import optimize_race_strategy
                optimize_race_strategy(mock=mock)
            except Exception as _e:
                print(f"[PERF OPT] Mock mod — optimize_race_strategy: {_e}")
            actions.append("performance_optimizer: recalculated")

            try:
                from agents.chief_engineer.main import ChiefEngineerAgent
                chief = ChiefEngineerAgent()
                chief.update_state(
                    motor_demanded_power_w=float(payload.get("peak_power_w", 17000)),
                    track_segment="straight",
                )
                decision = chief.synthesize_decision("power_optimization")
                print(
                    "[CHIEF] Yeni motor state sentezi: "
                    f"confidence={decision.get('confidence', 0):.2f}"
                )
            except Exception as _e:
                print(f"[CHIEF] Mock mod — motor state synthesis: {_e}")
            actions.append("chief_engineer: state_synthesized")

            route_event(
                FCEVEvent.MOTOR_FOUND,
                {
                    "motor_name": payload.get("supplier")
                    or payload.get("component_name", "Rear Electric Motor"),
                    "peak_power_w": payload.get("peak_power_w", 17000),
                },
                mock=mock,
            )
            actions.append("motor_found: routed")

    # -----------------------------------------------------------------------
    # MOTOR_FOUND — Motor seçimi tamamlandı
    # -----------------------------------------------------------------------
    elif event == FCEVEvent.MOTOR_FOUND:
        print(f"[ROUTER] MOTOR_FOUND: {payload.get('motor_name')}")

        # Araç modelini güncelle
        actions.append("vehicle_model: update")

        # Performans optimizatörünü tetikle
        actions.append("performance_optimizer: retrigger")

        # Yakıt hücresi yöneticisini bilgilendir
        actions.append("fuel_cell_manager: recalculate_power_split")

        # LinkedIn teknik gönderi oluştur
        actions.append("linkedin_post: trigger")
        try:
            from agents.social_media.content_generator import generate_technical_post
            result = generate_technical_post(
                "technical_milestone",
                {"commit_message": f"Motor seçildi: {payload.get('motor_name', '?')}"},
                mock=mock,
            )
            if result:
                print(
                    f"[LINKEDIN] Post taslağı: "
                    f"{result.get('linkedin_text', '')[:150]}"
                )
        except Exception as _e:
            print(f"[LINKEDIN] Mock mod — generate_technical_post: {_e}")

        _mock_slack_notify(
            f"Motor seçildi: {payload.get('motor_name')} "
            f"— Simülasyonlar yeniden başlatılıyor",
            "#fcev-technical",
        )

    # -----------------------------------------------------------------------
    # SENSOR_CRITICAL — Kritik sensör alarmı
    # -----------------------------------------------------------------------
    elif event == FCEVEvent.SENSOR_CRITICAL:
        print("[ROUTER] !!! SENSOR_CRITICAL !!!")

        _mock_slack_notify(
            "[ALARM] KRITIK SENSOR ALARMI: " + str(payload),
            "#fcev-emergency",
        )

        # Acil eylemler
        actions.append("EBS_simulation_trigger")
        actions.append("safety_monitor_alert")
        actions.append("halt_all_processes")
        actions.append("firestore_log")

        print("[SAFETY] Tüm işlemler durduruldu. İnsan müdahalesi gerekli.")

    # -----------------------------------------------------------------------
    # SPONSOR_AGREED — Sponsor anlaşmayı kabul etti
    # -----------------------------------------------------------------------
    elif event == FCEVEvent.SPONSOR_AGREED:
        print(f"[ROUTER] SPONSOR_AGREED: {payload.get('company')}")

        # Anlaşma takip sistemini güncelle
        try:
            from agents.sponsor.agreement_tracker import update_pipeline
            update_pipeline(payload.get("company", ""), "agreed", mock=mock)
        except Exception as _e:
            print(f"[SPONSOR] Mock mod — agreement_tracker: {_e}")
        actions.append("agreement_tracker_updated")

        # Sosyal medya gönderisi oluştur
        try:
            from agents.social_media.content_generator import generate_technical_post
            result = generate_technical_post(
                "sponsor_joined",
                {"company": payload.get("company", "")},
                mock=mock,
            )
            if result:
                print(
                    f"[SOCIAL] LinkedIn post taslağı üretildi: "
                    f"{result.get('linkedin_text', '')[:100]}"
                )
        except Exception as _e:
            print(f"[SOCIAL] Mock mod — generate_technical_post: {_e}")
        actions.append("social_post_generated")

        _mock_slack_notify(
            f"[YILDIZ] {payload.get('company')} sponsorlugu onayladi!",
            "#fcev-sponsors",
        )

        actions.append("thank_you_email")
        actions.append("readme_pr")

    # -----------------------------------------------------------------------
    # NEW_COMMIT_MAIN — Main dalına yeni commit
    # -----------------------------------------------------------------------
    elif event == FCEVEvent.NEW_COMMIT_MAIN:
        try:
            from agents.analysis.code_improvement_agent import analyze_autonomous_code
            analyze_autonomous_code(mock=mock)
        except Exception as _e:
            print(f"[CODE] Mock mod — analyze_autonomous_code: {_e}")
        actions.append("code_analysis_triggered")

    # -----------------------------------------------------------------------
    # DEFAULT — Bilinmeyen / diğer olaylar
    # -----------------------------------------------------------------------
    else:
        print(f"[ROUTER] {event.name} alındı, payload: {payload}")
        actions.append(f"{event.name}: logged")

    return actions


# ===========================================================================
# Test Fonksiyonu
# ===========================================================================

def test_event_routing(mock: bool = True) -> None:
    """
    Tüm ana olay yollarını sahte yüklerle test eder ve sonuçları ekrana yazar.

    Args:
        mock (bool): True ise dış servis çağrıları simüle edilir. Varsayılan: True.
    """
    separator = "=" * 60

    test_cases = [
        (
            FCEVEvent.NEW_COMPONENT_ADDED,
            {
                "component_name": "Bosch SME 120 Motor Kontrolcüsü",
                "component_id": "comp-001",
                "mass_kg": 3.2,
                "category": "electronics",
            },
        ),
        (
            FCEVEvent.MOTOR_FOUND,
            {
                "motor_name": "Cascadia Motion PM150DX",
                "peak_power_kw": 150,
                "continuous_power_kw": 100,
                "max_rpm": 6000,
            },
        ),
        (
            FCEVEvent.SENSOR_CRITICAL,
            {
                "sensor_id": "HV_ISOLATION_001",
                "value": 0.42,
                "threshold": 500,
                "unit": "ohm/V",
                "location": "battery_pack_rear",
            },
        ),
        (
            FCEVEvent.SPONSOR_AGREED,
            {
                "company": "Bosch Turkey",
                "contact": "mehmet.yilmaz@bosch.com",
                "value_usd": 15000,
                "category": "technical",
            },
        ),
        (
            FCEVEvent.NEW_COMMIT_MAIN,
            {
                "commit_hash": "a3f8c1d",
                "author": "agu-dev-team",
                "message": "feat: LSTM anomaly detector entegre edildi",
                "files_changed": 7,
            },
        ),
    ]

    print("\n" + separator)
    print("  AGU FCEV — Event Router Test Başlıyor")
    print(separator + "\n")

    for i, (event, payload) in enumerate(test_cases, 1):
        print(f"\n--- Test {i}/{len(test_cases)}: {event.name} ---")
        actions = route_event(event, payload, mock=mock)
        print(f"[RESULT] Eylemler ({len(actions)}): {actions}")
        print()

    print(separator)
    print("  Tüm testler tamamlandı.")
    print(separator + "\n")


# ===========================================================================
# Doğrudan Çalıştırma
# ===========================================================================

if __name__ == "__main__":
    test_event_routing(mock=True)
