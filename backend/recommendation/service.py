"""推荐工作流：解析、真实天气、候选、精排、安全复核、持久化。"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from .contracts import BusinessError, neutral_parsed, optional_text, parse_request, validate_parsed
from .engine import generate, validate_rank

CHINA_TZ = timezone(timedelta(hours=8))
STYLE_MAP = {
    '美拉德': (['vintage','casual'], ['棕','焦糖','巧克力']),
    'y2k': (['street','vintage'], ['银','粉']),
    '多巴胺': (['street','casual'], ['黄','橙','粉']),
    '老钱': (['minimal','formal'], ['米白','藏青','卡其']),
    '芭蕾': (['sweet'], ['粉','米白']),
    '工装': (['street','casual'], ['卡其','橄榄绿']),
    '港风': (['vintage'], ['红','黑','棕']),
    '极简': (['minimal'], ['黑','白','灰']),
    '冷淡': (['minimal'], ['黑','白','灰']),
}


def local_parse(scene: str, style: str) -> dict:
    """无模型时只解析明确的常见词；未知词标记低置信度。"""
    result = neutral_parsed()
    low = result['low_confidence_fields']
    s = scene.casefold()
    mapping = [
        (('面试','会议','正式'), 'formal', True, 5, 2),
        (('运动','跑步','健身'), 'sport', False, 1, 5),
        (('聚会','生日','派对','演唱会'), 'party', False, 3, 3),
        (('约会',), 'date', True, 3, 2),
        (('旅行','旅游','游玩'), 'travel', False, 2, 4),
        (('上班','通勤','学校','上课'), 'commute', True, 3, 3),
        (('咖啡馆','咖啡店'), 'casual', True, 2, 2),
        (('公园','野餐','散步'), 'casual', False, 2, 4),
    ]
    for words, category, indoor, formality, walking in mapping:
        if any(word in s for word in words):
            result['scene'] = category
            result['scene_attrs'].update(indoor=indoor, formality=formality, walking=walking)
            break
    if '拍照' in s or '拍' in s:
        result['scene_attrs']['photoFriendly'] = True
    if scene and result['scene'] is None:
        low.append('scene')
    t = style.casefold()
    for word, (tags, colors) in STYLE_MAP.items():
        if word in t:
            result['style_tags'], result['color_family'] = tags, colors
            break
    if style and not result['style_tags']:
        low += ['style_tags', 'color_family']
    result['style_note'] = ('已按常见场景和风格词作规则解析。' if not low else
                            '部分输入暂无法可靠理解，已使用基础搭配。')
    return validate_parsed(result)


def snapshot(item: dict) -> dict:
    return {'source': item['source'], 'id': item['id'], 'name': item.get('name') or '未命名单品',
            'imageUrl': item.get('image_url') or item.get('thumb_url') or ''}


def template_reason(items: list[dict], parsed: dict, weather: dict | None) -> str:
    if not items:
        return '衣橱中暂无已确认且可用的单品，请先添加并确认衣物。'
    named = '、'.join(i.get('name') or '未命名单品' for i in items[:4])
    parts = [f'选择了{named}，组成现有衣橱中可用的搭配。']
    categories = {i['category'] for i in items}
    if weather:
        low, high = weather['temperatureMinC'], weather['temperatureMaxC']
        if high - low >= 8 and 'outerwear' in categories:
            parts.append('早晚温差较大，外套便于叠穿和脱卸。')
        elif low <= 12 and 'outerwear' in categories:
            parts.append('最低气温偏低，增加外套保暖。')
        elif high >= 29:
            parts.append('最高气温较高，优先采用轻便组合。')
    colors = [i.get('color') for i in items if i.get('color')]
    if colors:
        parts.append('配色参考了衣橱中的' + '、'.join(dict.fromkeys(colors[:3])) + '。')
    if parsed['scene_attrs']['walking'] >= 4 and 'shoes' in categories:
        parts.append('步行需求较高，已将鞋类纳入搭配。')
    return ''.join(parts)


class RecommendationService:
    def __init__(self, wardrobe, city_weather, llm, store, *, today=None):
        self.wardrobe, self.city_weather, self.llm, self.store = wardrobe, city_weather, llm, store
        self.today = today or (lambda: datetime.now(CHINA_TZ).date())

    def parse(self, scene: str, style: str) -> tuple[dict, bool]:
        if not scene and not style:
            return neutral_parsed(), False
        if self.llm.configured:
            try:
                return self.llm.parse(scene, style), True
            except (RuntimeError, ValueError):
                pass
        return local_parse(scene, style), False

    def parse_preview(self, body: object) -> dict:
        if not isinstance(body, dict) or set(body) - {'sceneText','styleText'}:
            raise BusinessError(40001, '请求字段无效')
        return self.parse(optional_text(body.get('sceneText'), 'sceneText'),
                          optional_text(body.get('styleText'), 'styleText'))[0]

    def get_weather(self, city_id: str, day: date) -> dict:
        city = self.city_weather.resolve(city_id)
        if not city:
            raise BusinessError(50302, '目的地城市无法识别，请从城市搜索结果重选', 503)
        if day < self.today() or day > self.today() + timedelta(days=14):
            raise BusinessError(50301, '日期超出可用预报范围', 503)
        try:
            return self.city_weather.weather(city, day)
        except RuntimeError:
            raise BusinessError(50301, '天气暂不可用', 503) from None

    def generate(self, user_id: str, payload: object, *, previous: dict | None = None) -> dict:
        request = parse_request(payload, self.today())
        parsed, model_parsed = self.parse(request['sceneText'], request['styleText'])
        warnings = []
        if (request['sceneText'] or request['styleText']) and not model_parsed:
            warnings.append('模型解析未使用；按可识别的常见词进行规则解析')
        if parsed['low_confidence_fields']:
            warnings.append('部分场景或风格理解置信度低，请核对输入')
        dest = request['destination']
        if dest and parsed['scene'] is None:
            parsed['scene'] = 'travel'
            parsed['scene_attrs']['walking'] = max(parsed['scene_attrs']['walking'], 4)
        city_id = dest['cityId'] if dest else self.wardrobe.current_city_id(user_id)
        if dest and not self.city_weather.resolve(city_id):
            raise BusinessError(50302, '目的地城市无法识别，请从城市搜索结果重选', 503)
        weather = None
        if city_id:
            try:
                weather = self.get_weather(city_id, date.fromisoformat(request['date']))
            except BusinessError as error:
                if error.code == 50302 and dest:
                    raise
                warnings.append('未获取天气，仅供参考；请检查城市、日期或稍后重试')
        else:
            warnings.append('未确定当前城市，未获取天气，仅供参考；请选择城市')
        if weather and (weather.get('rainProbability') or 0) >= 60:
            warnings.append('降雨概率较高，建议携带雨具并注意鞋面防水')
        wardrobe = [i for i in self.wardrobe.items(user_id, request['wardrobeScope'] == 'owned_and_wish')
                    if i.get('user_id') == user_id]
        preferences = self.wardrobe.preferences(user_id)
        feedback = self.store.feedback_history(user_id)
        excluded = {(i['source'], i['id']) for i in previous['items']} if previous else None
        candidates = generate(wardrobe, parsed, weather, preferences, feedback,
                              request['locked_items'], excluded)
        chosen = candidates[0] if candidates else {'items': [], 'score': 0}
        model_status = 'rule_based'
        reason = template_reason(chosen['items'], parsed, weather)
        local_tips = []
        if candidates and self.llm.configured:
            shortlist = {}
            for candidate in candidates:
                for item in candidate['items']:
                    key = (item['source'], item['id'])
                    if key not in shortlist and len(shortlist) < 10:
                        shortlist[key] = item
            model_candidates = [c for c in candidates if all(
                (i['source'], i['id']) in shortlist for i in c['items'])]
            compact = [{'itemKeys': [{'source': i['source'], 'id': i['id']} for i in c['items']],
                        'score': c['score']} for c in model_candidates]
            context = {'parsed': parsed, 'weather': weather, 'destination': dest}
            for _ in range(2):
                try:
                    selected, proposed_reason, proposed_tips = validate_rank(
                        self.llm.rank(compact, list(shortlist.values()), context),
                        model_candidates, request['locked_items'])
                    chosen, reason, local_tips = selected, proposed_reason, proposed_tips
                    model_status = 'generated'
                    break
                except (RuntimeError, ValueError):
                    warnings.append('模型精排不可用，已采用规则搭配')
        if previous and chosen['items'] and excluded == {(i['source'],i['id']) for i in chosen['items']}:
            warnings.append('可用衣物不足，暂无法生成不同搭配')
        categories = {i['category'] for i in chosen['items']}
        if chosen['items']:
            if 'dress' not in categories:
                for c, name in [('tops','上装'),('bottoms','下装')]:
                    if c not in categories:
                        warnings.append(f'当前衣橱缺少{name}')
            if 'shoes' not in categories:
                warnings.append('当前衣橱缺少鞋类')
            if weather and weather['temperatureMinC'] <= 12 and 'outerwear' not in categories:
                warnings.append('低温天气缺少合适外套，搭配仅供参考')
        else:
            warnings.append('当前衣橱没有已确认且可用的单品')
        for item in chosen['items']:
            if item['source'] == 'wish':
                warnings.append(f"{item.get('name') or '心愿单品'}来自心愿衣橱，尚未拥有")
        if dest and not local_tips:
            if parsed['scene_attrs']['walking'] >= 4:
                local_tips.append('旅行步行较多，建议优先穿适合长时间活动的鞋。')
            if parsed['scene_attrs']['photoFriendly']:
                local_tips.append('拍照时可利用现有衣物中的协调配色。')
        # 持久化前再次向衣橱端确认，阻断生成期间被删除或取消公开的单品。
        for item in chosen['items']:
            if not self.wardrobe.still_available(user_id, item['source'], item['id']):
                raise BusinessError(40901, '衣物状态已变化，请重新生成', 409)
        result = {'parsed': parsed, 'items': [snapshot(i) for i in chosen['items']],
                  'warnings': list(dict.fromkeys(warnings)), 'local_tips': local_tips,
                  'reason': reason, 'weather': weather, 'modelStatus': model_status}
        result['id'] = self.store.save(user_id, result, request, chosen['score'])
        return result

    def detail(self, user_id: str, rec_id: str) -> dict:
        stored = self.store.get(user_id, rec_id)
        items = [dict(i, available=self.wardrobe.still_available(user_id, i['source'], i['id']))
                 for i in stored['items']]
        return {'id': stored['id'], 'parsed': stored['parsed_scene'], 'items': items,
                'warnings': stored['warnings'], 'local_tips': stored['local_tips'],
                'reason': stored['reason'], 'weather': stored['weather_snapshot'],
                'modelStatus': stored['model_status'], 'sceneText': stored['scene_text'],
                'styleText': stored['style_text'], 'createdAt': stored['created_at']}

    def regenerate(self, user_id: str, rec_id: str, body: object) -> dict:
        previous = self.store.get(user_id, rec_id)
        if not isinstance(body, dict) or set(body) - {'locked_items'}:
            raise BusinessError(40001, '重新生成请求字段无效')
        request = dict(previous['request_json'])
        request['locked_items'] = body.get('locked_items', [])
        return self.generate(user_id, request, previous=previous)
