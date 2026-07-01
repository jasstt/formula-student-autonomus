import os
import datetime
from typing import Optional

try:
    from google.cloud import firestore as _firestore
except ImportError:
    _firestore = None

try:
    from agents.eval.decision_critic import evaluate_decision
except ImportError:
    evaluate_decision = None

FIRESTORE_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'formula-student-autonomus')


def generate_weekly_report(mock: bool = True) -> str:
    """
    Son 7 günün kararlarını değerlendirir.
    Markdown rapor üretir, Slack'e gönderir.
    Cloud Scheduler: her Pazartesi 09:00
    """
    now = datetime.datetime.utcnow()
    since = now - datetime.timedelta(days=7)

    if mock:
        decisions = [
            {'decision_id': f'mock-{i}', 'agent_name': ag, 'confidence': c,
             'reasoning': 'Test reasoning text that is long enough', 'tags': []}
            for i, (ag, c) in enumerate([
                ('chief_engineer', 0.82), ('chief_engineer', 0.91),
                ('content_generator', 1.0), ('sponsor_outreach', 0.63),
                ('structural_analysis', 0.77), ('chief_engineer', 0.55),
                ('event_router', 0.88), ('content_generator', 0.72),
            ])
        ]
    else:
        decisions = []
        if _firestore and FIRESTORE_PROJECT:
            try:
                db = _firestore.Client(project=FIRESTORE_PROJECT)
                docs = (
                    db.collection('decisions')
                    .where('timestamp', '>=', since.isoformat())
                    .stream()
                )
                decisions = [d.to_dict() for d in docs]
            except Exception as e:
                print(f'[WEEKLY EVAL] Firestore hatasi: {e}')

    if not decisions:
        return 'Rapor: Son 7 günde karar bulunamadı.'

    # İstatistikler
    total = len(decisions)
    conf_avg = sum(d.get('confidence', 0) for d in decisions) / total
    by_agent: dict[str, int] = {}
    all_flags: dict[str, int] = {}  # agent -> flag sayısı

    for d in decisions:
        ag = d.get('agent_name', 'unknown')
        by_agent[ag] = by_agent.get(ag, 0) + 1

    # Critic değerlendirmesi
    flagged = 0
    most_flagged_agent = '—'
    max_flags = 0
    agent_flags: dict[str, int] = {}

    if evaluate_decision:
        for d in decisions:
            result = evaluate_decision(d, mock=True)
            if result.flags:
                flagged += 1
                ag = d.get('agent_name', 'unknown')
                agent_flags[ag] = agent_flags.get(ag, 0) + len(result.flags)

    if agent_flags:
        most_flagged_agent = max(agent_flags, key=lambda k: agent_flags[k])
        max_flags = agent_flags[most_flagged_agent]

    flag_rate = round(flagged / total * 100, 1)

    # Markdown rapor
    report = f"""# Haftalık Agent Eval Raporu
**Dönem:** {since.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}  
**Oluşturma:** {now.strftime('%Y-%m-%d %H:%M')} UTC

## Özet
| Metrik | Değer |
|--------|-------|
| Toplam Karar | {total} |
| Ort. Confidence | {conf_avg:.3f} |
| Flag Oranı | {flag_rate}% |
| En Çok Flaglanan | {most_flagged_agent} ({max_flags} flag) |

## Agent Bazında Karar Dağılımı
| Agent | Karar Sayısı |
|-------|-------------|
""" + ''.join(f'| {ag} | {cnt} |\n' for ag, cnt in sorted(by_agent.items(), key=lambda x: -x[1])) + f"""

## Değerlendirme
{'⚠️ Flag oranı yüksek (%{flag_rate} > %15) — Agent kalitesi incelenmeli!' if flag_rate > 15 else '✅ Flag oranı normal aralıkta.'}
{'⚠️ Ortalama confidence düşük (< 0.6) — Model kalibrasyonu kontrol edilmeli.' if conf_avg < 0.6 else ''}

*Rapor otomatik üretildi — Eval Agent*
"""

    # Dosyaya kaydet
    os.makedirs('reports', exist_ok=True)
    filename = f'reports/weekly_eval_{now.strftime("%Y%m%d")}.md'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'[WEEKLY EVAL] Rapor kaydedildi: {filename}')

    # Slack bildirimi
    slack_msg = (f'📊 Haftalık Eval Raporu | {total} karar | '
                 f'Conf: {conf_avg:.2f} | Flag: {flag_rate}% | '
                 f'En çok: {most_flagged_agent}')
    print(f'[SLACK] #fcev-eval: {slack_msg}')

    return report


if __name__ == '__main__':
    print(generate_weekly_report(mock=True)[:500])
