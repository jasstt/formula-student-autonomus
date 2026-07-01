import os
import datetime
from dataclasses import dataclass, field
from typing import Optional

try:
    from agents.integrations.github_client import create_github_issue
except ImportError:
    create_github_issue = None


@dataclass
class AgentPermission:
    agent_name: str
    can_write_github: bool = False
    can_send_email: bool = False
    can_post_social: bool = False
    can_trigger_safety_action: bool = False  # ASLA True olmaz
    max_daily_actions: int = 10


# ── İzin Kayıt Defteri ───────────────────────────────────────
PERMISSION_REGISTRY: dict[str, AgentPermission] = {
    'chief_engineer': AgentPermission(
        agent_name='chief_engineer',
        can_write_github=False,
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,  # Sadece öneri üretir
        max_daily_actions=1000,
    ),
    'structural_analysis_agent': AgentPermission(
        agent_name='structural_analysis_agent',
        can_write_github=True,   # Issue açabilir
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,
        max_daily_actions=20,
    ),
    'electrical_safety_agent': AgentPermission(
        agent_name='electrical_safety_agent',
        can_write_github=True,   # Safety issue açabilir
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,
        max_daily_actions=20,
    ),
    'sponsor_outreach_agent': AgentPermission(
        agent_name='sponsor_outreach_agent',
        can_write_github=False,
        can_send_email=True,     # Mail gönderebilir
        can_post_social=False,
        can_trigger_safety_action=False,
        max_daily_actions=25,    # Günlük rate limit ile eşleşsin
    ),
    'content_generator': AgentPermission(
        agent_name='content_generator',
        can_write_github=False,
        can_send_email=False,
        can_post_social=True,    # LinkedIn/Instagram
        can_trigger_safety_action=False,
        max_daily_actions=10,
    ),
    'code_improvement_agent': AgentPermission(
        agent_name='code_improvement_agent',
        can_write_github=True,   # Issue/PR açabilir
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,
        max_daily_actions=50,
    ),
    'decision_critic': AgentPermission(
        agent_name='decision_critic',
        can_write_github=True,   # Quality issue açabilir
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,
        max_daily_actions=100,
    ),
    'event_router': AgentPermission(
        agent_name='event_router',
        can_write_github=False,
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,
        max_daily_actions=5000,  # Yüksek throughput
    ),
    'hydrogen_safety_agent': AgentPermission(
        agent_name='hydrogen_safety_agent',
        can_write_github=True,
        can_send_email=False,
        can_post_social=False,
        can_trigger_safety_action=False,  # Sadece uyarı, tetikleme değil
        max_daily_actions=1440,  # Her dakika çalışabilir
    ),
}

# ACTION_TYPE → permission field haritası
ACTION_PERMISSION_MAP = {
    'write_github':        'can_write_github',
    'send_email':          'can_send_email',
    'post_social':         'can_post_social',
    'trigger_safety':      'can_trigger_safety_action',
    'create_github_issue': 'can_write_github',
    'create_pull_request': 'can_write_github',
    'send_calendar_invite':'can_send_email',
    'post_linkedin':       'can_post_social',
    'post_instagram':      'can_post_social',
}

# Günlük aksiyon sayacı (process-level, gerçekte Redis/Firestore'da tutulur)
_daily_action_count: dict[str, int] = {}
_last_reset_date: str = datetime.date.today().isoformat()


def _reset_if_new_day():
    global _daily_action_count, _last_reset_date
    today = datetime.date.today().isoformat()
    if today != _last_reset_date:
        _daily_action_count = {}
        _last_reset_date = today


def check_permission(
    agent_name: str,
    action_type: str,
    mock: bool = True
) -> bool:
    """
    CRITICAL: Bu fonksiyon her dış etkili aksiyonun ilk satırında çağrılmalı.
    İzin yoksa PermissionError fırlatır.
    Günlük limit aşıldıysa da reddeder.

    Returns True eğer izin verildi.
    """
    _reset_if_new_day()

    # Kayıt defterinde olmayan agent → reddet
    perm = PERMISSION_REGISTRY.get(agent_name)
    if perm is None:
        msg = f'[SECURITY] UNKNOWN AGENT: "{agent_name}" kayıt defterinde yok!'
        print(msg)
        if not mock and create_github_issue:
            try:
                create_github_issue(
                    f'Security: Unknown agent "{agent_name}" tried "{action_type}"',
                    f'Agent `{agent_name}` is not in PERMISSION_REGISTRY.\n'
                    f'Action attempted: `{action_type}`\n'
                    f'Time: {datetime.datetime.utcnow().isoformat()}',
                    labels=['security-violation']
                )
            except Exception:
                pass
        raise PermissionError(msg)

    # Permission alanını bul
    perm_field = ACTION_PERMISSION_MAP.get(action_type)
    if perm_field is not None:
        allowed = getattr(perm, perm_field, False)
        if not allowed:
            msg = (f'[SECURITY] PERMISSION DENIED: {agent_name} → '
                   f'{action_type} ({perm_field}=False)')
            print(msg)
            if not mock and create_github_issue:
                try:
                    create_github_issue(
                        f'Security Violation: {agent_name} unauthorized {action_type}',
                        f'**Agent:** `{agent_name}`\n**Action:** `{action_type}`\n'
                        f'**Time:** {datetime.datetime.utcnow().isoformat()}\n'
                        f'**Permission field:** `{perm_field}` is False',
                        labels=['security-violation']
                    )
                except Exception:
                    pass
            raise PermissionError(msg)

    # Günlük limit kontrolü
    key = f'{agent_name}:{datetime.date.today().isoformat()}'
    current = _daily_action_count.get(key, 0)
    if current >= perm.max_daily_actions:
        msg = (f'[SECURITY] RATE LIMIT: {agent_name} günlük limite '
               f'ulaştı ({current}/{perm.max_daily_actions})')
        print(msg)
        raise PermissionError(msg)

    # İzin verildi — sayacı artır
    _daily_action_count[key] = current + 1
    print(f'[SECURITY] OK: {agent_name} → {action_type} '
          f'({_daily_action_count[key]}/{perm.max_daily_actions})')
    return True


if __name__ == '__main__':
    print('=== PERMISSIONS TEST ===')
    # OK: structural_analysis GitHub issue açabilir
    check_permission('structural_analysis_agent', 'write_github', mock=True)
    print('Test 1 OK: structural_analysis → write_github izni var')

    # FAIL: chief_engineer mail gönderemez
    try:
        check_permission('chief_engineer', 'send_email', mock=True)
        print('HATA: Bunu kabul etmemeli!')
    except PermissionError as e:
        print(f'Test 2 OK: Reddedildi → {e}')

    # FAIL: bilinmeyen agent
    try:
        check_permission('rogue_agent', 'write_github', mock=True)
        print('HATA: Bunu kabul etmemeli!')
    except PermissionError as e:
        print(f'Test 3 OK: Reddedildi → {e}')
