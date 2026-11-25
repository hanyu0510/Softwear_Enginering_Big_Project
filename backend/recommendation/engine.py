"""确定性筛选、结构化组合与模型结果复核。"""
from __future__ import annotations

import itertools
from collections import defaultdict

from .contracts import CATEGORIES, COLORS, SCENES, SEASONS, SOURCES, STYLES, BusinessError
from .config import load_weights

WEIGHTS = load_weights()
NEUTRAL = {'白', '米白', '黑', '灰', '深灰', '浅灰', '米', '卡其'}
WARM = {'棕', '焦糖', '巧克力', '咖', '卡其', '米', '黄', '橙', '红'}
COOL = {'蓝', '浅蓝', '藏青', '绿', '橄榄绿', '紫', '银', '牛仔蓝'}


def validate_item(item: dict) -> bool:
    """不完整标签可用；身份、状态、来源及类别为硬约束。"""
    if item.get('source') not in SOURCES or item.get('category') not in CATEGORIES:
        return False
    if item.get('verify_status') != 'confirmed' or item.get('deleted'):
        return False
    if not isinstance(item.get('id'), str) or not item['id']:
        return False
    if item['source'] == 'wish' and not (item.get('available') and item.get('source_visibility') == 'public'):
        return False
    if item.get('warmth') is not None and (type(item['warmth']) is not int or not 1 <= item['warmth'] <= 5):
        return False
    for field, allowed in (('season', SEASONS), ('style', STYLES), ('occasion', SCENES)):
        if item.get(field) is not None and (not isinstance(item[field], list) or
                                            any(not isinstance(v, str) or v not in allowed for v in item[field])):
            return False
    return True


def _color(item: dict) -> str | None:
    color = item.get('color')
    return color if color in COLORS else None


def _target_warmth(weather: dict | None) -> float:
    if not weather:
        return 3
    low, high = weather['temperatureMinC'], weather['temperatureMaxC']
    return 1 if high >= 29 else 2 if high >= 23 else 3 if low >= 12 else 4 if low >= 3 else 5


def item_score(item: dict, parsed: dict, weather: dict | None, preferences: dict, feedback: list[dict]) -> float:
    target = _target_warmth(weather)
    warmth = item.get('warmth')
    weather_score = 0.5 if warmth is None else max(0, 1 - abs(warmth - target) / 4)
    season = item.get('season') or []
    if weather and season:
        low, high = weather['temperatureMinC'], weather['temperatureMaxC']
        expected = {'winter'} if high <= 12 else {'summer'} if low >= 24 else {'spring', 'autumn'}
        weather_score = min(1, weather_score + (0.08 if expected.intersection(season) else 0))
    occasion = item.get('occasion') or []
    scene = parsed['scene']
    occasion_score = 0.5 if not scene or not occasion else (1 if scene in occasion else 0.25)
    tags = item.get('style') or []
    desired = parsed['style_tags'] or preferences.get('styles') or []
    style_score = 0.5 if not desired or not tags else (1 if set(tags) & set(desired) else 0.25)
    color = _color(item)
    family = set(parsed['color_family'])
    color_score = 0.5 if not family or not color else (1 if color in family else 0.65 if color in NEUTRAL else 0.25)
    avoid = set(preferences.get('avoid_colors') or [])
    preference_score = 0.2 if color in avoid else 0.75 if item.get('is_favorite') else 0.5
    for row in feedback:
        if color and color in row.get('colors', []):
            preference_score += 0.1 if row['preference'] == 'like' else -0.1
    preference_score = max(0, min(1, preference_score))
    walking = parsed['scene_attrs']['walking']
    practicality = 1 if walking < 4 or item['category'] != 'shoes' else (1 if (warmth or 3) <= 3 else 0.35)
    if (weather and (weather.get('rainProbability') or 0) >= 60 and item['category'] == 'shoes'
            and any(word in (item.get('material') or '') for word in ('麂皮', '绒面'))):
        practicality = min(practicality, 0.2)
    return sum(WEIGHTS[k] * v for k, v in {
        'weather': weather_score, 'occasion': occasion_score, 'style': style_score,
        'color': color_score, 'preference': preference_score, 'practicality': practicality,
        'completeness': 0.5}.items())


def candidate_score(items: list[dict], parsed: dict, weather: dict | None, preferences: dict,
                    feedback: list[dict]) -> float:
    if not items:
        return 0
    score = sum(item_score(i, parsed, weather, preferences, feedback) for i in items) / len(items)
    colors = [_color(i) for i in items if _color(i)]
    if len(colors) > 1 and (set(colors) <= WARM or set(colors) <= COOL or any(c in NEUTRAL for c in colors)):
        score += 0.07
    categories = {i['category'] for i in items}
    if {'tops', 'bottoms', 'shoes'} <= categories or {'dress', 'shoes'} <= categories:
        score += 0.08
    if weather:
        low, high = weather['temperatureMinC'], weather['temperatureMaxC']
        if high - low >= 8 or low <= 12:
            score += 0.08 if 'outerwear' in categories else -0.08
        if high >= 29 and 'outerwear' in categories:
            score -= 0.15
    return round(score, 4)


def generate(items: list[dict], parsed: dict, weather: dict | None, preferences: dict,
             feedback: list[dict], locks: list[dict], exclude: set[tuple[str, str]] | None = None) -> list[dict]:
    """每类取 Top 4，最多返回 10 套；锁定项不可被软评分挤掉。"""
    usable = [i for i in items if validate_item(i)]
    by_key = {(i['source'], i['id']): i for i in usable}
    locked_keys = {(i['source'], i['id']) for i in locks}
    if not locked_keys <= set(by_key):
        raise BusinessError(40401, '锁定单品不可用或无权访问', 404)
    if len(usable) == 0:
        return []
    grouped = defaultdict(list)
    for item in usable:
        grouped[item['category']].append(item)
    for category in grouped:
        grouped[category].sort(key=lambda i: -item_score(i, parsed, weather, preferences, feedback))
        kept = grouped[category][:4]
        kept.extend(i for i in grouped[category] if (i['source'], i['id']) in locked_keys and i not in kept)
        grouped[category] = kept
    cold = weather and (weather['temperatureMinC'] <= 12 or weather['temperatureMaxC'] - weather['temperatureMinC'] >= 8)
    templates = [('tops','bottoms','shoes'), ('dress','shoes')]
    if cold or grouped['outerwear']:
        templates = [('tops','bottoms','outerwear','shoes'), ('dress','outerwear','shoes')] + templates
    choices = []
    for template in templates:
        pools = [grouped[c] for c in template]
        if any(not pool for pool in pools):
            continue
        for combo in itertools.product(*pools):
            combo = list(combo)
            optional_locks = [by_key[k] for k in locked_keys if by_key[k]['category'] in ('bag', 'accessory')]
            combo += optional_locks
            keys = {(i['source'], i['id']) for i in combo}
            if len(keys) != len(combo) or not locked_keys <= keys:
                continue
            choices.append(combo)
            if len(choices) >= 300:
                break
    if not choices:
        partial = list(by_key[k] for k in locked_keys)
        for category in ('tops','bottoms','shoes','outerwear','bag','accessory'):
            if category not in {i['category'] for i in partial} and grouped[category]:
                partial.append(grouped[category][0])
            if len(partial) == 5:
                break
        choices = [partial]
    enriched = []
    seen = set()
    for combo in choices:
        if len(combo) < 5:
            for extra in grouped['bag'][:1] + grouped['accessory'][:1]:
                if len(combo) >= 5:
                    break
                if (extra['source'], extra['id']) not in {(i['source'], i['id']) for i in combo}:
                    combo = combo + [extra]
        key = frozenset((i['source'], i['id']) for i in combo)
        if key in seen or not locked_keys <= key:
            continue
        seen.add(key)
        score = candidate_score(combo, parsed, weather, preferences, feedback)
        if exclude and key == frozenset(exclude):
            score -= 0.35
        enriched.append({'items': combo, 'score': score})
    enriched.sort(key=lambda c: -c['score'])
    return enriched[:10]


def validate_rank(value: object, candidates: list[dict], locks: list[dict]) -> tuple[dict, str, list[str]]:
    """模型只能选候选索引；所有结果仍由服务端从合法候选重新构建。"""
    if not isinstance(value, dict) or type(value.get('candidateIndex')) is not int:
        raise ValueError('模型候选索引无效')
    index = value['candidateIndex']
    if not 0 <= index < len(candidates):
        raise ValueError('模型选择了非法候选')
    reason, tips = value.get('reason'), value.get('local_tips')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValueError('模型推荐理由无效')
    if not isinstance(tips, list) or len(tips) > 3 or any(not isinstance(x, str) or len(x) > 150 for x in tips):
        raise ValueError('模型当地建议无效')
    combo = candidates[index]
    keys = [(i['source'], i['id']) for i in combo['items']]
    if len(keys) != len(set(keys)) or not {(x['source'], x['id']) for x in locks} <= set(keys):
        raise ValueError('模型结果未保留合法锁定项')
    return combo, reason.strip(), tips
