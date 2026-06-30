import os
import sys
import datetime
import json
from agents.surveillance.sources.blueprint_reader import VehicleBlueprint

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

FS_COG_HEIGHT_LIMIT_MM = 350  # Formula Student kural limiti
FS_FRONT_REAR_TARGET = (45, 55)  # % ön/arka hedef

def analyze_weight_distribution(mock: bool = True) -> dict:
    """
    Ağırlık dağılımı ve ağırlık merkezi analizi.
    Tetikleyici: NEW_COMPONENT_ADDED, COMPONENT_SPECS_UPDATED
    """
    print('[STRUCTURAL] Ağırlık analizi başlıyor...')

    if mock:
        # Mock veri
        components = [
            {'name': 'FC Stack', 'mass_kg': 12.0, 'x_mm': 800, 'y_mm': 0, 'z_mm': 280},
            {'name': 'Battery Pack', 'mass_kg': 8.5, 'x_mm': 400, 'y_mm': 0, 'z_mm': 200},
            {'name': 'Electric Motor', 'mass_kg': 7.2, 'x_mm': 1600, 'y_mm': 0, 'z_mm': 250},
            {'name': 'Chassis', 'mass_kg': 25.0, 'x_mm': 900, 'y_mm': 0, 'z_mm': 150},
            {'name': 'Driver+Seat', 'mass_kg': 80.0, 'x_mm': 700, 'y_mm': 0, 'z_mm': 320},
        ]
    else:
        bp = VehicleBlueprint()
        params = bp.load_vehicle_params()
        # Blueprint'ten gerçek parça verilerini al
        components = [
            {'name': 'FC Stack', 'mass_kg': params.get('fc_stack_mass_kg', 12.0), 'x_mm': 800, 'y_mm': 0, 'z_mm': 280},
            {'name': 'Battery Pack', 'mass_kg': params.get('battery_mass_kg', 8.5), 'x_mm': 400, 'y_mm': 0, 'z_mm': 200},
            {'name': 'Motor', 'mass_kg': params.get('motor_mass_kg', 7.2), 'x_mm': 1600, 'y_mm': 0, 'z_mm': 250},
        ]

    total_mass = sum(c['mass_kg'] for c in components)

    # Ağırlık merkezi hesapla
    cog_x = sum(c['mass_kg'] * c['x_mm'] for c in components) / total_mass
    cog_y = sum(c['mass_kg'] * c['y_mm'] for c in components) / total_mass
    cog_z = sum(c['mass_kg'] * c['z_mm'] for c in components) / total_mass

    # Ön/arka dağılım (x < 900mm ön, x >= 900mm arka varsayımı)
    wheelbase_mm = 1800
    front_mass = sum(c['mass_kg'] * (1 - c['x_mm']/wheelbase_mm) for c in components if c['x_mm'] < wheelbase_mm)
    rear_mass = total_mass - front_mass
    front_pct = (front_mass / total_mass) * 100
    rear_pct = 100 - front_pct

    # Limit kontrolü
    cog_ok = cog_z < FS_COG_HEIGHT_LIMIT_MM
    dist_ok = abs(front_pct - FS_FRONT_REAR_TARGET[0]) < 10  # ±10% tolerans

    result = {
        'total_mass_kg': round(total_mass, 2),
        'cog_x_mm': round(cog_x, 1),
        'cog_y_mm': round(cog_y, 1),
        'cog_z_mm': round(cog_z, 1),
        'front_pct': round(front_pct, 1),
        'rear_pct': round(rear_pct, 1),
        'cog_height_ok': cog_ok,
        'distribution_ok': dist_ok,
        'timestamp': datetime.datetime.now().isoformat()
    }

    # Rapor
    status = '✅ UYUMLU' if (cog_ok and dist_ok) else '⚠️ İNCELEME GEREKLİ'
    print(f'[STRUCTURAL] {status}')
    print(f'  Toplam kütle: {total_mass:.1f} kg')
    print(f'  CoG yüksekliği: {cog_z:.1f}mm (limit: {FS_COG_HEIGHT_LIMIT_MM}mm) {"✅" if cog_ok else "❌"}')
    print(f'  Ön/Arka: {front_pct:.1f}% / {rear_pct:.1f}% (hedef: 45/55) {"✅" if dist_ok else "⚠️"}')

    # Rapor dosyası
    os.makedirs('reports', exist_ok=True)
    rpath = f'reports/weight_analysis_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.md'
    with open(rpath, 'w', encoding='utf-8') as f:
        f.write(f'# Ağırlık Analizi Raporu\n\n')
        f.write(f'**Durum:** {status}\n\n')
        f.write(f'| Metrik | Değer | Durum |\n|--------|-------|-------|\n')
        f.write(f'| Toplam Kütle | {total_mass:.1f} kg | — |\n')
        f.write(f'| CoG Yüksekliği | {cog_z:.1f} mm | {"✅" if cog_ok else "❌"} |\n')
        f.write(f'| Ön/Arka Dağılım | {front_pct:.1f}/{rear_pct:.1f}% | {"✅" if dist_ok else "⚠️"} |\n')
    print(f'[STRUCTURAL] Rapor: {rpath}')

    if not cog_ok:
        print('[STRUCTURAL] ⚠️ CoG limiti aşıldı — GitHub Issue açılmalı')

    return result

if __name__ == '__main__':
    analyze_weight_distribution(mock=True)
