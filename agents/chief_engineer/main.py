import os
import json
import datetime
import dataclasses
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

try:
    from google.cloud import firestore
except ImportError:
    firestore = None
from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
FIRESTORE_PROJECT = GCP_PROJECT


@dataclass
class VehicleSystemState:
    # Güç sistemi
    fc_current_power_w: float = 0.0
    fc_temperature_c: float = 25.0
    fc_efficiency: float = 0.55
    battery_soc: float = 1.0
    battery_temperature_c: float = 25.0
    motor_demanded_power_w: float = 0.0

    # Otonom sistem
    current_speed_kmh: float = 0.0
    path_curvature: float = 0.0
    next_waypoint_distance_m: float = 100.0
    lidar_confidence: float = 0.95
    camera_confidence: float = 0.90

    # Çevre
    track_segment: str = 'straight'
    lap_progress: float = 0.0

    # Genel sağlık
    active_warnings: List[str] = field(default_factory=list)
    active_errors: List[str] = field(default_factory=list)
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d['last_update'] = self.last_update.isoformat()
        return d


class ChiefEngineerAgent:
    def __init__(self):
        self.state = VehicleSystemState()
        self.decision_log = []
        self._setup_gemini()

    def _setup_gemini(self):
        if genai and GEMINI_API_KEY:
            self.model = genai.Client(api_key=GEMINI_API_KEY)
        else:
            self.model = None

    def update_state(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self.state.last_update = datetime.datetime.now()

    def synthesize_decision(self, scenario: str = 'power_optimization') -> dict:
        """
        Gemini API ile sistem kararı sentezler.

        KRİTİK KURAL: Güvenlik kritik kararlar (EBS, emergency stop)
        ASLA otomatik uygulanmaz — sadece öneri üretilir.
        confidence < 0.6 ise insan onayı istenir.
        """
        s = self.state

        if scenario == 'power_optimization':
            prompt = f"""Sen bir Formula Student FCEV aracının baş mühendis yapay zeka asistanısın.

Mevcut sistem durumu:
- FC sıcaklığı: {s.fc_temperature_c:.1f}°C (normal: 40-75°C)
- Batarya SOC: {s.battery_soc*100:.1f}%
- Motor talebi: {s.motor_demanded_power_w/1000:.1f} kW
- Hız: {s.current_speed_kmh:.1f} km/h
- Önümüzdeki segment: {s.track_segment}, {s.next_waypoint_distance_m:.0f}m
- FC verimi: {s.fc_efficiency*100:.1f}%

Optimal güç dağılımı kararı ver. JSON formatında yanıt ver:
{{
  "fc_power_ratio": 0.0-1.0,
  "regen_braking": true/false,
  "speed_recommendation_kmh": float,
  "reasoning": "kısa açıklama",
  "confidence": 0.0-1.0
}}"""

        elif scenario == 'safety_check':
            prompt = f"""Formula Student FCEV güvenlik değerlendirmesi:
- H2 sensör: {s.active_warnings} aktif uyarı
- FC sıcaklığı: {s.fc_temperature_c:.1f}°C
- Hatalar: {s.active_errors}

JSON formatında yanıt ver:
{{
  "action": "warn"/"slow"/"stop",
  "reasoning": "açıklama",
  "confidence": 0.0-1.0,
  "human_approval_required": true/false
}}"""

        elif scenario == 'route_decision':
            prompt = f"""Formula Student FCEV rota kararı:
- LiDAR güven: {s.lidar_confidence*100:.0f}%
- Kamera güven: {s.camera_confidence*100:.0f}%
- Hız: {s.current_speed_kmh:.1f} km/h
- Yol eğriliği: {s.path_curvature:.3f}
- Sonraki waypoint: {s.next_waypoint_distance_m:.0f}m

JSON formatında yanıt ver:
{{
  "recommended_speed_kmh": float,
  "braking_point_m": float,
  "reasoning": "açıklama",
  "confidence": 0.0-1.0
}}"""
        else:
            prompt = f"Sistem durumu: {json.dumps(s.to_dict(), ensure_ascii=False)[:500]}\nGenel değerlendirme yap."

        result = self._call_gemini(prompt)

        # confidence < 0.6 kontrolü
        if result.get('confidence', 1.0) < 0.6:
            result['human_approval_required'] = True
            print('[CHIEF] ⚠️ Düşük güven skoru — insan onayı gerekli!')

        # GÜVENLİK: Stop/EBS kararları ASLA otomatik uygulanmaz
        if result.get('action') in ('stop', 'ebs'):
            result['auto_apply'] = False
            result['human_approval_required'] = True
            print('[CHIEF] 🔴 GÜVENLİK KARARI — Otomatik uygulama DEVRE DIŞI. İnsan onayı gerekli.')

        # Log
        self._log_decision(scenario, result)
        return result

    def _call_gemini(self, prompt: str) -> dict:
        """Gemini API çağrısı. Hata halinde kural tabanlı fallback."""
        if self.model:
            try:
                response = self.model.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                text = response.text.strip()
                # JSON parse
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0].strip()
                elif '```' in text:
                    text = text.split('```')[1].split('```')[0].strip()
                return json.loads(text)
            except json.JSONDecodeError:
                print('[CHIEF] JSON parse hatasi, metin olarak donduruluyor')
                return {'reasoning': text[:500], 'confidence': 0.5}
            except Exception as e:
                print(f'[CHIEF] Gemini API hatasi: {e} — Kural tabanlı fallback aktif')

        # Kural tabanlı fallback (LSTM veya Gemini yoksa)
        return self._rule_based_fallback()

    def _rule_based_fallback(self) -> dict:
        """Gemini erişilemez ise basit kural tabanlı karar."""
        s = self.state
        # SOC < 0.2 → FC max güç (basit kural — LSTM değil)
        if s.battery_soc < 0.2:
            fc_ratio = 1.0
        elif s.fc_temperature_c > 75:
            fc_ratio = 0.6  # Termal koruma
        else:
            fc_ratio = 0.7
        return {
            'fc_power_ratio': fc_ratio,
            'regen_braking': s.current_speed_kmh > 40,
            'speed_recommendation_kmh': min(s.current_speed_kmh, 60),
            'reasoning': 'Kural tabanlı fallback (Gemini erişilemez)',
            'confidence': 0.65,
            'fallback': True
        }

    def _log_decision(self, scenario: str, result: dict):
        """Karar geçmişini ve Firestore'a loglar."""
        entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'scenario': scenario,
            'state_snapshot': {
                'fc_temp': self.state.fc_temperature_c,
                'soc': self.state.battery_soc,
                'motor_power': self.state.motor_demanded_power_w,
            },
            'decision': result
        }
        self.decision_log.append(entry)

        try:
            db = get_firestore_client()
            db.collection('chief_engineer_decisions').add(entry)
        except Exception as e:
            print(f'[FIRESTORE] Chief Engineer karar logu yazilamadi: {e}')


def main(mock: bool = True):
    print('=== BAŞ MÜHENDİS AGENT TEST ===')
    agent = ChiefEngineerAgent()

    # Test senaryosu: FC 78°C, SOC %35, motor 15kW, 200m düzlük
    agent.update_state(
        fc_temperature_c=78.0,
        battery_soc=0.35,
        motor_demanded_power_w=15000,
        next_waypoint_distance_m=200,
        track_segment='straight',
        current_speed_kmh=65.0
    )

    print(f'Durum: FC={agent.state.fc_temperature_c}°C, SOC={agent.state.battery_soc*100:.0f}%, Motor={agent.state.motor_demanded_power_w/1000:.0f}kW')
    print('Karar sentezleniyor...')

    if mock:
        # Mock modda Gemini çağrısı değil, fallback
        result = agent._rule_based_fallback()
        result['source'] = 'mock_fallback'
    else:
        result = agent.synthesize_decision('power_optimization')

    print(f'\nKarar:')
    for k, v in result.items():
        print(f'  {k}: {v}')

    conf = result.get('confidence', 0)
    if conf >= 0.6:
        print(f'\n[OK] Confidence {conf:.2f} >= 0.6 — Karar geçerli')
    else:
        print(f'\n[UYARI] Confidence {conf:.2f} < 0.6 — İnsan onayı gerekli')

    return result


if __name__ == '__main__':
    main(mock=False)
