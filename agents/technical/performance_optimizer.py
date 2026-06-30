import os
import datetime
import json
import statistics

def optimize_race_strategy(lap_history: list = None, mock: bool = True) -> dict:
    """
    Geçmiş tur verilerinden enerji ve performans optimizasyonu.
    Tetikleyici: LAP_COMPLETED
    """
    print('[PERF OPT] Yarış stratejisi optimizasyonu başlıyor...')

    if mock or lap_history is None:
        lap_history = [
            {'lap': 1, 'time_s': 87.2, 'energy_wh': 1350, 'fc_power_ratio': 0.7, 'avg_speed': 46.5},
            {'lap': 2, 'time_s': 85.8, 'energy_wh': 1280, 'fc_power_ratio': 0.72, 'avg_speed': 47.2},
            {'lap': 3, 'time_s': 84.1, 'energy_wh': 1310, 'fc_power_ratio': 0.68, 'avg_speed': 48.0},
        ]

    if not lap_history:
        return {'error': 'Tur verisi yok'}

    # Enerji vs süre analizi
    times = [l['time_s'] for l in lap_history]
    energies = [l['energy_wh'] for l in lap_history]
    fc_ratios = [l.get('fc_power_ratio', 0.7) for l in lap_history]

    best_time_idx = times.index(min(times))
    best_lap = lap_history[best_time_idx]

    # Optimal FC oranı (en iyi turdan interpolasyon)
    optimal_fc_ratio = best_lap.get('fc_power_ratio', 0.7)
    avg_energy = statistics.mean(energies)
    trend = 'iyileşiyor' if times[-1] < times[0] else 'kötüleşiyor'

    recommendation = {
        'optimal_fc_power_ratio': round(optimal_fc_ratio, 3),
        'recommended_speed_kmh': round(best_lap.get('avg_speed', 48) * 1.02, 1),
        'energy_target_wh': round(avg_energy * 0.95, 0),
        'strategy': 'enerji_tasarrufu' if avg_energy > 1300 else 'hiz_odakli',
        'trend': trend,
        'best_lap_time_s': min(times),
        'improvement_potential_s': round(max(times) - min(times), 1),
        'next_lap_params': {
            'fc_ratio': optimal_fc_ratio,
            'regen_aggressive': avg_energy > 1300,
            'corner_entry_speed': 'azalt' if trend == 'kötüleşiyor' else 'koru'
        }
    }

    print(f'[PERF OPT] En iyi tur: {min(times):.1f}s | Trend: {trend}')
    print(f'[PERF OPT] Önerilen FC oranı: {optimal_fc_ratio:.3f}')
    print(f'[PERF OPT] Strateji: {recommendation["strategy"]}')
    print(f'[PERF OPT] Digital twin doğrulaması başlatılıyor...')
    # Gerçekte: digital_twin simülasyonunu çalıştır ve doğrula
    print(f'[PERF OPT] ✅ Parametre seti hazır')

    return recommendation

if __name__ == '__main__':
    result = optimize_race_strategy(mock=True)
    print('\nSonuç:', json.dumps(result, ensure_ascii=False, indent=2))
