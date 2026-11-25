"""首版规则权重；可用环境变量中的 JSON 覆盖，所有权重和应为 1。"""
import json
import os

DEFAULT_WEIGHTS = {'weather': 0.25, 'occasion': 0.15, 'style': 0.16, 'color': 0.12,
                   'preference': 0.12, 'practicality': 0.12, 'completeness': 0.08}


def load_weights():
    raw = os.getenv('RECOMMENDATION_WEIGHTS')
    weights = json.loads(raw) if raw else DEFAULT_WEIGHTS
    if (not isinstance(weights, dict) or set(weights) != set(DEFAULT_WEIGHTS) or
            any(type(v) not in (float, int) or v < 0 for v in weights.values()) or
            abs(sum(weights.values()) - 1) > 1e-6):
        raise ValueError('RECOMMENDATION_WEIGHTS 必须含全部非负权重且总和为 1')
    return weights
