"""独立标准库 HTTP 入口；团队后端可复用 RecommendationService 注册原路由。"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .contracts import BusinessError, iso_date, optional_text
from .catalog_fixture import CatalogWardrobe
from .providers import LLMProvider, LiveCityWeather, MockCityWeather
from .repositories import MockWardrobe, OutfitStore, UnconfiguredWardrobe
from .service import RecommendationService

ROOT = '/api/v1'
MAX_BODY = 64 * 1024


def create_app(*, mode: str | None = None, store_path: str | None = None, wardrobe=None,
               city_weather=None, llm=None, today=None) -> RecommendationService:
    mode = mode or os.getenv('RECOMMENDATION_MODE', 'live')
    if mode not in ('live', 'mock', 'catalog_live_weather'):
        raise ValueError('RECOMMENDATION_MODE 必须为 live、mock 或 catalog_live_weather')
    if mode == 'live' and os.getenv('WEATHER_PROVIDER', 'open_meteo') != 'open_meteo':
        raise ValueError('当前仅实现 WEATHER_PROVIDER=open_meteo；其他供应商请注入 city_weather')
    repository = wardrobe or (CatalogWardrobe() if mode == 'catalog_live_weather' else
                              MockWardrobe() if mode == 'mock' else UnconfiguredWardrobe())
    provider = city_weather or (MockCityWeather() if mode == 'mock' else LiveCityWeather(
        float(os.getenv('WEATHER_TIMEOUT_SECONDS', '5'))))
    if mode == 'catalog_live_weather' and city_weather is None:
        # 虚拟用户的当前位置来自明确标记的模拟资料；气温仍通过实时供应商查询。
        provider.cities.update(MockCityWeather().cities)
    path = store_path or os.getenv('RECOMMENDATION_DB_PATH') or str(Path(__file__).parent / 'data' / 'recommendation.sqlite3')
    service = RecommendationService(repository, provider, llm or LLMProvider(), OutfitStore(path), today=today)
    service.demo_mode = mode
    return service


def handler_factory(service: RecommendationService):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, code: int, message: str, data, request_id: str):
            body = json.dumps({'code': code, 'message': message, 'data': data, 'requestId': request_id},
                              ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                raise BusinessError(40001, '请发送 JSON', 400)
            try:
                length = int(self.headers.get('Content-Length', ''))
            except ValueError:
                raise BusinessError(40001, 'Content-Length 无效') from None
            if not 0 < length <= MAX_BODY:
                raise BusinessError(40001, '请求体为空或过大')
            try:
                return json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                raise BusinessError(40001, 'JSON 格式无效') from None

        def _user(self):
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer ') or not auth[7:].strip():
                raise BusinessError(40101, '请先登录', 401)
            return service.wardrobe.current_user(auth[7:].strip())

        @staticmethod
        def _page(query):
            try:
                page = int(query.get('page', ['1'])[0])
                size = int(query.get('pageSize', ['20'])[0])
            except ValueError:
                raise BusinessError(40001, '分页参数无效') from None
            if page < 1 or not 1 <= size <= 100:
                raise BusinessError(40001, '分页参数无效')
            return page, size

        def _dispatch(self, method: str):
            request_id = 'req_' + uuid.uuid4().hex[:12]
            try:
                parsed_url = urlsplit(self.path)
                path = parsed_url.path
                query = parse_qs(parsed_url.query)
                image_match = re.fullmatch(r'/demo/images/(catalog_[0-9]+)', path)
                if image_match and method == 'GET' and isinstance(service.wardrobe, CatalogWardrobe):
                    image_path = service.wardrobe.image_path(image_match.group(1))
                    if not image_path:
                        raise BusinessError(40401, '图片不存在', 404)
                    content = image_path.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/webp' if image_path.suffix.lower() == '.webp' else 'image/jpeg' if image_path.suffix.lower() in ('.jpg', '.jpeg') else 'image/png')
                    self.send_header('Cache-Control', 'private, max-age=300')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                if path in ('/', '/demo') and method == 'GET' and isinstance(service.wardrobe, MockWardrobe):
                    content = (Path(__file__).parent / 'demo.html').read_text(encoding='utf-8')
                    content = content.replace('%DEMO_MODE%', '模拟账号 · 真实天气 · 商品样本' if service.demo_mode == 'catalog_live_weather' else '全模拟数据')
                    content = content.replace('%DEMO_NOTE%', '衣物来自本地公开商品样本并假设由模拟用户拥有；天气来自实时供应商。' if service.demo_mode == 'catalog_live_weather' else '账号、衣物和天气均为测试替身，不代表真实用户或预报。')
                    content = content.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                if path == '/health' and method == 'GET':
                    return self._send(200, 0, 'ok', {'status': 'ok'}, request_id)
                if not path.startswith(ROOT + '/'):
                    raise BusinessError(40401, '接口不存在', 404)
                user = self._user()
                route = path[len(ROOT):]
                if route == '/cities' and method == 'GET':
                    keyword = optional_text(query.get('keyword', [''])[0], 'keyword', 80)
                    country = optional_text(query.get('country', [''])[0], 'country', 80)
                    try:
                        data = service.city_weather.search(keyword, country)
                    except RuntimeError:
                        raise BusinessError(50302, '城市搜索暂不可用', 503) from None
                    return self._send(200, 0, 'ok', data, request_id)
                if route == '/weather' and method == 'GET':
                    city_id = query.get('cityId', [''])[0]
                    if not city_id or len(city_id) > 100:
                        raise BusinessError(40001, 'cityId 无效')
                    day = iso_date(query.get('date', [''])[0], 'date')
                    return self._send(200, 0, 'ok', service.get_weather(city_id, day), request_id)
                if route == '/recommend/scene-parse' and method == 'POST':
                    return self._send(200, 0, 'ok', service.parse_preview(self._body()), request_id)
                if route == '/recommendations' and method == 'POST':
                    return self._send(201, 0, 'ok', service.generate(user, self._body()), request_id)
                if route == '/recommendations' and method == 'GET':
                    page, size = self._page(query)
                    rows, total = service.store.history(user, page, size)
                    data = {'list': [service.detail(user, r['id']) for r in rows], 'total': total,
                            'page': page, 'pageSize': size}
                    return self._send(200, 0, 'ok', data, request_id)
                match = re.fullmatch(r'/recommendations/([A-Za-z0-9_-]+)(/regenerate|/feedback)?', route)
                if match:
                    rec_id, action = match.groups()
                    if action is None and method == 'GET':
                        return self._send(200, 0, 'ok', service.detail(user, rec_id), request_id)
                    if action == '/regenerate' and method == 'POST':
                        return self._send(201, 0, 'ok', service.regenerate(user, rec_id, self._body()), request_id)
                    if action == '/feedback' and method == 'PUT':
                        body = self._body()
                        if not isinstance(body, dict) or set(body) - {'preference','reason'} or body.get('preference') not in ('like','dislike'):
                            raise BusinessError(40001, '反馈字段无效')
                        reason = optional_text(body.get('reason'), 'reason', 300)
                        saved = service.store.feedback(user, rec_id, body['preference'], reason)
                        return self._send(200, 0, 'ok', {'preference': body['preference'], 'savedAt': saved}, request_id)
                raise BusinessError(40401, '接口不存在', 404)
            except BusinessError as error:
                self._send(error.status, error.code, error.message, None, request_id)
            except Exception:
                # 不记录请求体、Token 或私人衣橱数据。
                self._send(500, 50001, '服务内部错误', None, request_id)

        def do_GET(self): self._dispatch('GET')
        def do_POST(self): self._dispatch('POST')
        def do_PUT(self): self._dispatch('PUT')

    return Handler


def create_server(host: str | None = None, port: int | None = None, **kwargs):
    service = create_app(**kwargs)
    bind_host = host or os.getenv('RECOMMENDATION_HOST', '127.0.0.1')
    if service.demo_mode == 'catalog_live_weather' and bind_host not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('商品样本联调模式仅允许监听本机回环地址')
    return ThreadingHTTPServer((bind_host,
                                port if port is not None else int(os.getenv('RECOMMENDATION_PORT', '8010'))),
                               handler_factory(service))


if __name__ == '__main__':
    server = create_server()
    print(f'推荐服务已启动: {server.server_address}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
