import os
import sys
import json
import datetime
from agents.integrations.github_client import create_issue

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

FS_HV_VOLTAGE = 600  # Max HV voltaj (V)
MIN_CABLE_AREA_MM2 = 4  # Min kablo kesiti
HV_NAME_MARKERS = (
    'high voltage',
    'hv ',
    'hv-',
    'battery management',
    'motor controller',
    'dc/dc',
    'contactor',
    'fuel cell',
    'isolation monitoring',
)

def _is_hv_node(node: dict) -> bool:
    name = (node.get('name') or '').lower()
    node_id = (node.get('id') or '').lower()
    text = f'{name} {node_id}'
    return any(marker in text for marker in HV_NAME_MARKERS)

def _estimate_current_a(component: dict) -> float:
    name = (component.get('name') or '').lower()
    voltage = component.get('voltage_v', 400) or 400
    if 'motor controller' in name:
        power_w = 17000
    elif 'dc/dc' in name or 'converter' in name:
        power_w = 5000
    elif 'battery' in name:
        power_w = 12000
    elif 'fuel cell' in name or 'fc' in name:
        power_w = 5000
    else:
        power_w = 1000
    return power_w / max(voltage, 1)

def _load_hv_components_from_blueprint() -> tuple[list[dict], dict]:
    config_path = os.path.join('data', 'blueprint', 'config.json')
    if not os.path.exists(config_path):
        raise RuntimeError('data/blueprint/config.json bulunamadi.')

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    nodes_by_id = {n.get('id'): n for n in config.get('nodes', [])}
    hv_ids = set()
    for edge in config.get('electricalConnections', []):
        source = nodes_by_id.get(edge.get('source'), {})
        target = nodes_by_id.get(edge.get('target'), {})
        pin_text = ' '.join(str(edge.get(k, '')) for k in ('sourcePin', 'targetPin', 'label')).lower()
        if 'hv' in pin_text or _is_hv_node(source) or _is_hv_node(target):
            if _is_hv_node(source):
                hv_ids.add(edge.get('source'))
            if _is_hv_node(target):
                hv_ids.add(edge.get('target'))

    components = []
    for node_id in sorted(x for x in hv_ids if x in nodes_by_id):
        node = nodes_by_id[node_id]
        name = node.get('name') or node_id
        name_lower = name.lower()
        component = {
            'name': name,
            'type': node.get('type', ''),
            'voltage_v': FS_HV_VOLTAGE if 'high voltage' in name_lower or 'hv' in name_lower else 400,
        }
        component['current_a'] = _estimate_current_a(component)
        components.append(component)

    checks = {
        'imd_present': any('isolation monitoring' in (n.get('name') or '').lower() for n in nodes_by_id.values()),
        'ebs_present': any('emergency brake' in (n.get('name') or '').lower() for n in nodes_by_id.values()),
        'precharge_present': any('pre-charge' in (n.get('name') or '').lower() or 'precharge' in (n.get('name') or '').lower() for n in nodes_by_id.values()),
    }
    return components, checks

def check_hv_compliance(components: list = None, mock: bool = True) -> dict:
    """
    HV güvenlik uyumluluk kontrolü.
    IEC 60364 + Formula Student EV kuralları.
    Tetikleyici: NEW_COMPONENT_ADDED (elektrik parçası)
    """
    print('[ELECTRICAL] HV uyumluluk kontrolü başlıyor...')

    if mock or components is None:
        if mock:
            components = [
                {'name': 'FC Stack', 'voltage_v': 400, 'current_a': 120, 'type': 'source'},
                {'name': 'Motor Controller', 'voltage_v': 400, 'current_a': 100, 'type': 'load'},
                {'name': 'Battery Pack', 'voltage_v': 350, 'current_a': 80, 'type': 'storage'},
            ]
            blueprint_checks = {'imd_present': True, 'ebs_present': True, 'precharge_present': True}
        else:
            components, blueprint_checks = _load_hv_components_from_blueprint()
    else:
        blueprint_checks = {'imd_present': None, 'ebs_present': None, 'precharge_present': None}

    checks = {}
    issues = []

    # 1. IMD bağlantısı (her sistem için zorunlu)
    checks['imd_required'] = bool(blueprint_checks.get('imd_present'))
    if checks['imd_required']:
        print('  [CHECK] IMD bağlantısı: ✅ Mevcut')
    else:
        print('  [CHECK] IMD bağlantısı: ❌ Bulunamadı')
        issues.append('Isolation Monitoring Device blueprint içinde bulunamadı')

    # 2. Pre-charge devresi
    checks['precharge'] = bool(blueprint_checks.get('precharge_present'))
    for comp in components:
        if comp.get('voltage_v', 0) > 60:
            # Pre-charge süresi: RC = 5 * R * C (C varsayımı 1000µF)
            precharge_ok = checks['precharge']
            if not precharge_ok and ('controller' in comp['name'].lower() or 'converter' in comp['name'].lower()):
                issues.append(f'{comp["name"]}: Pre-charge devresi blueprint içinde doğrulanamadı')
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
    checks['ebs_independent_power'] = bool(blueprint_checks.get('ebs_present'))
    if checks['ebs_independent_power']:
        print('  [CHECK] EBS bağımsız güç kaynağı: ✅')
    else:
        print('  [CHECK] EBS bağımsız güç kaynağı: ❌ Doğrulanamadı')
        issues.append('Emergency Brake System blueprint içinde doğrulanamadı')

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
        print(f'  Sorunlar: {issues}')
        if not mock:
            body = (
                "HV compliance check found safety-critical issues from the real blueprint/config data path.\n\n"
                + "\n".join(f"- {issue}" for issue in issues)
                + "\n\nChecks:\n"
                + "\n".join(f"- {key}: {value}" for key, value in checks.items())
            )
            issue_url = create_issue(
                "[Auto][Safety] HV compliance issues require review",
                body,
                labels=["safety-critical", "automated"],
            )
            if issue_url:
                print(f'  GitHub Issue açıldı: {issue_url}')
            else:
                print('  GitHub Issue açılamadı; terminal çıktısı kontrol edilmeli.')
        else:
            print(f'  GitHub Issue açılıyor (label: safety-critical)...')

    return result

if __name__ == '__main__':
    check_hv_compliance(mock=True)
