import os
import sys
import csv
import datetime
import json
from agents.surveillance.sources.blueprint_reader import VehicleBlueprint
from agents.integrations.github_client import create_issue

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

FS_COG_HEIGHT_LIMIT_MM = 350  # Formula Student kural limiti
FS_FRONT_REAR_TARGET = (45, 55)  # % ön/arka hedef

MASS_ESTIMATES_BY_TYPE = {
    'mcu': 1.2,
    'sensor': 0.4,
    'module': 1.5,
    'power': 3.0,
    'actuator': 2.5,
    'display': 0.8,
    'structural': 12.0,
    'enclosure': 2.0,
    'mechanism': 4.0,
    '3d_printed': 0.2,
    'motor': 1.0,
}

def _safe_float(value, default=0.0) -> float:
    try:
        if value in (None, ''):
            return default
        return float(str(value).replace(',', '.'))
    except Exception:
        return default

def _load_real_components() -> list[dict]:
    """Load component positions from blueprint config and masses from CSV when available."""
    csv_rows = {}
    csv_path = os.path.join('data', 'blueprint', 'parts.csv')
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                name = row.get('Name') or row.get('Component Name') or ''
                if name:
                    csv_rows[name.lower()] = row

    config_path = os.path.join('data', 'blueprint', 'config.json')
    components = []
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        for node in config.get('nodes', []):
            name = node.get('name') or node.get('id') or 'unknown'
            row = csv_rows.get(name.lower(), {})
            node_type = (node.get('type') or row.get('Type') or '').lower()
            explicit_mass = _safe_float(row.get('Weight (kg)'), 0.0)
            mass_kg = explicit_mass or MASS_ESTIMATES_BY_TYPE.get(node_type, 1.0)
            quantity = int(_safe_float(row.get('Quantity') or node.get('quantity'), 1.0) or 1)
            position = node.get('position3d') or {}
            components.append({
                'name': name,
                'mass_kg': mass_kg * quantity,
                'x_mm': _safe_float(position.get('x'), 0.0),
                'y_mm': _safe_float(position.get('y'), 0.0),
                'z_mm': _safe_float(position.get('z'), 0.0),
            })

    if not components:
        raise RuntimeError('Blueprint config.json veya parts.csv uzerinden bilesen okunamadi.')

    return components

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
        components = _load_real_components()

    total_mass = sum(c['mass_kg'] for c in components)

    # Ağırlık merkezi hesapla. Blueprint koordinatları araç merkezine göre
    # negatif/pozitif olabildiği için yükseklik ve aks dağılımı normalize edilir.
    cog_x = sum(c['mass_kg'] * c['x_mm'] for c in components) / total_mass
    cog_y = sum(c['mass_kg'] * c['y_mm'] for c in components) / total_mass
    cog_z = sum(c['mass_kg'] * c['z_mm'] for c in components) / total_mass
    min_z = min(c['z_mm'] for c in components)
    cog_height_mm = cog_z - min_z

    # Ön/arka dağılımı min/max x aralığını temsili aks hattı kabul ederek hesapla.
    min_x = min(c['x_mm'] for c in components)
    max_x = max(c['x_mm'] for c in components)
    span_x = max(max_x - min_x, 1.0)
    front_pct = max(0.0, min(100.0, ((max_x - cog_x) / span_x) * 100))
    rear_pct = 100 - front_pct

    # Limit kontrolü
    cog_ok = cog_height_mm < FS_COG_HEIGHT_LIMIT_MM
    dist_ok = abs(front_pct - FS_FRONT_REAR_TARGET[0]) < 10  # ±10% tolerans

    result = {
        'total_mass_kg': round(total_mass, 2),
        'cog_x_mm': round(cog_x, 1),
        'cog_y_mm': round(cog_y, 1),
        'cog_z_mm': round(cog_height_mm, 1),
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
    print(f'  CoG yüksekliği: {cog_height_mm:.1f}mm (limit: {FS_COG_HEIGHT_LIMIT_MM}mm) {"✅" if cog_ok else "❌"}')
    print(f'  Ön/Arka: {front_pct:.1f}% / {rear_pct:.1f}% (hedef: 45/55) {"✅" if dist_ok else "⚠️"}')

    # Rapor dosyası
    os.makedirs('reports', exist_ok=True)
    rpath = f'reports/weight_analysis_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.md'
    with open(rpath, 'w', encoding='utf-8') as f:
        f.write(f'# Ağırlık Analizi Raporu\n\n')
        f.write(f'**Durum:** {status}\n\n')
        f.write(f'| Metrik | Değer | Durum |\n|--------|-------|-------|\n')
        f.write(f'| Toplam Kütle | {total_mass:.1f} kg | — |\n')
        f.write(f'| CoG Yüksekliği | {cog_height_mm:.1f} mm | {"✅" if cog_ok else "❌"} |\n')
        f.write(f'| Ön/Arka Dağılım | {front_pct:.1f}/{rear_pct:.1f}% | {"✅" if dist_ok else "⚠️"} |\n')
    print(f'[STRUCTURAL] Rapor: {rpath}')

    if not mock and (not cog_ok or not dist_ok):
        body = (
            "Structural analysis found a Formula Student packaging risk.\n\n"
            f"- Total mass: {total_mass:.1f} kg\n"
            f"- CoG height: {cog_height_mm:.1f} mm (limit: {FS_COG_HEIGHT_LIMIT_MM} mm)\n"
            f"- Front/rear distribution: {front_pct:.1f}% / {rear_pct:.1f}% (target: 45/55)\n"
            f"- Report: `{rpath}`\n\n"
            "This issue was opened automatically from the real blueprint/config data path."
        )
        issue_url = create_issue(
            "[Auto][Structural] Weight distribution requires review",
            body,
            labels=["structural", "automated"],
        )
        if issue_url:
            print(f'[STRUCTURAL] GitHub Issue açıldı: {issue_url}')
        else:
            print('[STRUCTURAL] ⚠️ GitHub Issue açılamadı; rapor dosyası üretildi.')
    elif not cog_ok:
        print('[STRUCTURAL] ⚠️ CoG limiti aşıldı — GitHub Issue açılmalı')

    return result

if __name__ == '__main__':
    analyze_weight_distribution(mock=True)
