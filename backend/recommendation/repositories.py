"""推荐自有数据持久化与跨模块衣橱接口。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .contracts import BusinessError


class OutfitStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS outfits (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, items TEXT NOT NULL,
                  warnings TEXT NOT NULL, occasion TEXT, scene_text TEXT, style_text TEXT,
                  parsed_scene TEXT NOT NULL, destination_city_id TEXT, travel_date TEXT,
                  local_tips TEXT NOT NULL, reason TEXT NOT NULL, weather_snapshot TEXT,
                  score REAL NOT NULL, model_status TEXT NOT NULL, request_json TEXT NOT NULL,
                  created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_outfits_user_created ON outfits(user_id,created_at DESC);
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                  user_id TEXT NOT NULL, recommendation_id TEXT NOT NULL,
                  preference TEXT NOT NULL, reason TEXT, saved_at TEXT NOT NULL,
                  PRIMARY KEY(user_id,recommendation_id), FOREIGN KEY(recommendation_id) REFERENCES outfits(id));
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _decode(row):
        data = dict(row)
        for field in ('items','warnings','parsed_scene','local_tips','weather_snapshot','request_json'):
            data[field] = json.loads(data[field]) if data[field] is not None else None
        return data

    def save(self, user_id: str, result: dict, request: dict, score: float) -> str:
        rec_id = 'rec_' + uuid.uuid4().hex[:20]
        with self._db() as db:
            db.execute('''INSERT INTO outfits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                rec_id, user_id, json.dumps(result['items'], ensure_ascii=False),
                json.dumps(result['warnings'], ensure_ascii=False), result['parsed']['scene'],
                request['sceneText'], request['styleText'], json.dumps(result['parsed'], ensure_ascii=False),
                (request['destination'] or {}).get('cityId'), request['travelDate'],
                json.dumps(result['local_tips'], ensure_ascii=False), result['reason'],
                json.dumps(result['weather'], ensure_ascii=False) if result['weather'] else None,
                score, result['modelStatus'], json.dumps(request, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat()))
            db.commit()
        return rec_id

    def get(self, user_id: str, rec_id: str) -> dict:
        with self._db() as db:
            row = db.execute('SELECT * FROM outfits WHERE id=? AND user_id=?', (rec_id,user_id)).fetchone()
        if not row:
            raise BusinessError(40401, '推荐不存在或不可见', 404)
        return self._decode(row)

    def history(self, user_id: str, page: int, size: int) -> tuple[list[dict], int]:
        with self._db() as db:
            total = db.execute('SELECT COUNT(*) FROM outfits WHERE user_id=?', (user_id,)).fetchone()[0]
            rows = db.execute('SELECT * FROM outfits WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                              (user_id, size, (page-1)*size)).fetchall()
        return [self._decode(r) for r in rows], total

    def feedback(self, user_id: str, rec_id: str, preference: str, reason: str) -> str:
        self.get(user_id, rec_id)
        saved = datetime.now(timezone.utc).isoformat()
        with self._db() as db:
            db.execute('''INSERT INTO recommendation_feedback VALUES (?,?,?,?,?)
                ON CONFLICT(user_id,recommendation_id) DO UPDATE SET
                  preference=excluded.preference,reason=excluded.reason,saved_at=excluded.saved_at''',
                       (user_id,rec_id,preference,reason,saved))
            db.commit()
        return saved

    def feedback_history(self, user_id: str) -> list[dict]:
        with self._db() as db:
            rows = db.execute('''SELECT f.preference,o.parsed_scene FROM recommendation_feedback f
                JOIN outfits o ON o.id=f.recommendation_id WHERE f.user_id=? ORDER BY f.saved_at DESC LIMIT 30''',
                              (user_id,)).fetchall()
        return [{'preference': r['preference'], 'colors': json.loads(r['parsed_scene']).get('color_family', [])}
                for r in rows]


class WardrobePort:
    """账号和衣橱负责人接入时实现这些方法；服务不直接访问他们的表。"""
    def current_user(self, token: str) -> str:
        raise NotImplementedError

    def items(self, user_id: str, include_wish: bool) -> list[dict]:
        raise NotImplementedError

    def preferences(self, user_id: str) -> dict:
        return {'styles': [], 'avoid_colors': []}

    def current_city_id(self, user_id: str) -> str | None:
        return None

    def still_available(self, user_id: str, source: str, item_id: str) -> bool:
        return False


class UnconfiguredWardrobe(WardrobePort):
    def current_user(self, token: str) -> str:
        raise BusinessError(40101, '认证服务尚未接入', 401)

    def items(self, user_id: str, include_wish: bool) -> list[dict]:
        raise BusinessError(50001, '衣橱服务尚未接入', 503)


class MockWardrobe(WardrobePort):
    """两名模拟用户、30 件模拟衣物，仅在 RECOMMENDATION_MODE=mock 启用。"""
    def __init__(self):
        self.tokens = {'mock-token-u1': 'mock_u1', 'mock-token-u2': 'mock_u2'}
        categories = ['tops','bottoms','outerwear','dress','shoes','bag','accessory']
        colors = ['白','棕','黑','米白','焦糖','浅蓝','灰','银','粉','卡其']
        styles = ['minimal','vintage','casual','street','sweet','formal','sporty']
        self.records = []
        for user, count in (('mock_u1', 32), ('mock_u2', 7)):
            for n in range(count):
                category = categories[n % len(categories)]
                self.records.append({
                    'id': f'item_{user}_{n+1}', 'user_id': user, 'source': 'owned',
                    'name': f'模拟{category}{n+1}', 'image_url': f'/mock/{user}/{n+1}.jpg',
                    'category': category, 'color': colors[n % len(colors)],
                    'warmth': None if n == 11 else n % 5 + 1,
                    'season': [] if n == 12 else [['spring','autumn'],['winter'],['summer']][n % 3],
                    'style': [styles[n % len(styles)]], 'occasion': [['casual','travel'],['commute'],['formal']][n % 3],
                    'verify_status': 'pending' if n == 13 else 'confirmed',
                    'visibility': 'private', 'is_favorite': n % 6 == 0, 'deleted': False})
        self.records += [
            {'id': 'wish_valid', 'user_id': 'mock_u1', 'source': 'wish', 'name': '模拟心愿米白外套',
             'image_url': '/mock/wish/1.jpg', 'category': 'outerwear', 'color': '米白', 'warmth': 4,
             'season': ['winter'], 'style': ['minimal'], 'occasion': ['travel'],
             'verify_status': 'confirmed', 'available': True, 'source_visibility': 'public'},
            {'id': 'wish_invalid', 'user_id': 'mock_u1', 'source': 'wish', 'name': '已失效模拟心愿鞋',
             'image_url': '/mock/wish/2.jpg', 'category': 'shoes', 'color': '黑', 'warmth': 2,
             'season': [], 'style': [], 'occasion': [], 'verify_status': 'confirmed',
             'available': False, 'source_visibility': 'private'},
        ]

    def current_user(self, token: str) -> str:
        user = self.tokens.get(token)
        if not user:
            raise BusinessError(40101, 'token 无效', 401)
        return user

    def items(self, user_id: str, include_wish: bool) -> list[dict]:
        return [dict(i) for i in self.records if i['user_id'] == user_id and
                (include_wish or i['source'] == 'owned')]

    def preferences(self, user_id: str) -> dict:
        return {'styles': ['vintage'], 'avoid_colors': ['紫']} if user_id == 'mock_u1' else {'styles': [], 'avoid_colors': []}

    def current_city_id(self, user_id: str) -> str | None:
        return 'city_suzhou' if user_id == 'mock_u1' else 'city_beijing'

    def still_available(self, user_id: str, source: str, item_id: str) -> bool:
        return any(i['user_id'] == user_id and i['source'] == source and i['id'] == item_id and
                   i['verify_status'] == 'confirmed' and not i.get('deleted') and
                   (source == 'owned' or i.get('available') and i.get('source_visibility') == 'public')
                   for i in self.records)
