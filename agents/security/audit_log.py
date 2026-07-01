import os
import uuid
import datetime
from typing import Optional

try:
    from google.cloud import firestore as _firestore
except ImportError:
    _firestore = None

FIRESTORE_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')

# audit_trail koleksiyonu — sadece append, hiç update/delete yok


def log_action(
    agent_name: str,
    action_type: str,
    target: str,
    result: str,
    metadata: Optional[dict] = None,
    mock: bool = True
) -> str:
    """
    Her dış etkili aksiyonu immutable audit_trail koleksiyonuna yazar.
    Aksiyon türleri: 'send_email', 'post_linkedin', 'post_instagram',
                     'create_github_issue', 'create_pull_request',
                     'send_calendar_invite', 'firestore_write'
    Returns: audit_id
    """
    audit_id = str(uuid.uuid4())
    record = {
        'audit_id':   audit_id,
        'agent_name': agent_name,
        'action_type': action_type,
        'target':     target,
        'result':     result,
        'metadata':   metadata or {},
        'timestamp':  datetime.datetime.utcnow().isoformat(),
        # Değiştirilemez olduğunu belirtmek için
        '_immutable': True,
        '_version': 1,
    }

    print(f'[AUDIT] {agent_name} | {action_type} → {target} | {result} | id={audit_id[:8]}')

    if mock:
        return audit_id

    if _firestore and FIRESTORE_PROJECT:
        try:
            db = _firestore.Client(project=FIRESTORE_PROJECT)
            # Document ID olarak audit_id kullan — overwrite olmaz
            db.collection('audit_trail').document(audit_id).create(record)
        except Exception as e:
            # create() var olan doc üzerine hata fırlatır — güvenli
            print(f'[AUDIT] Firestore yazma hatasi: {e}')

    return audit_id


def get_audit_trail(
    agent_name: Optional[str] = None,
    action_type: Optional[str] = None,
    days: int = 7,
    mock: bool = True
) -> list[dict]:
    """
    Audit kayıtlarını filtreli getir.
    Returns: [{audit_id, agent_name, action_type, target, result, timestamp}, ...]
    """
    if mock:
        return [
            {
                'audit_id': str(uuid.uuid4()),
                'agent_name': 'sponsor_outreach_agent',
                'action_type': 'send_email',
                'target': 'company@example.com',
                'result': 'sent',
                'timestamp': (datetime.datetime.utcnow() - datetime.timedelta(hours=2)).isoformat(),
            },
            {
                'audit_id': str(uuid.uuid4()),
                'agent_name': 'content_generator',
                'action_type': 'post_linkedin',
                'target': 'AGU Formula Student LinkedIn',
                'result': 'posted',
                'timestamp': (datetime.datetime.utcnow() - datetime.timedelta(hours=5)).isoformat(),
            },
            {
                'audit_id': str(uuid.uuid4()),
                'agent_name': 'structural_analysis_agent',
                'action_type': 'create_github_issue',
                'target': 'jasstt/formula-student-autonomus',
                'result': 'created:#42',
                'timestamp': (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat(),
            },
        ]

    records = []
    if _firestore and FIRESTORE_PROJECT:
        since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        try:
            db = _firestore.Client(project=FIRESTORE_PROJECT)
            q = db.collection('audit_trail').where('timestamp', '>=', since.isoformat())
            if agent_name:
                q = q.where('agent_name', '==', agent_name)
            if action_type:
                q = q.where('action_type', '==', action_type)
            records = [d.to_dict() for d in q.stream()]
        except Exception as e:
            print(f'[AUDIT] Sorgu hatasi: {e}')
    return records


if __name__ == '__main__':
    print('=== AUDIT LOG TEST ===')
    aid = log_action('sponsor_outreach_agent', 'send_email', 'info@bmw.com', 'sent', mock=True)
    print('log_action OK, id:', aid[:8])
    trail = get_audit_trail(mock=True)
    print('get_audit_trail OK, records:', len(trail))
