import os
import time
import datetime
import threading
import json

from agents.chief_engineer.main import ChiefEngineerAgent, VehicleSystemState

try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None

PUBSUB_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')


class SystemMonitor:
    def __init__(self, agent: ChiefEngineerAgent = None, update_interval_ms: int = 100):
        self.agent = agent or ChiefEngineerAgent()
        self.update_interval = update_interval_ms / 1000
        self.running = False
        self._thread = None
        self.tick_count = 0

    def _publish_state(self, state_dict: dict):
        """VehicleSystemState'i Pub/Sub'a yayınlar."""
        if pubsub_v1 and PUBSUB_PROJECT:
            try:
                publisher = pubsub_v1.PublisherClient()
                topic = publisher.topic_path(PUBSUB_PROJECT, 'state-update-topic')
                publisher.publish(topic, json.dumps(state_dict).encode())
            except Exception:
                pass

    def _check_critical_thresholds(self, state: VehicleSystemState) -> list:
        """Kritik eşikleri kontrol eder, uyarı listesi döner."""
        warnings = []
        # Kural tabanlı eşikler — LSTM değil, if/else yeterli
        if state.fc_temperature_c > 80:
            warnings.append(f'FC_TEMP_CRITICAL: {state.fc_temperature_c:.1f}°C')
        if state.battery_soc < 0.15:
            warnings.append(f'BATTERY_CRITICAL: SOC {state.battery_soc*100:.1f}%')
        if state.lidar_confidence < 0.5:
            warnings.append(f'LIDAR_LOW_CONF: {state.lidar_confidence*100:.0f}%')
        return warnings

    def _monitoring_loop(self, max_ticks: int = None):
        """100ms döngüde state günceller ve kontrol eder."""
        while self.running:
            self.tick_count += 1

            # Simüle edilmiş state güncellemesi (gerçekte sensörden gelir)
            current_state = self.agent.state
            warnings = self._check_critical_thresholds(current_state)

            if warnings:
                self.agent.state.active_warnings = warnings
                print(f'[MONITOR] Tick {self.tick_count} — Uyarılar: {warnings}')

            # Her 50 tick'te bir state yayınla (5 saniye)
            if self.tick_count % 50 == 0:
                state_dict = current_state.to_dict()
                self._publish_state(state_dict)
                print(f'[MONITOR] Tick {self.tick_count} — State yayinlandi')

            if max_ticks and self.tick_count >= max_ticks:
                self.stop()
                break

            time.sleep(self.update_interval)

    def start(self, background: bool = True, max_ticks: int = None):
        self.running = True
        self.tick_count = 0
        if background:
            self._thread = threading.Thread(
                target=self._monitoring_loop, kwargs={'max_ticks': max_ticks}, daemon=True
            )
            self._thread.start()
            print(f'[MONITOR] Arka planda baslatildi ({self.update_interval*1000:.0f}ms aralık)')
        else:
            self._monitoring_loop(max_ticks=max_ticks)

    def stop(self):
        self.running = False
        print(f'[MONITOR] Durduruldu. Toplam tick: {self.tick_count}')


def run_demo(seconds: int = 3):
    agent = ChiefEngineerAgent()
    agent.update_state(fc_temperature_c=72.0, battery_soc=0.45, current_speed_kmh=55.0)
    monitor = SystemMonitor(agent, update_interval_ms=500)
    monitor.start(background=True, max_ticks=seconds * 2)
    time.sleep(seconds + 0.5)
    print(f'Demo tamamlandi. {monitor.tick_count} tick islendi.')


if __name__ == '__main__':
    run_demo(3)
