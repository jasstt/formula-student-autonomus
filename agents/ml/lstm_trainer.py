import os
import csv
import json
import random
import datetime

try:
    import torch
    import torch.nn as nn
    import numpy as np
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    import numpy as np  # numpy is more likely available without torch

from agents.ml.lstm_anomaly_detector import LSTMBase, SensorLSTM


# ─────────────────────────────────────────────────────────────
# Synthetic data generation + training utilities for the FCEV
# sensor anomaly LSTM.  Run this file directly to produce a
# trained model checkpoint at models/sensor_lstm.pt
# ─────────────────────────────────────────────────────────────


def generate_training_data(
    n_samples: int = 1000,
    output_path: str = 'data/training/sensor_sequences.csv',
) -> str:
    """Generate synthetic sensor sequences and save to CSV.

    Each sample is a sequence of 50 timesteps.  80 % are labelled normal,
    20 % have an injected anomaly.

    CSV columns:
        sequence_id, timestep, speed_kmh, fc_temp_c, battery_soc,
        motor_power_w, h2_pressure_bar, battery_temp_c, label, anomaly_type

    Returns the output path.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    rng = random.Random(2024)
    SEQ_LEN = 50

    rows = []
    for seq_id in range(n_samples):
        is_anomaly = rng.random() < 0.20
        label = 1 if is_anomaly else 0

        # Choose anomaly flavour once per sequence
        if is_anomaly:
            anomaly_kind = rng.choice(['thermal', 'pressure', 'electrical'])
        else:
            anomaly_kind = 'normal'

        for t in range(SEQ_LEN):
            # --- base (normal) ranges ---
            speed_kmh      = rng.uniform(20.0, 80.0)
            fc_temp_c      = rng.uniform(40.0, 70.0)
            battery_soc    = rng.uniform(0.3, 1.0)
            motor_power_w  = rng.uniform(1000.0, 12000.0)
            h2_pressure_bar= rng.uniform(350.0, 700.0)
            battery_temp_c = rng.uniform(20.0, 40.0)

            # --- inject anomaly into last 20 timesteps of the sequence ---
            if is_anomaly and t >= 30:
                if anomaly_kind == 'thermal':
                    fc_temp_c = rng.uniform(76.0, 90.0)
                elif anomaly_kind == 'pressure':
                    h2_pressure_bar = rng.uniform(200.0, 300.0)
                elif anomaly_kind == 'electrical':
                    battery_temp_c = rng.uniform(45.0, 60.0)

            rows.append({
                'sequence_id':     seq_id,
                'timestep':        t,
                'speed_kmh':       round(speed_kmh, 2),
                'fc_temp_c':       round(fc_temp_c, 2),
                'battery_soc':     round(battery_soc, 4),
                'motor_power_w':   round(motor_power_w, 1),
                'h2_pressure_bar': round(h2_pressure_bar, 2),
                'battery_temp_c':  round(battery_temp_c, 2),
                'label':           label,
                'anomaly_type':    anomaly_kind,
            })

    fieldnames = [
        'sequence_id', 'timestep', 'speed_kmh', 'fc_temp_c',
        'battery_soc', 'motor_power_w', 'h2_pressure_bar',
        'battery_temp_c', 'label', 'anomaly_type',
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'[TRAINER] {n_samples} sekans uretildi: {output_path}')
    return output_path


def train_sensor_model(
    data_path: str = 'data/training/sensor_sequences.csv',
    model_output: str = 'models/sensor_lstm.pt',
    epochs: int = 50,
    lr: float = 0.001,
) -> dict:
    """Train the SensorLSTM on generated sequence data and save weights.

    Returns a dict with training metrics.
    """
    if not TORCH_AVAILABLE:
        print('[TRAINER] WARNING: PyTorch mevcut değil — egitim atlanıyor.')
        return {'accuracy': 0.0, 'error': 'PyTorch not available'}

    # ── directories ──────────────────────────────────────────────────────────
    models_dir = os.path.dirname(model_output) if os.path.dirname(model_output) else 'models'
    os.makedirs(models_dir, exist_ok=True)

    # ── load CSV ─────────────────────────────────────────────────────────────
    sequences = {}   # seq_id -> {'features': [...], 'label': int}
    with open(data_path, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sid = int(row['sequence_id'])
            if sid not in sequences:
                sequences[sid] = {'features': [], 'label': int(row['label'])}
            sequences[sid]['features'].append([
                float(row['speed_kmh']),
                float(row['fc_temp_c']),
                float(row['battery_soc']),
                float(row['motor_power_w']),
                float(row['h2_pressure_bar']),
                float(row['battery_temp_c']),
            ])

    seq_ids = sorted(sequences.keys())

    # ── normalisation constants (same as SensorLSTM) ─────────────────────────
    FEAT_MIN = np.array([0.0,  20.0, 0.0,    0.0,   200.0,  0.0], dtype=np.float32)
    FEAT_MAX = np.array([150.0, 95.0, 1.0, 15000.0, 800.0, 70.0], dtype=np.float32)

    def normalise(arr):
        return np.clip((arr - FEAT_MIN) / (FEAT_MAX - FEAT_MIN + 1e-8), 0.0, 1.0)

    # ── build tensors ─────────────────────────────────────────────────────────
    X_list, y_list = [], []
    for sid in seq_ids:
        feats = np.array(sequences[sid]['features'], dtype=np.float32)  # (50, 6)
        feats = normalise(feats)
        X_list.append(feats)
        y_list.append(float(sequences[sid]['label']))

    X = torch.tensor(np.array(X_list), dtype=torch.float32)  # (N, 50, 6)
    y = torch.tensor(y_list, dtype=torch.float32).unsqueeze(1)  # (N, 1)

    # ── train / val split ─────────────────────────────────────────────────────
    n_total = X.shape[0]
    n_train = int(n_total * 0.8)

    # Shuffle indices deterministically
    torch.manual_seed(2024)
    perm = torch.randperm(n_total)
    train_idx = perm[:n_train]
    val_idx   = perm[n_train:]

    X_train, y_train = X[train_idx], y[train_idx]
    X_val,   y_val   = X[val_idx],   y[val_idx]

    # ── model / loss / optim ─────────────────────────────────────────────────
    model     = LSTMBase(input_size=6, hidden_size=64, num_layers=2, output_size=1)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # ── training loop ─────────────────────────────────────────────────────────
    model.train()
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        logits = model(X_train)          # (N_train, 1)
        loss   = criterion(logits, y_train)
        loss.backward()
        optimizer.step()

        if epoch % 10 == 0:
            print(f'[TRAINER] Epoch {epoch:3d}/{epochs}  |  Loss: {loss.item():.4f}')

    # ── validation accuracy ────────────────────────────────────────────────────
    model.eval()
    with torch.no_grad():
        val_logits = model(X_val)                          # (N_val, 1)
        val_probs  = torch.sigmoid(val_logits)             # (N_val, 1)
        val_preds  = (val_probs >= 0.5).float()
        val_acc    = (val_preds == y_val).float().mean().item()

    # ── save ──────────────────────────────────────────────────────────────────
    torch.save(model.state_dict(), model_output)
    print(f'[TRAINER] Model kaydedildi: {model_output}')
    print(f'[TRAINER] Validation accuracy: {val_acc:.4f}')

    return {
        'accuracy':   val_acc,
        'epochs':     epochs,
        'model_path': model_output,
        'timestamp':  datetime.datetime.now().isoformat(),
    }


if __name__ == '__main__':
    print('=== LSTM EGITIMI ===')
    data_path = generate_training_data(1000)
    results   = train_sensor_model(data_path)
    print('Sonuclar:', results)
