import os
import datetime
import json
from typing import Optional, List

try:
    from google.cloud import firestore as _firestore
except ImportError:
    _firestore = None

FIRESTORE_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')

# In-memory fallback (Firestore yoksa veya mock modda)
_local_patterns: dict = {}  # {category: [pattern_dict, ...]}


class LongTermMemory:
    """
    Kalıcı pattern ve geçmiş bilgisi belleği.
    
    Kategoriler:
      - 'sponsor_behavior'    → Şirket yanıt geçmişi
      - 'lap_history'         → Geçmiş tur verileri
      - 'component_history'   → Parça değişiklik geçmişi
      - 'anomaly_history'     → Sensör anomali geçmişi
    
    Basit keyword/tarih bazlı filtreleme — embedding gerektirmez.
    """

    def __init__(self):
        self._db = None
        if _firestore and FIRESTORE_PROJECT:
            try:
                self._db = _firestore.Client(project=FIRESTORE_PROJECT)
            except Exception as e:
                print(f'[LONG_TERM] Firestore bağlantı hatasi: {e}')

    def store_pattern(self, category: str, pattern: dict, mock: bool = True) -> str:
        """
        Yeni bir pattern kaydeder.
        Returns: pattern doc ID
        """
        import uuid
        doc_id = str(uuid.uuid4())
        record = {
            'doc_id': doc_id,
            'category': category,
            'pattern': pattern,
            'stored_at': datetime.datetime.utcnow().isoformat(),
        }

        print(f'[LONG_TERM] store_pattern: {category} | {list(pattern.keys())[:3]}')

        if mock:
            if category not in _local_patterns:
                _local_patterns[category] = []
            _local_patterns[category].append(record)
            return doc_id

        if self._db:
            try:
                self._db.collection('long_term_patterns').document(doc_id).set(record)
            except Exception as e:
                print(f'[LONG_TERM] Firestore yazma hatasi: {e}')
        return doc_id

    def query_similar_patterns(
        self,
        category: str,
        query: dict,
        top_k: int = 5,
        mock: bool = True
    ) -> List[dict]:
        """
        Kategoriye göre benzer pattern'ları döner.
        Basit keyword/değer bazlı skorlama kullanır.
        
        Örnek:
          category='sponsor_behavior',
          query={'sector': 'automotive', 'company_size': 'large'}
          → O sektördeki büyük şirketlerin yanıt geçmişi
        """
        if mock:
            # Mock: önceden saklanmış + varsayılan örnekler
            mock_data = {
                'sponsor_behavior': [
                    {'company': 'BMW', 'sector': 'automotive', 'avg_response_days': 12,
                     'response_rate': 0.35, 'company_size': 'large'},
                    {'company': 'Bosch', 'sector': 'automotive', 'avg_response_days': 8,
                     'response_rate': 0.55, 'company_size': 'large'},
                    {'company': 'TechStartup', 'sector': 'tech', 'avg_response_days': 3,
                     'response_rate': 0.72, 'company_size': 'small'},
                ],
                'lap_history': [
                    {'lap': 1, 'segment': 'hairpin', 'fc_ratio': 0.65, 'speed_kmh': 38, 'time_s': 91.2},
                    {'lap': 2, 'segment': 'hairpin', 'fc_ratio': 0.68, 'speed_kmh': 40, 'time_s': 88.5},
                    {'lap': 3, 'segment': 'hairpin', 'fc_ratio': 0.70, 'speed_kmh': 41, 'time_s': 87.1},
                ],
                'component_history': [
                    {'component': 'FC Stack', 'change': 'replaced', 'date': '2025-03-15', 'reason': 'thermal degradation'},
                    {'component': 'Rear Motor', 'change': 'added', 'date': '2025-06-01', 'reason': 'Emrax 228 upgrade'},
                ],
                'anomaly_history': [
                    {'type': 'thermal', 'sensor': 'FC_TEMP', 'value': 76.2, 'date': '2025-05-20'},
                    {'type': 'pressure', 'sensor': 'H2_PRESSURE', 'value': 285.0, 'date': '2025-04-10'},
                ],
            }
            candidates = mock_data.get(category, [])
            # Basit skorlama: query key/value eşleşme sayısı
            scored = []
            for c in candidates:
                score = sum(1 for k, v in query.items() if c.get(k) == v)
                scored.append((score, c))
            scored.sort(key=lambda x: -x[0])
            return [item for _, item in scored[:top_k]]

        if not self._db:
            return []

        results = []
        try:
            q = self._db.collection('long_term_patterns').where('category', '==', category)
            docs = q.order_by('stored_at', direction=_firestore.Query.DESCENDING).limit(top_k * 3).stream()
            candidates = [d.to_dict() for d in docs]

            # Keyword skorlama
            scored = []
            for doc in candidates:
                p = doc.get('pattern', {})
                score = sum(1 for k, v in query.items() if p.get(k) == v)
                scored.append((score, doc))
            scored.sort(key=lambda x: -x[0])
            results = [item['pattern'] for _, item in scored[:top_k]]
        except Exception as e:
            print(f'[LONG_TERM] Sorgu hatasi: {e}')
        return results


if __name__ == '__main__':
    print('=== LONG TERM MEMORY TEST ===')
    mem = LongTermMemory()
    
    # Pattern sakla
    doc_id = mem.store_pattern('sponsor_behavior', {
        'company': 'TestCorp', 'sector': 'automotive',
        'response_days': 14, 'company_size': 'large'
    }, mock=True)
    print('store_pattern OK, id:', doc_id[:8])
    
    # Benzer pattern sorgula
    results = mem.query_similar_patterns(
        'sponsor_behavior',
        {'sector': 'automotive', 'company_size': 'large'},
        top_k=3, mock=True
    )
    print(f'query_similar_patterns OK, {len(results)} sonuc bulundu')
    for r in results:
        print(f'  - {r.get("company", r.get("sector", "?"))}')
    
    # Tur geçmişi sorgula
    laps = mem.query_similar_patterns(
        'lap_history',
        {'segment': 'hairpin'},
        top_k=5, mock=True
    )
    print(f'lap_history sorgusu OK, {len(laps)} tur bulundu')
    
    print('LongTermMemory testi GECTI')
