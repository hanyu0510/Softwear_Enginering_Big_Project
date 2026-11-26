"""正式契约的边界校验；不接受客户端提供的 userId。"""
from __future__ import annotations

from datetime import date, timedelta

CATEGORIES = frozenset('tops bottoms outerwear dress shoes bag accessory other'.split())
SCENES = frozenset('commute date travel casual formal party sport'.split())
STYLES = frozenset('minimal street sweet formal casual vintage sporty'.split())
SEASONS = frozenset('spring summer autumn winter'.split())
COLORS = frozenset('白 米白 黑 灰 深灰 浅灰 棕 焦糖 巧克力 咖 卡其 米 黄 橙 红 粉 紫 蓝 浅蓝 藏青 绿 橄榄绿 银 金 牛仔蓝'.split())
SOURCES = frozenset(('owned', 'wish'))


class BusinessError(Exception):
    def __init__(self, code: int, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def object_body(value: object, allowed: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) - allowed:
        raise BusinessError(40001, '请求字段无效')
    return value


def optional_text(value: object, field: str, limit: int = 300) -> str:
    if value is None:
        return ''
    if not isinstance(value, str) or len(value) > limit:
        raise BusinessError(40001, f'{field} 必须是至多 {limit} 字的字符串')
    return value.strip()


def iso_date(value: object, field: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise BusinessError(40001, f'{field} 必须为 YYYY-MM-DD')
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise BusinessError(40001, f'{field} 日期无效') from None
    if result.isoformat() != value:
        raise BusinessError(40001, f'{field} 必须为 YYYY-MM-DD')
    return result


def parse_request(value: object, today: date) -> dict:
    data = object_body(value, {'sceneText', 'styleText', 'destination', 'travelDate', 'date', 'wardrobeScope', 'locked_items'})
    scene = optional_text(data.get('sceneText'), 'sceneText')
    style = optional_text(data.get('styleText'), 'styleText')
    dest = data.get('destination')
    travel = data.get('travelDate')
    day = data.get('date')
    if (dest is None) != (travel is None):
        raise BusinessError(40001, 'destination 与 travelDate 必须同时提供')
    if dest is not None:
        object_body(dest, {'cityId', 'cityName'})
        if not isinstance(dest.get('cityId'), str) or not dest['cityId'].strip():
            raise BusinessError(40001, 'destination.cityId 无效')
        trip_day = iso_date(travel, 'travelDate')
        if trip_day < today:
            raise BusinessError(40001, 'travelDate 不能早于今天')
        if day is not None and iso_date(day, 'date') != trip_day:
            raise BusinessError(40001, 'date 与 travelDate 不一致')
        target = trip_day
    else:
        target = iso_date(day, 'date') if day is not None else today
        if target != today:
            raise BusinessError(40001, '本地推荐当前仅支持当日；旅行请提供 destination 与 travelDate')
    scope = data.get('wardrobeScope', 'owned')
    if scope not in ('owned', 'owned_and_wish'):
        raise BusinessError(40001, 'wardrobeScope 无效')
    locks = data.get('locked_items', [])
    if not isinstance(locks, list) or len(locks) > 5:
        raise BusinessError(40001, 'locked_items 无效')
    unique = set()
    for lock in locks:
        object_body(lock, {'source', 'id'})
        key = (lock.get('source'), lock.get('id'))
        if key[0] not in SOURCES or not isinstance(key[1], str) or not key[1] or key in unique:
            raise BusinessError(40001, 'locked_items 存在重复或非法单品')
        if key[0] == 'wish' and scope != 'owned_and_wish':
            raise BusinessError(40001, '当前衣橱范围不允许锁定心愿单品')
        unique.add(key)
    return {'sceneText': scene, 'styleText': style, 'destination': dest,
            'travelDate': travel, 'date': target.isoformat(), 'wardrobeScope': scope,
            'locked_items': locks}


def validate_parsed(value: object) -> dict:
    object_body(value, {'scene', 'scene_attrs', 'style_tags', 'color_family', 'style_note', 'low_confidence_fields'})
    if set(value) != {'scene', 'scene_attrs', 'style_tags', 'color_family', 'style_note', 'low_confidence_fields'}:
        raise ValueError('解析字段缺失')
    attrs = object_body(value['scene_attrs'], {'indoor', 'formality', 'walking', 'photoFriendly'})
    if set(attrs) != {'indoor', 'formality', 'walking', 'photoFriendly'}:
        raise ValueError('场景属性缺失')
    if value['scene'] is not None and (not isinstance(value['scene'], str) or value['scene'] not in SCENES):
        raise ValueError('场合枚举无效')
    if type(attrs['indoor']) is not bool or type(attrs['photoFriendly']) is not bool:
        raise ValueError('场景布尔值无效')
    if any(type(attrs[k]) is not int or not 1 <= attrs[k] <= 5 for k in ('formality', 'walking')):
        raise ValueError('场景数值无效')
    if not isinstance(value['style_tags'], list) or any(not isinstance(s, str) or s not in STYLES for s in value['style_tags']):
        raise ValueError('风格枚举无效')
    if not isinstance(value['color_family'], list) or any(not isinstance(c, str) or c not in COLORS for c in value['color_family']):
        raise ValueError('颜色白名单无效')
    if not isinstance(value['style_note'], str) or len(value['style_note']) > 300:
        raise ValueError('风格解释无效')
    permitted = {'scene', 'scene_attrs', 'style_tags', 'color_family', 'style_note'}
    if not isinstance(value['low_confidence_fields'], list) or any(not isinstance(x, str) or x not in permitted for x in value['low_confidence_fields']):
        raise ValueError('低置信度字段无效')
    return value


def neutral_parsed(note: str = '') -> dict:
    return {'scene': None, 'scene_attrs': {'indoor': False, 'formality': 2, 'walking': 3, 'photoFriendly': False},
            'style_tags': [], 'color_family': [], 'style_note': note, 'low_confidence_fields': []}
