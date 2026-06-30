import os
import json
import datetime
import numpy as np
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
# KURAL: LSTM sadece zaman serisi anomali tespiti ve sponsor
# yanıt tahmini için kullanılır.
# Basit eşik kararları (SOC < 0.2 → FC max güç gibi)
# if/else ile yapılır — LSTM KULLANILMAZ.
# ─────────────────────────────────────────────────────────────


class LSTMBase(nn.Module if TORCH_AVAILABLE else object):
    """Base LSTM module used by both sensor and sponsor predictors."""

    def __init__(self, input_size, hidden_size=64, num_layers=2, output_size=1):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available. Cannot instantiate LSTMBase.")
        super(LSTMBase, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        # Take the last time step output
        out = self.fc(out[:, -1, :])  # (batch, output_size)
        return out


class SensorLSTM:
    """Sensor anomaly detection using sliding window of 50 readings.

    Accepts a window of 50 sensor readings (each a dict) and returns an
    anomaly score between 0 and 1, along with the inferred anomaly type
    and confidence.  Falls back to rule-based logic when PyTorch is not
    available or the model weights have not been loaded yet.
    """

    # Normalisation constants (min/max per feature)
    _FEAT_MIN = np.array([0.0,  20.0, 0.0,    0.0,   200.0,  0.0])
    _FEAT_MAX = np.array([150.0, 95.0, 1.0, 15000.0, 800.0, 70.0])

    def __init__(self, model_path: str = 'models/sensor_lstm.pt'):
        self.model_path = model_path
        self.model = None
        self._model_loaded = False
        if TORCH_AVAILABLE:
            self.model = self._build_model()

    def _build_model(self) -> 'LSTMBase':
        return LSTMBase(input_size=6, hidden_size=64, num_layers=2, output_size=1)

    def load_model(self) -> bool:
        """Load model weights from *model_path*.

        Returns True on success, False if the file does not exist or
        PyTorch is unavailable.
        """
        if not TORCH_AVAILABLE:
            print("[SensorLSTM] WARNING: PyTorch mevcut değil, model yüklenemedi.")
            return False
        if not os.path.exists(self.model_path):
            print(f"[SensorLSTM] WARNING: Model dosyası bulunamadı: {self.model_path}")
            return False
        try:
            state_dict = torch.load(self.model_path, map_location='cpu')
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self._model_loaded = True
            print(f"[SensorLSTM] Model yüklendi: {self.model_path}")
            return True
        except Exception as exc:
            print(f"[SensorLSTM] Model yükleme hatası: {exc}")
            return False

    def _window_to_tensor(self, sensor_window: list) -> 'torch.Tensor':
        """Convert a list of sensor dicts to a normalised (1, 50, 6) tensor."""
        rows = []
        for reading in sensor_window:
            row = np.array([
                reading.get('speed_kmh', 0.0),
                reading.get('fc_temp_c', 60.0),
                reading.get('battery_soc', 0.5),
                reading.get('motor_power_w', 5000.0),
                reading.get('h2_pressure_bar', 450.0),
                reading.get('battery_temp_c', 30.0),
            ], dtype=np.float32)
            # Min-max normalisation to [0, 1]
            row = (row - self._FEAT_MIN) / (self._FEAT_MAX - self._FEAT_MIN + 1e-8)
            row = np.clip(row, 0.0, 1.0)
            rows.append(row)
        arr = np.array(rows, dtype=np.float32)  # (50, 6)
        tensor = torch.tensor(arr).unsqueeze(0)   # (1, 50, 6)
        return tensor

    def _infer_anomaly_type(self, sensor_window: list) -> str:
        """Determine anomaly type from which sensor deviates most."""
        last = sensor_window[-1] if sensor_window else {}
        fc_temp = last.get('fc_temp_c', 60.0)
        h2_pressure = last.get('h2_pressure_bar', 450.0)
        battery_temp = last.get('battery_temp_c', 30.0)
        motor_power = last.get('motor_power_w', 5000.0)

        deviations = {
            'thermal':    abs(fc_temp - 57.5) / 37.5,          # centre at 57.5 °C
            'pressure':   abs(h2_pressure - 500.0) / 300.0,    # centre at 500 bar
            'electrical': abs(battery_temp - 35.0) / 35.0,     # centre at 35 °C
        }
        max_type = max(deviations, key=deviations.get)
        if deviations[max_type] < 0.15:
            return 'normal'
        return max_type

    def predict(self, sensor_window: list) -> dict:
        """Run inference on *sensor_window* (list of 50 sensor dicts).

        Returns a dict with keys:
            anomaly_score  – float in [0, 1]
            anomaly_type   – 'normal' | 'thermal' | 'pressure' | 'electrical'
            confidence     – float in [0, 1]
            timestamp      – ISO-8601 string
        """
        if not TORCH_AVAILABLE or not self._model_loaded:
            return self.rule_based_fallback(sensor_window)

        # Pad or truncate window to exactly 50 readings
        window = sensor_window[-50:]
        while len(window) < 50:
            window = [window[0]] + window

        try:
            self.model.eval()
            with torch.no_grad():
                tensor = self._window_to_tensor(window)
                logit = self.model(tensor)           # (1, 1)
                anomaly_score = torch.sigmoid(logit).item()

            anomaly_type = self._infer_anomaly_type(window)
            if anomaly_score < 0.5:
                anomaly_type = 'normal'

            confidence = abs(anomaly_score - 0.5) * 2.0  # 0 at boundary, 1 at extremes

            return {
                'anomaly_score': round(float(anomaly_score), 4),
                'anomaly_type': anomaly_type,
                'confidence': round(float(confidence), 4),
                'timestamp': datetime.datetime.now().isoformat(),
            }
        except Exception as exc:
            print(f"[SensorLSTM] Tahmin hatası, fallback kullanılıyor: {exc}")
            return self.rule_based_fallback(sensor_window)

    def rule_based_fallback(self, sensor_window: list) -> dict:
        # Güvenlik için kural tabanlı fallback — LSTM kullanılmaz
        last = sensor_window[-1] if sensor_window else {}
        fc_temp = last.get('fc_temp_c', 60.0)
        h2_pressure = last.get('h2_pressure_bar', 450.0)
        battery_temp = last.get('battery_temp_c', 30.0)

        anomaly_type = 'normal'
        score = 0.1

        if fc_temp > 75.0:
            anomaly_type = 'thermal'
            score = 0.8
        elif h2_pressure < 300.0:
            anomaly_type = 'pressure'
            score = 0.8
        elif battery_temp > 45.0:
            anomaly_type = 'electrical'
            score = 0.8

        return {
            'anomaly_score': score,
            'anomaly_type': anomaly_type,
            'confidence': 0.7 if anomaly_type != 'normal' else 0.9,
            'timestamp': datetime.datetime.now().isoformat(),
        }

    def mock_predict(self, n_samples: int = 10) -> list:
        """Generate *n_samples* dummy predictions for testing."""
        results = []
        rng = np.random.default_rng(seed=42)
        anomaly_types = ['normal', 'thermal', 'pressure', 'electrical']
        for i in range(n_samples):
            atype = anomaly_types[i % len(anomaly_types)]
            score = rng.uniform(0.05, 0.25) if atype == 'normal' else rng.uniform(0.65, 0.95)
            results.append({
                'anomaly_score': round(float(score), 4),
                'anomaly_type': atype,
                'confidence': round(float(rng.uniform(0.6, 0.99)), 4),
                'timestamp': datetime.datetime.now().isoformat(),
            })
        return results


class SponsorResponseLSTM:
    """Predicts sponsor response probability and timing from historical data.

    Inputs are engineered features describing the outreach context; the model
    outputs a (response_probability, estimated_days) pair.  Falls back to a
    simple heuristic when PyTorch is unavailable.
    """

    def __init__(self):
        self.model = None
        if TORCH_AVAILABLE:
            self.model = self._build_model()
            self.model.eval()

    def _build_model(self) -> 'LSTMBase':
        return LSTMBase(input_size=4, hidden_size=32, num_layers=1, output_size=2)

    def predict(self, features: dict) -> dict:
        """Predict sponsor response from *features* dict.

        Expected keys:
            email_sent_day           – int 0-6 (Monday=0)
            company_size             – int 1 (small) / 2 (mid) / 3 (large)
            sector_type              – int 0-4
            previous_response_time_days – float

        Returns:
            response_probability – float in [0, 1]
            estimated_days       – int
            confidence           – float in [0, 1]
        """
        if not TORCH_AVAILABLE or self.model is None:
            # Simple heuristic fallback
            company_size = features.get('company_size', 2)
            prev_days = features.get('previous_response_time_days', 7.0)
            prob = min(1.0, company_size * 0.3 + 0.4 - (prev_days * 0.005))
            est_days = max(1, int(prev_days * 0.8))
            return {
                'response_probability': round(float(prob), 4),
                'estimated_days': est_days,
                'confidence': 0.55,
            }

        try:
            feat_vec = np.array([
                features.get('email_sent_day', 0) / 6.0,
                (features.get('company_size', 2) - 1) / 2.0,
                features.get('sector_type', 0) / 4.0,
                min(features.get('previous_response_time_days', 7.0), 60.0) / 60.0,
            ], dtype=np.float32)

            # Shape: (1, 1, 4) — single sequence of length 1
            tensor = torch.tensor(feat_vec).unsqueeze(0).unsqueeze(0)

            with torch.no_grad():
                out = self.model(tensor)  # (1, 2)
                prob = torch.sigmoid(out[0, 0]).item()
                days_raw = torch.sigmoid(out[0, 1]).item() * 30.0  # scale to 0-30 days

            confidence = abs(prob - 0.5) * 2.0

            return {
                'response_probability': round(float(prob), 4),
                'estimated_days': max(1, int(round(days_raw))),
                'confidence': round(float(confidence), 4),
            }
        except Exception as exc:
            print(f"[SponsorLSTM] Tahmin hatası: {exc}")
            company_size = features.get('company_size', 2)
            return {
                'response_probability': round(company_size * 0.3 + 0.1, 4),
                'estimated_days': 7,
                'confidence': 0.4,
            }

    def mock_predict(self) -> dict:
        """Return a dummy prediction for testing."""
        return {
            'response_probability': 0.724,
            'estimated_days': 8,
            'confidence': 0.612,
        }


if __name__ == '__main__':
    print('=== SENSOR LSTM TEST ===')
    sensor = SensorLSTM()
    sensor.load_model()
    preds = sensor.mock_predict(5)
    for p in preds:
        print(f'  Score: {p["anomaly_score"]:.3f} | Type: {p["anomaly_type"]} | Conf: {p["confidence"]:.3f}')

    print('\n=== SPONSOR LSTM TEST ===')
    sponsor = SponsorResponseLSTM()
    result = sponsor.mock_predict()
    print(f'  Response prob: {result["response_probability"]:.3f} | Est. days: {result["estimated_days"]}')
