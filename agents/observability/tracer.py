import os
import uuid
import datetime
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    from google.cloud import firestore as _firestore
except ImportError:
    _firestore = None

FIRESTORE_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')

@dataclass
class AgentDecision:
    agent_name: str
    input_summary: str
    reasoning: str
    output: dict
    confidence: float           # 0.0 - 1.0
    model_used: str             # 'gemini-2.5-flash', 'rule-based', 'lstm', 'gemini-1.5-pro'
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    tokens_spent: int = 0
    latency_ms: float = 0.0
    parent_decision_id: Optional[str] = None
    tags: list = field(default_factory=list)  # ['safety', 'power', 'sponsor'] etc.

    def to_dict(self) -> dict:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


def log_decision(decision: AgentDecision, mock: bool = True) -> str:
    """
    AgentDecision'i Firestore decisions koleksiyonuna yazar.
    Düşük confidence veya yüksek latency durumunda uyarı üretir.
    Returns: decision_id
    """
    data = decision.to_dict()

    # ── Kural tabanlı uyarı kontrolleri ─────────────────────
    if decision.confidence < 0.5:
        print(f'[TRACER] WARNING: {decision.agent_name} düşük güven skoru '
              f'{decision.confidence:.2f} — decision_id={decision.decision_id}')
        print(f'[SLACK] #fcev-alerts: ⚠️ Düşük confidence: '
              f'{decision.agent_name} ({decision.confidence:.2f})')

    if decision.latency_ms > 5000:
        print(f'[TRACER] PERFORMANCE_WARNING: {decision.agent_name} '
              f'{decision.latency_ms:.0f}ms — decision_id={decision.decision_id}')

    print(f'[TRACER] {decision.agent_name} | conf={decision.confidence:.2f} | '
          f'model={decision.model_used} | latency={decision.latency_ms:.0f}ms | '
          f'id={decision.decision_id[:8]}')

    if mock:
        # Mock modda sadece yazdır, Firestore'a gitme
        return decision.decision_id

    if _firestore and FIRESTORE_PROJECT:
        try:
            db = _firestore.Client(project=FIRESTORE_PROJECT)
            db.collection('decisions').document(decision.decision_id).set(data)
        except Exception as e:
            print(f'[TRACER] Firestore yazma hatasi: {e}')

    return decision.decision_id
