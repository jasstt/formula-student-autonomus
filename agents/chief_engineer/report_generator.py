import os
import json
import datetime
import statistics

from agents.chief_engineer.main import VehicleSystemState


def generate_lap_report(lap_data: dict, output_dir: str = 'reports', mock: bool = True) -> str:
    """
    Simülasyon turu sonrası analiz raporu üretir.
    Returns: rapor dosyasının yolu
    """
    os.makedirs(output_dir, exist_ok=True)

    if mock:
        lap_data = {
            'lap_number': lap_data.get('lap_number', 1),
            'lap_time_s': 85.3,
            'energy_used_wh': 1240,
            'fc_avg_efficiency': 0.54,
            'fc_max_temp_c': 72.1,
            'battery_min_soc': 0.31,
            'anomalies': [],
            'avg_speed_kmh': 48.2,
            'top_speed_kmh': 73.4,
            'regen_energy_wh': 89
        }

    lap_num = lap_data.get('lap_number', 1)
    now = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    filename = f'lap_{lap_num:02d}_report_{now}.md'
    filepath = os.path.join(output_dir, filename)

    report = f"""# Tur {lap_num} Analiz Raporu
**Tarih:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Performans Özeti
| Metrik | Değer |
|--------|-------|
| Tur Süresi | {lap_data.get('lap_time_s', 0):.1f} s |
| Ort. Hız | {lap_data.get('avg_speed_kmh', 0):.1f} km/h |
| Maks Hız | {lap_data.get('top_speed_kmh', 0):.1f} km/h |
| Enerji Tüketimi | {lap_data.get('energy_used_wh', 0):.0f} Wh |
| Rejeneratif Enerji | {lap_data.get('regen_energy_wh', 0):.0f} Wh |

## Yakıt Hücresi & Batarya
| Metrik | Değer | Durum |
|--------|-------|-------|
| FC Ort. Verim | {lap_data.get('fc_avg_efficiency', 0)*100:.1f}% | {'✅' if lap_data.get('fc_avg_efficiency', 0) > 0.5 else '⚠️'} |
| FC Maks Sıcaklık | {lap_data.get('fc_max_temp_c', 0):.1f}°C | {'✅' if lap_data.get('fc_max_temp_c', 0) < 75 else '🔴'} |
| Batarya Min SOC | {lap_data.get('battery_min_soc', 0)*100:.1f}% | {'✅' if lap_data.get('battery_min_soc', 0) > 0.2 else '⚠️'} |

## Anomali Özeti
{chr(10).join(['- ' + a for a in lap_data.get('anomalies', [])]) or '✅ Anomali tespit edilmedi'}

## Bir Sonraki Tur Önerileri
- FC güç oranı: {'artır (verim iyi)' if lap_data.get('fc_avg_efficiency', 0) > 0.52 else 'düşür (verim düşük)'}
- Batarya SOC {'kritik — şarj stratejisi gözden geçir' if lap_data.get('battery_min_soc', 0) < 0.25 else 'normal aralıkta'}
- {'⚠️ FC sıcaklığı yüksek — soğutma sistemi kontrol edilmeli' if lap_data.get('fc_max_temp_c', 0) > 74 else 'Termal yönetim nominal'}

*Rapor otomatik üretildi — Baş Mühendis Agent*
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f'[REPORT] Tur raporu: {filepath}')

    # Slack bildirimi (mock)
    slack_msg = f'📊 Tur {lap_num} raporu hazır | Süre: {lap_data.get("lap_time_s", 0):.1f}s | Enerji: {lap_data.get("energy_used_wh", 0):.0f}Wh'
    print(f'[SLACK] #fcev-telemetry: {slack_msg}')

    return filepath


if __name__ == '__main__':
    path = generate_lap_report({'lap_number': 1}, mock=True)
    print('Rapor olusturuldu:', path)
    with open(path) as f:
        print(f.read())
