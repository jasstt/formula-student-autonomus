import os
import time
from enum import Enum
from typing import Optional

# Model fiyatları (USD / 1K token, Temmuz 2025 yaklaşık)
MODEL_COST_PER_1K = {
    'gemini-2.5-flash': 0.00010,
    'gemini-1.5-flash': 0.00010,
    'gemini-1.5-pro':   0.00350,
    'rule-based':       0.0,
    'lstm':             0.0,
}


class TaskComplexity(Enum):
    TRIVIAL  = 'trivial'   # keyword eşleştirme, basit hesap, if/else kural
    MODERATE = 'moderate'  # sınıflandırma, kısa üretim, tek adım
    COMPLEX  = 'complex'   # çok adımlı akıl yürütme, sentez, güvenlik kararı


# ── Görev → Karmaşıklık haritası ─────────────────────────────
TASK_COMPLEXITY_MAP: dict[str, TaskComplexity] = {
    # TRIVIAL — LLM çağrısı yapma
    'arxiv_importance_scoring':   TaskComplexity.TRIVIAL,
    'sensor_threshold_check':     TaskComplexity.TRIVIAL,
    'battery_low_check':          TaskComplexity.TRIVIAL,
    'component_weight_calc':      TaskComplexity.TRIVIAL,
    'h2_ppm_alert':               TaskComplexity.TRIVIAL,

    # MODERATE — ucuz, hızlı
    'sponsor_email_classification': TaskComplexity.MODERATE,
    'social_media_caption':         TaskComplexity.MODERATE,
    'lap_report_summary':           TaskComplexity.MODERATE,
    'sponsor_response_prediction':  TaskComplexity.MODERATE,
    'code_style_lint':              TaskComplexity.MODERATE,

    # COMPLEX — pahalı, güçlü
    'power_optimization_decision':  TaskComplexity.COMPLEX,
    'safety_check_decision':        TaskComplexity.COMPLEX,
    'route_decision':               TaskComplexity.COMPLEX,
    'code_improvement_analysis':    TaskComplexity.COMPLEX,
    'structural_compliance_review': TaskComplexity.COMPLEX,
}

# ── Karmaşıklık → Model haritası ─────────────────────────────
COMPLEXITY_MODEL_MAP: dict[TaskComplexity, Optional[str]] = {
    TaskComplexity.TRIVIAL:  None,                  # LLM yok
    TaskComplexity.MODERATE: 'gemini-2.5-flash',    # hızlı + ucuz
    TaskComplexity.COMPLEX:  'gemini-2.5-flash',    # şimdilik flash (pro quota olunca değiştir)
}


def route_model(
    task_type: str,
    complexity_override: Optional[TaskComplexity] = None,
    mock: bool = True
) -> dict:
    """
    Görev türüne göre kullanılacak model ve maliyeti belirler.

    Returns:
        {
          task_type, complexity, model, use_llm,
          estimated_cost_per_call, routing_reason
        }
    """
    complexity = complexity_override or TASK_COMPLEXITY_MAP.get(
        task_type, TaskComplexity.MODERATE  # bilinmeyeni moderate varsay
    )
    model = COMPLEXITY_MODEL_MAP[complexity]
    use_llm = model is not None
    cost = MODEL_COST_PER_1K.get(model or 'rule-based', 0.0)

    # Routing gerekçesi
    if complexity == TaskComplexity.TRIVIAL:
        reason = 'Kural tabanlı — LLM token tasarrufu'
    elif complexity == TaskComplexity.MODERATE:
        reason = f'Moderate görev — {model} (hızlı/ucuz)'
    else:
        reason = f'Karmaşık karar — {model} (güçlü)'

    result = {
        'task_type': task_type,
        'complexity': complexity.value,
        'model': model,
        'use_llm': use_llm,
        'estimated_cost_per_1k_tokens_usd': cost,
        'routing_reason': reason,
    }

    print(f'[ROUTER] {task_type} → {complexity.value.upper()} → '
          f'{model or "rule-based"} | {reason}')
    return result


def estimate_cost(tokens: int, model: str) -> float:
    """Token sayısı ve modele göre USD maliyet tahmini."""
    rate = MODEL_COST_PER_1K.get(model, 0.0)
    return round(tokens / 1000 * rate, 6)


if __name__ == '__main__':
    print('=== MODEL ROUTER TEST ===')
    tasks = [
        'arxiv_importance_scoring',
        'social_media_caption',
        'power_optimization_decision',
        'unknown_task_type',
    ]
    for t in tasks:
        r = route_model(t)
        print(f'  → model={r["model"]} | use_llm={r["use_llm"]}\n')
