import os
import datetime

# H2 alarm seviyeleri (LFL = %4 hacimsel = 40000 ppm)
H2_GREEN_PPM  = 400   # < 10% LFL → normal
H2_YELLOW_PPM = 1000  # 10-25% LFL → uyarı
H2_RED_PPM    = 4000  # > 25% LFL → kritik

def monitor_hydrogen_system(sensor_readings: list = None, mock: bool = True) -> dict:
    """
    H2 sensör izleme ve alarm sistemi.
    Tetikleyici: SENSOR_ANOMALY, sürekli izleme

    NOT: Basit eşik kararları if/else ile yapılır — LSTM değil.
    LSTM sadece tank basınç trend analizi için kullanılır.
    """
    print('[H2 SAFETY] Hidrojen güvenlik izleme başlıyor...')

    if mock or sensor_readings is None:
        import random
        sensor_readings = [
            {'sensor_id': 'H2_S1', 'ppm': random.randint(50, 300), 'location': 'engine_bay'},
            {'sensor_id': 'H2_S2', 'ppm': random.randint(30, 200), 'location': 'fuel_cell'},
            {'sensor_id': 'H2_S3', 'ppm': random.randint(10, 100), 'location': 'tank_area'},
            {'sensor_id': 'PRESSURE', 'bar': random.uniform(400, 650), 'location': 'tank'},
        ]

    alerts = []
    max_ppm = 0
    overall_level = 'GREEN'

    for reading in sensor_readings:
        if 'ppm' in reading:
            ppm = reading['ppm']
            max_ppm = max(max_ppm, ppm)

            # if/else eşik kararları — LSTM kullanılmaz (basit kural yeterli)
            if ppm >= H2_RED_PPM:
                level = 'RED'
                overall_level = 'RED'
                alerts.append(f'🔴 KRİTİK: {reading["sensor_id"]} = {ppm} ppm (limit: {H2_RED_PPM})')
            elif ppm >= H2_YELLOW_PPM:
                level = 'YELLOW'
                if overall_level != 'RED':
                    overall_level = 'YELLOW'
                alerts.append(f'🟡 UYARI: {reading["sensor_id"]} = {ppm} ppm')
            else:
                level = 'GREEN'

            print(f'  {reading["sensor_id"]} ({reading["location"]}): {ppm} ppm → {level}')

        elif 'bar' in reading:
            bar = reading['bar']
            print(f'  TANK BASINCI: {bar:.1f} bar {"✅" if bar > 300 else "⚠️"}')
            # Basınç trend analizi için LSTM kullanılabilir (zaman serisi)
            # Şimdilik basit kontrol
            if bar < 300:
                alerts.append(f'⚠️ Tank basıncı düşük: {bar:.1f} bar')

    result = {
        'overall_level': overall_level,
        'max_ppm': max_ppm,
        'alerts': alerts,
        'sensor_count': len(sensor_readings),
        'timestamp': datetime.datetime.now().isoformat()
    }

    print(f'[H2 SAFETY] Seviye: {overall_level} | Maks: {max_ppm} ppm')

    if overall_level == 'RED':
        print('[H2 SAFETY] 🔴 FCEVEvent.SENSOR_CRITICAL tetikleniyor!')
    elif overall_level == 'YELLOW':
        print('[H2 SAFETY] 🟡 FCEVEvent.SENSOR_ANOMALY tetikleniyor!')

    if alerts:
        for a in alerts:
            print(f'  {a}')

    return result

if __name__ == '__main__':
    monitor_hydrogen_system(mock=True)
