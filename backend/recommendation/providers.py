"""可替换的天气与模型供应商。真实模式绝不切换到模拟天气。"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import BusinessError, neutral_parsed, validate_parsed

LOG = logging.getLogger(__name__)


def fetch_json(url: str, *, payload: dict | None = None, headers: dict | None = None,
               timeout: float = 5, attempts: int = 2) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    last = None
    for number in range(attempts):
        try:
            req = Request(url, data=body, headers=headers or {}, method='POST' if body is not None else 'GET')
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last = error
            if number + 1 < attempts:
                time.sleep(0.15 * (number + 1))
    raise RuntimeError('上游服务不可用') from last


class LiveCityWeather:
    """Open-Meteo 地理编码与每日预报。cityId 使用其稳定地理编码 ID。"""
    def __init__(self, timeout: float = 5):
        self.timeout = timeout
        self.base = os.getenv('WEATHER_BASE_URL', 'https://api.open-meteo.com').rstrip('/')
        self.cities: dict[str, dict] = {}
        self.cache: dict[tuple[str, str, str], tuple[float, dict]] = {}

    def search(self, keyword: str, country: str = '') -> list[dict]:
        if not keyword:
            return []
        language = 'en' if country and country.isascii() else 'zh'
        result = fetch_json('https://geocoding-api.open-meteo.com/v1/search?' + urlencode(
            {'name': keyword, 'count': 20, 'language': language, 'format': 'json'}), timeout=self.timeout)
        cities = []
        for row in result.get('results', []):
            city = {'cityId': f"om_{row['id']}", 'cityName': row['name'],
                    'region': row.get('admin1') or '', 'country': row.get('country') or '',
                    'lat': row['latitude'], 'lng': row['longitude']}
            if not country or country.casefold() in (city['country'].casefold(), str(row.get('country_code', '')).casefold()):
                self.cities[city['cityId']] = city
                cities.append(city)
        return cities

    def resolve(self, city_id: str) -> dict | None:
        if city_id in self.cities:
            return self.cities[city_id]
        if not city_id.startswith('om_') or not city_id[3:].isdigit():
            return None
        try:
            result = fetch_json('https://geocoding-api.open-meteo.com/v1/get?' + urlencode(
                {'id': city_id[3:], 'language': 'zh'}), timeout=self.timeout)
            if not result.get('id'):
                return None
            city = {'cityId': city_id, 'cityName': result['name'],
                    'region': result.get('admin1') or '', 'country': result.get('country') or '',
                    'lat': result['latitude'], 'lng': result['longitude']}
            self.cities[city_id] = city
            return city
        except RuntimeError:
            return None

    def weather(self, city: dict, day: date) -> dict:
        key = (city['cityId'], day.isoformat(), 'open-meteo')
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        result = fetch_json(self.base + '/v1/forecast?' + urlencode({
            'latitude': city['lat'], 'longitude': city['lng'],
            'daily': 'temperature_2m_min,temperature_2m_max,precipitation_probability_max,weather_code',
            'timezone': 'auto', 'forecast_days': 16,
        }), timeout=self.timeout)
        daily = result.get('daily') or {}
        dates = daily.get('time') or []
        if day.isoformat() not in dates or not daily.get('temperature_2m_min') or not daily.get('temperature_2m_max'):
            raise RuntimeError('天气预报无有效日期数据')
        index = dates.index(day.isoformat())
        if len(daily['temperature_2m_min']) <= index or len(daily['temperature_2m_max']) <= index:
            raise RuntimeError('天气预报缺少目标日期温度')
        low, high = daily['temperature_2m_min'][index], daily['temperature_2m_max'][index]
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)) or low > high:
            raise RuntimeError('天气预报温度无效')
        codes = daily.get('weather_code') or []
        code = codes[index] if len(codes) > index else None
        condition = ('晴' if code == 0 else '多云' if code in (1, 2, 3) else
                     '雪' if code is not None and 71 <= code <= 77 else
                     '雨' if code is not None and (51 <= code <= 67 or 80 <= code <= 82) else '其他')
        weather = {'cityId': city['cityId'], 'cityName': city['cityName'], 'date': day.isoformat(),
                   'temperatureMinC': low,
                   'temperatureMaxC': high,
                   'condition': condition,
                   'rainProbability': ((daily.get('precipitation_probability_max') or [])[index]
                                       if len(daily.get('precipitation_probability_max') or []) > index else None),
                   'observedAt': datetime.now(timezone.utc).isoformat(),
                   'source': 'Open-Meteo', 'forecast': True}
        self.cache[key] = (time.monotonic() + (300 if day == date.today() else 3600), weather)
        return weather


class MockCityWeather:
    """仅供测试，所有返回的 source 均显式标识为 MOCK。"""
    def __init__(self):
        self.cities = {
            'city_suzhou': {'cityId': 'city_suzhou', 'cityName': '苏州', 'region': '江苏', 'country': '中国', 'lat': 31.2989, 'lng': 120.5853},
            'city_rome': {'cityId': 'city_rome', 'cityName': '罗马', 'region': '拉齐奥', 'country': '意大利', 'lat': 41.9028, 'lng': 12.4964},
            'city_beijing': {'cityId': 'city_beijing', 'cityName': '北京', 'region': '北京', 'country': '中国', 'lat': 39.9042, 'lng': 116.4074},
        }
        self.unavailable = False
        self.temperature = (8, 16)
        self.rain_probability = 20

    def search(self, keyword: str, country: str = '') -> list[dict]:
        return [c for c in self.cities.values() if (keyword.casefold() in (c['cityName'] + c['region'] + c['country']).casefold()
                or keyword.casefold() in {'suzhou': '苏州', 'rome': '罗马', 'beijing': '北京'} and
                c['cityName'] == {'suzhou': '苏州', 'rome': '罗马', 'beijing': '北京'}[keyword.casefold()])
                and (not country or country.casefold() == c['country'].casefold())]

    def resolve(self, city_id: str) -> dict | None:
        return self.cities.get(city_id)

    def weather(self, city: dict, day: date) -> dict:
        if self.unavailable:
            raise RuntimeError('模拟天气故障')
        low, high = self.temperature
        return {'cityId': city['cityId'], 'cityName': city['cityName'], 'date': day.isoformat(),
                'temperatureMinC': low, 'temperatureMaxC': high, 'condition': '模拟多云',
                'rainProbability': self.rain_probability, 'observedAt': datetime.now(timezone.utc).isoformat(),
                'source': 'MOCK_TEST_ONLY', 'forecast': day > date.today()}


class LLMProvider:
    """OpenAI 兼容 JSON 端点适配；没有 Key 时调用方使用本地规则。"""
    def __init__(self):
        self.key = os.getenv('LLM_API_KEY', '')
        self.base = os.getenv('LLM_BASE_URL', '').rstrip('/')
        self.model = os.getenv('LLM_MODEL', '')
        self.timeout = float(os.getenv('LLM_TIMEOUT_SECONDS', '8'))

    @property
    def configured(self) -> bool:
        return bool(self.key and self.base and self.model)

    def _json(self, system: str, data: dict) -> dict:
        if not self.configured:
            raise RuntimeError('模型未配置')
        started = time.monotonic()
        try:
            result = fetch_json(self.base + '/chat/completions', payload={
                'model': self.model, 'temperature': 0.2, 'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}]},
                headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'},
                timeout=self.timeout)
            output = json.loads(result['choices'][0]['message']['content'])
            LOG.info('llm task success elapsed_ms=%d tokens=%s', int((time.monotonic()-started)*1000),
                     result.get('usage', {}).get('total_tokens'))
            return output
        except (KeyError, IndexError, ValueError, RuntimeError) as error:
            LOG.warning('llm task failed elapsed_ms=%d type=%s', int((time.monotonic()-started)*1000), type(error).__name__)
            raise RuntimeError('模型输出不可用') from error

    def parse(self, scene: str, style: str) -> dict:
        from .prompts import SCENE_PROMPT
        try:
            return validate_parsed(self._json(SCENE_PROMPT, {'sceneText': scene, 'styleText': style}))
        except BusinessError as error:
            raise ValueError('模型输出结构无效') from error

    def rank(self, candidates: list[dict], items: list[dict], context: dict) -> dict:
        from .prompts import RANK_PROMPT
        safe_items = [{k: item.get(k) for k in ('id','source','name','category','color','warmth','style','occasion')}
                      for item in items]
        return self._json(RANK_PROMPT, {'candidates': candidates, 'items': safe_items, 'context': context})
