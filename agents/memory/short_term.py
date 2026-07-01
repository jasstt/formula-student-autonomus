import os
import json
import datetime
from typing import Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
DEFAULT_TTL = 5  # saniye — araç anlık durumu

# In-memory fallback (Redis yoksa)
_local_store: dict = {}
_local_expiry: dict = {}


class ShortTermMemory:
    """
    Araç anlık durum belleği.
    
    KRİTİK KURAL: TTL'siz ASLA set yapılmasın — bellek şişer.
    Tüm set çağrıları ttl_seconds parametresi gerektirir.
    
    Desteklenen anahtarlar:
      - 'vehicle_state'     → VehicleSystemState dict (TTL: 5s)
      - 'sensor_window'     → Son 50 sensör okuması (TTL: 10s)
      - 'current_lap'       → Anlık tur bilgisi (TTL: 300s)
      - 'lstm_last_pred'    → Son LSTM tahmini (TTL: 2s)
    """

    def __init__(self):
        self._client = None
        if REDIS_AVAILABLE:
            try:
                self._client = redis.Redis(
                    host=REDIS_HOST, port=REDIS_PORT,
                    decode_responses=True,
                    socket_timeout=1,
                    socket_connect_timeout=1
                )
                self._client.ping()
                print('[MEMORY] Redis bağlantısı kuruldu')
            except Exception:
                self._client = None
                print('[MEMORY] Redis erişilemez — in-memory fallback aktif')
        else:
            print('[MEMORY] Redis paketi yok — in-memory fallback aktif')

    def _set(self, key: str, value: dict, ttl_seconds: int):
        """TTL zorunlu — TTL'siz set yasak."""
        assert ttl_seconds > 0, 'TTL sıfır veya negatif olamaz!'
        serialized = json.dumps(value, default=str)
        if self._client:
            self._client.setex(key, ttl_seconds, serialized)
        else:
            self._local_store_set(key, value, ttl_seconds)

    def _get(self, key: str) -> Optional[dict]:
        if self._client:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        return self._local_store_get(key)

    def _local_store_set(self, key: str, value: dict, ttl: int):
        _local_store[key] = value
        _local_expiry[key] = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)

    def _local_store_get(self, key: str) -> Optional[dict]:
        if key not in _local_store:
            return None
        if datetime.datetime.utcnow() > _local_expiry.get(key, datetime.datetime.min):
            _local_store.pop(key, None)
            _local_expiry.pop(key, None)
            return None
        return _local_store[key]

    # ── Public API ───────────────────────────────────────────

    def set_vehicle_state(self, state: dict, ttl_seconds: int = 5) -> None:
        """Araç sistem durumunu sakla. TTL: 5s (varsayılan)."""
        assert ttl_seconds > 0, 'TTL zorunlu — bellek şişmemesi için'
        self._set('vehicle_state', state, ttl_seconds)

    def get_vehicle_state(self) -> Optional[dict]:
        """Anlık araç durumunu getir. TTL dolmuşsa None döner."""
        return self._get('vehicle_state')

    def set_sensor_window(self, window: list, ttl_seconds: int = 10) -> None:
        """Son 50 sensör okumasını sakla. TTL: 10s."""
        assert ttl_seconds > 0
        self._set('sensor_window', {'readings': window}, ttl_seconds)

    def get_sensor_window(self) -> Optional[list]:
        data = self._get('sensor_window')
        return data['readings'] if data else None

    def set_current_lap(self, lap_info: dict, ttl_seconds: int = 300) -> None:
        """Anlık tur bilgisi. TTL: 5 dakika."""
        assert ttl_seconds > 0
        self._set('current_lap', lap_info, ttl_seconds)

    def get_current_lap(self) -> Optional[dict]:
        return self._get('current_lap')

    def set_lstm_prediction(self, prediction: dict, ttl_seconds: int = 2) -> None:
        """Son LSTM tahminini sakla. TTL: 2s (çok taze veri gerekir)."""
        assert ttl_seconds > 0
        self._set('lstm_last_pred', prediction, ttl_seconds)

    def get_lstm_prediction(self) -> Optional[dict]:
        return self._get('lstm_last_pred')


if __name__ == '__main__':
    print('=== SHORT TERM MEMORY TEST ===')
    mem = ShortTermMemory()
    
    state = {'fc_temp': 72.5, 'soc': 0.65, 'speed': 55.0}
    mem.set_vehicle_state(state, ttl_seconds=5)
    retrieved = mem.get_vehicle_state()
    assert retrieved is not None, 'State alınamadı!'
    assert retrieved['fc_temp'] == 72.5
    print('set/get vehicle_state OK')
    
    # TTL sıfır kontrolü
    try:
        mem.set_vehicle_state({}, ttl_seconds=0)
        print('HATA: TTL=0 kabul edilmemeli!')
    except AssertionError:
        print('TTL=0 reddi OK')
    
    print('ShortTermMemory testi GECTI')
