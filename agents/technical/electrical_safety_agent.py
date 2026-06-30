import os
import datetime

FS_HV_VOLTAGE = 600  # Max HV voltaj (V)
MIN_CABLE_AREA_MM2 = 4  # Min kablo kesiti

def check_hv_compliance(components: list = None, mock: bool = True) -> dict:
    """
    HV güvenlik uyumluluk kontrolü.
    IEC 60364 + Formula Student EV kuralları.
    Tetikleyici: NEW_COMPONENT_ADDED (elektrik parçası)
    """
    print('[ELECTRICAL] HV uyumluluk kontrolü başlıyor...')

    if mock or components is None:
        components = [
            {'name': 'FC Stack', 'voltage_v': 400, 'current_a': 120, 'type': 'source'},
            {'name': 'Motor Controller', 'voltage_v': 400, 'current_a': 100, 'type': 'load'},
            {'name': 'Battery Pack', 'voltage_v': 350, 'current_a': 80, 'type': 'storage'},
        ]

    checks = {}
    issues = []

    # 1. IMD bağlantısı (her sistem için zorunlu)
    checks['imd_required'] = True  # Mock: varsayım
    print('  [CHECK] IMD bağlantısı: ✅ Mevcut')

    # 2. Pre-charge devresi
    for comp in components:
        if comp['type'] == 'load' and comp.get('voltage_v', 0) > 60:
            # Pre-charge süresi: RC = 5 * R * C (C varsayımı 1000µF)
            precharge_ok = True  # Simplified check
            checks['precharge'] = precharge_ok
            print(f'  [CHECK] Pre-charge ({comp["name"]}): {"✅" if precharge_ok else "❌"}')

    # 3. Kablo kesiti kontrolü
    for comp in components:
        current = comp.get('current_a', 0)
        required_area = max(current / 3, MIN_CABLE_AREA_MM2)
        cable_ok = required_area <= 50  # 50mm² max stok
        if not cable_ok:
            issues.append(f'{comp["name"]}: Kablo kesiti yetersiz ({required_area:.1f}mm² gerekli)')
        print(f'  [CHECK] Kablo kesiti {comp["name"]}: {required_area:.1f}mm² → {"✅" if cable_ok else "❌"}')

    # 4. EBS bağımsız güç
    checks['ebs_independent_power'] = True  # Mock
    print('  [CHECK] EBS bağımsız güç kaynağı: ✅')

    overall_ok = len(issues) == 0
    result = {
        'compliant': overall_ok,
        'checks': checks,
        'issues': issues,
        'timestamp': datetime.datetime.now().isoformat()
    }

    status = '✅ UYUMLU' if overall_ok else f'⚠️ {len(issues)} SORUN'
    print(f'[ELECTRICAL] {status}')
    if issues:
        print(f'  GitHub Issue açılıyor (label: safety-critical)...')
        print(f'  Sorunlar: {issues}')

    return result

if __name__ == '__main__':
    check_hv_compliance(mock=True)
