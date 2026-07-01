import os
import datetime
from typing import Optional

try:
    from google.cloud import firestore as _firestore
except ImportError:
    _firestore = None

FIRESTORE_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')


def get_decision_trace(decision_id: str, mock: bool = True) -> list[dict]:
    """
    Bir kararın tüm parent zincirini geriye doğru izler.
    Returns: [root_decision, ..., leaf_decision] sırasında dict listesi
    """
    if mock:
        # Mock: yapay zincir
        import uuid
        parent_id = str(uuid.uuid4())
        return [
            {
                'decision_id': parent_id,
                'agent_name': 'telemetry_stream',
                'input_summary': 'FC_TEMP sensor reading 76.2°C',
                'reasoning': 'Raw sensor data above threshold',
                'confidence': 0.99,
                'model_used': 'rule-based',
                'timestamp': (datetime.datetime.utcnow() - datetime.timedelta(seconds=2)).isoformat(),
                'parent_decision_id': None,
            },
            {
                'decision_id': decision_id,
                'agent_name': 'chief_engineer',
                'input_summary': 'FC thermal anomaly + battery_soc=0.35',
                'reasoning': 'FC sıcaklığı 76°C > 75°C eşiği, termal koruma aktif',
                'confidence': 0.82,
                'model_used': 'gemini-2.5-flash',
                'timestamp': datetime.datetime.utcnow().isoformat(),
                'parent_decision_id': parent_id,
            }
        ]

    if not (_firestore and FIRESTORE_PROJECT):
        return []

    chain = []
    current_id = decision_id
    visited = set()

    try:
        db = _firestore.Client(project=FIRESTORE_PROJECT)
        while current_id and current_id not in visited:
            visited.add(current_id)
            doc = db.collection('decisions').document(current_id).get()
            if not doc.exists:
                break
            data = doc.to_dict()
            chain.insert(0, data)  # en üste ekle (root önce)
            current_id = data.get('parent_decision_id')
    except Exception as e:
        print(f'[DASHBOARD] Trace hatasi: {e}')

    return chain


def get_cost_summary(days: int = 7, mock: bool = True) -> dict:
    """
    Son N günün token harcaması, agent bazında kırılım.
    Returns: {total_tokens, by_agent: {agent: tokens}, estimated_usd}
    """
    if mock:
        return {
            'period_days': days,
            'total_tokens': 142500,
            'by_agent': {
                'chief_engineer':        85000,
                'content_generator':     32000,
                'code_improvement_agent': 18000,
                'sponsor_outreach':       7500,
            },
            'by_model': {
                'gemini-2.5-flash': 120000,
                'gemini-1.5-pro':    22500,
                'rule-based':            0,
                'lstm':                  0,
            },
            'estimated_usd': round(120000 * 0.000001 + 22500 * 0.000003, 4),
            'generated_at': datetime.datetime.utcnow().isoformat(),
        }

    if not (_firestore and FIRESTORE_PROJECT):
        return {'error': 'Firestore not available'}

    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    by_agent: dict = {}
    by_model: dict = {}
    total = 0

    try:
        db = _firestore.Client(project=FIRESTORE_PROJECT)
        docs = (
            db.collection('decisions')
            .where('timestamp', '>=', since.isoformat())
            .stream()
        )
        for doc in docs:
            d = doc.to_dict()
            tokens = d.get('tokens_spent', 0)
            agent = d.get('agent_name', 'unknown')
            model = d.get('model_used', 'unknown')
            total += tokens
            by_agent[agent] = by_agent.get(agent, 0) + tokens
            by_model[model] = by_model.get(model, 0) + tokens
    except Exception as e:
        print(f'[DASHBOARD] Cost sorgu hatasi: {e}')

    flash_tokens = by_model.get('gemini-2.5-flash', 0) + by_model.get('gemini-1.5-flash', 0)
    pro_tokens = by_model.get('gemini-1.5-pro', 0)
    estimated_usd = round(flash_tokens * 0.000001 + pro_tokens * 0.000003, 4)

    return {
        'period_days': days,
        'total_tokens': total,
        'by_agent': by_agent,
        'by_model': by_model,
        'estimated_usd': estimated_usd,
        'generated_at': datetime.datetime.utcnow().isoformat(),
    }


def get_confidence_distribution(mock: bool = True) -> dict:
    """
    Tüm kararların confidence dağılımı.
    Returns: {bins, low_confidence_pct, warning_threshold_exceeded}
    """
    if mock:
        return {
            'total_decisions': 248,
            'bins': {
                '0.0-0.5':  12,   # düşük
                '0.5-0.7':  45,
                '0.7-0.9': 148,
                '0.9-1.0':  43,
            },
            'low_confidence_pct': round(12 / 248 * 100, 1),  # 4.8%
            'warning_threshold_exceeded': False,  # eşik: >%15
            'avg_confidence': 0.743,
            'generated_at': datetime.datetime.utcnow().isoformat(),
        }

    if not (_firestore and FIRESTORE_PROJECT):
        return {'error': 'Firestore not available'}

    bins = {'0.0-0.5': 0, '0.5-0.7': 0, '0.7-0.9': 0, '0.9-1.0': 0}
    total = 0
    conf_sum = 0.0

    try:
        db = _firestore.Client(project=FIRESTORE_PROJECT)
        for doc in db.collection('decisions').stream():
            d = doc.to_dict()
            c = d.get('confidence', 0.5)
            total += 1
            conf_sum += c
            if c < 0.5:      bins['0.0-0.5'] += 1
            elif c < 0.7:    bins['0.5-0.7'] += 1
            elif c < 0.9:    bins['0.7-0.9'] += 1
            else:            bins['0.9-1.0'] += 1
    except Exception as e:
        print(f'[DASHBOARD] Confidence sorgu hatasi: {e}')

    low_pct = round(bins['0.0-0.5'] / max(total, 1) * 100, 1)
    return {
        'total_decisions': total,
        'bins': bins,
        'low_confidence_pct': low_pct,
        'warning_threshold_exceeded': low_pct > 15,
        'avg_confidence': round(conf_sum / max(total, 1), 3),
        'generated_at': datetime.datetime.utcnow().isoformat(),
    }
