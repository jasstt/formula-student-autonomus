import os
import datetime
from dataclasses import dataclass
from typing import Optional

try:
    from google.cloud import firestore as _firestore
except ImportError:
    _firestore = None

try:
    from agents.integrations.github_client import create_github_issue
except ImportError:
    create_github_issue = None

FIRESTORE_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')

# ─────────────────────────────────────────────────────────────
# KURAL: decision_critic bir ajanın kararını ASLA DEĞİŞTİRMEZ.
# Sadece flag ekler, raporlar ve gerekirse Issue açar.
# ─────────────────────────────────────────────────────────────

@dataclass
class CriticResult:
    decision_id: str
    agent_name: str
    flags: list          # list of str flag messages
    severity: str        # 'ok' | 'warning' | 'critical'
    evaluated_at: str
    auto_issue_created: bool = False


# Daha önce görülen decision_id'leri takip et (döngü tespiti)
_seen_decisions: dict[str, int] = {}  # decision_id -> count


def evaluate_decision(
    decision: dict,  # AgentDecision.to_dict() çıktısı veya raw dict
    mock: bool = True
) -> CriticResult:
    """
    Kural tabanlı karar değerlendirmesi (LLM kullanmaz).
    Üç tür flag tespit eder:
      1. reasoning_too_shallow  — yüksek confidence + kısa reasoning
      2. possible_loop          — aynı decision_id 3+ kez
      3. suspiciously_overconfident — confidence sürekli 1.0
    """
    decision_id = decision.get('decision_id', 'unknown')
    agent_name  = decision.get('agent_name', 'unknown')
    confidence  = float(decision.get('confidence', 0.5))
    reasoning   = str(decision.get('reasoning', ''))
    tags        = decision.get('tags', [])

    flags = []

    # ── Flag 1: Sığ Gerekçe ──────────────────────────────────
    if ('safety' in tags or agent_name == 'chief_engineer') and \
       confidence > 0.9 and len(reasoning.strip()) < 50:
        flags.append(
            f'REASONING_TOO_SHALLOW: confidence={confidence:.2f} ancak '
            f'reasoning yalnızca {len(reasoning)} karakter — '
            f'güvenlik kararı için yetersiz gerekçe'
        )

    # ── Flag 2: Olası Döngü ──────────────────────────────────
    _seen_decisions[decision_id] = _seen_decisions.get(decision_id, 0) + 1
    if _seen_decisions[decision_id] >= 3:
        flags.append(
            f'POSSIBLE_LOOP: decision_id={decision_id[:8]} '
            f'{_seen_decisions[decision_id]} kez görüldü — '
            f'sonsuz döngü riski'
        )

    # ── Flag 3: Şüpheli Aşırı Güven ─────────────────────────
    # Son 5 karar sürekli 1.0 ise uyar (bu çağrıda basit: tam 1.0 kontrolü)
    if confidence == 1.0:
        flags.append(
            'SUSPICIOUSLY_OVERCONFIDENT: confidence=1.0 — hiç belirsizlik yok. '
            'Reward hacking veya sabit dönüş riski. Model çıktısını doğrula.'
        )

    # ── Önem Seviyesi ────────────────────────────────────────
    critical_flags = [f for f in flags if any(
        kw in f for kw in ['SHALLOW', 'LOOP', 'OVERCONFIDENT']
    )]
    if len(critical_flags) >= 2 or 'POSSIBLE_LOOP' in ' '.join(flags):
        severity = 'critical'
    elif flags:
        severity = 'warning'
    else:
        severity = 'ok'

    result = CriticResult(
        decision_id=decision_id,
        agent_name=agent_name,
        flags=flags,
        severity=severity,
        evaluated_at=datetime.datetime.utcnow().isoformat(),
    )

    # ── Çıktı ────────────────────────────────────────────────
    icon = {'ok': '✅', 'warning': '⚠️', 'critical': '🔴'}.get(severity, '?')
    print(f'[CRITIC] {icon} {agent_name} | severity={severity} | flags={len(flags)}')
    for f in flags:
        print(f'  [FLAG] {f}')

    # ── Critical → GitHub Issue ──────────────────────────────
    if severity == 'critical' and not mock:
        try:
            if create_github_issue:
                issue_title = f'[Agent Quality] {agent_name}: {flags[0][:80]}'
                issue_body = (
                    f'**Decision ID:** `{decision_id}`\n'
                    f'**Agent:** {agent_name}\n'
                    f'**Severity:** {severity}\n\n'
                    f'**Flags:**\n' + '\n'.join(f'- {fl}' for fl in flags)
                )
                create_github_issue(issue_title, issue_body, labels=['agent-quality-review'])
                result.auto_issue_created = True
                print(f'[CRITIC] GitHub Issue açıldı: {issue_title[:60]}')
        except Exception as e:
            print(f'[CRITIC] GitHub Issue hatasi: {e}')

    return result


def test_critic():
    """3 farklı flag türünü test et."""
    print('=== DECISION CRITIC TEST ===')

    # Test 1: Sığ gerekçe (safety + high confidence + short reasoning)
    r1 = evaluate_decision({
        'decision_id': 'aaa-111',
        'agent_name': 'chief_engineer',
        'confidence': 0.95,
        'reasoning': 'Dur',  # 3 karakter — çok kısa
        'tags': ['safety'],
    }, mock=True)
    assert 'REASONING_TOO_SHALLOW' in ' '.join(r1.flags), f'Flag 1 tespit edilemedi: {r1.flags}'
    print(f'  Test 1 GECTI: {r1.severity}')

    # Test 2: Döngü tespiti — aynı decision_id 3 kez
    for _ in range(3):
        r2 = evaluate_decision({
            'decision_id': 'loop-999',
            'agent_name': 'event_router',
            'confidence': 0.7,
            'reasoning': 'Normal decision logic with sufficient text here',
            'tags': [],
        }, mock=True)
    assert 'POSSIBLE_LOOP' in ' '.join(r2.flags), f'Flag 2 tespit edilemedi: {r2.flags}'
    print(f'  Test 2 GECTI: {r2.severity}')

    # Test 3: Aşırı güven (confidence=1.0)
    r3 = evaluate_decision({
        'decision_id': 'bbb-222',
        'agent_name': 'content_generator',
        'confidence': 1.0,
        'reasoning': 'Bu karar çok uzun bir gerekçeyle alındı ve tamamen doğrudur',
        'tags': [],
    }, mock=True)
    assert 'SUSPICIOUSLY_OVERCONFIDENT' in ' '.join(r3.flags), f'Flag 3 tespit edilemedi: {r3.flags}'
    print(f'  Test 3 GECTI: {r3.severity}')

    print('Tüm 3 flag testi GECTI ✅')


if __name__ == '__main__':
    test_critic()
