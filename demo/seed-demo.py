"""Prepare course posts locally and create the presentation wardrobe through the public API."""
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNTIME = ROOT / 'backend/data/yida-classroom/state'
if Path(os.environ['YIDA_DEMO_RUNTIME']).resolve() != RUNTIME:
    raise RuntimeError('Refusing to seed outside the classroom state directory')
MEDIA = RUNTIME / 'media'
DATABASE = RUNTIME / 'public.sqlite3'

AUTHORS = ['林间手记', '苏禾', '朝颜', '周一衣记', '织织', '慢慢', '许栀']
POSTS = [
    ('coat', 0, '一件风衣的三种日常', '卡其风衣给针织和衬衫都留出了空间，深色下装把颜色收住。通勤选平底鞋，周末就换一只轻便的包。', '秋日通勤', (2,6)),
    ('soft', 1, '周末，把衣服穿轻一点', '海边风大，同色系的轻软针织和长裙刚刚好。', '同色系', (4,)),
    ('blue', 2, '浅蓝与燕麦，给工作日透口气', '浅蓝衬衫和燕麦色长裤，搭配简单，整天都舒服。', '通勤', (1,)),
    ('black', 3, '深色外套的轻松穿法', '给深色外套留一道浅色内搭，叠穿有了层次。', '日常', (3,)),
    ('knit', 4, '针织与自然光', '用柔软织物和浅中性色留住下午的自然光。', '针织', (9,)),
    ('weekend', 5, '公园长椅上的下午', '天气凉的时候，外套和围巾便是我出门前最先拿的两样。', '周末', (12,)),
    ('layer', 6, '降温后的第一套叠穿', '早晚凉些，我会多带一件可以随时脱下的外套。', '叠穿', (6,)),
    ('street', 3, '街角散步，轻装出门', '这次想把行走的舒适度放在前面，周末散步就能多走一站。', '街拍', (5,)),
    ('city', 2, '给城市日常留一点松弛', '轮廓松一些，连雨后的短途散步也能自在些。', '城市日常', (7,)),
    ('palette', 6, '今天的配色只留两个重点', '先挑一件作为主角，再用相近或更安静的色调去衬。', '配色', (8,)),
    ('detail', 1, '衣橱里最喜欢的质感', '把常穿的衣服按质感重新整理了一遍，出门前搭配更轻松了。', '衣橱整理', (11,)),
    ('slow', 4, '慢一点的周末穿搭', '不用临时找新衣服，从已经穿熟的几件里挑一件最舒服的。', '轻松周末', (10,)),
]

GARMENTS = [
    ('cream-knit','奶油色绞花针织衫','tops','米白',4,('spring','autumn','winter'),('minimal','vintage'),('commute','casual')),
    ('khaki-trench','卡其双排扣风衣','outerwear','卡其',3,('spring','autumn'),('minimal','vintage'),('commute','travel','formal')),
    ('blue-jeans','靛蓝直筒牛仔裤','bottoms','靛蓝',2,('spring','autumn'),('casual','vintage'),('commute','casual')),
    ('black-coat','黑色长大衣','outerwear','黑',5,('autumn','winter'),('minimal','formal'),('commute','formal')),
    ('brown-bag','焦棕肩包','bag','焦棕',None,('spring','autumn'),('minimal','vintage'),('commute','date')),
    ('white-sneakers','米白运动鞋','shoes','米白',None,('spring','summer','autumn'),('sporty','casual'),('travel','sport')),
    ('burgundy-scarf','酒红色围巾','accessory','酒红',4,('autumn','winter'),('vintage','casual'),('commute','date')),
    ('floral-dress','碎花连衣裙','dress','米白',2,('spring','summer'),('sweet','vintage'),('date','casual')),
    ('denim-overshirt','牛仔衬衫','tops','牛仔蓝',3,('spring','autumn'),('street','casual'),('travel','casual')),
]


def seed_community():
    now = datetime.now(timezone.utc)
    with sqlite3.connect(DATABASE.as_uri() + '?mode=rw', uri=True) as connection:
        for index, author in enumerate(AUTHORS):
            connection.execute('INSERT OR IGNORE INTO users (id,nickname,avatar_url,created_at) VALUES (?,?,?,?)',
                               (f'course_author_{index + 1}', author, f'/__course/media/avatar-{index + 1:02}.webp', now.isoformat()))
        for offset, (slug, author_index, title, body, tag, photos) in enumerate(POSTS):
            user, post = f'course_author_{author_index + 1}', f'course_{slug}'
            timestamp = (now - timedelta(hours=offset + 1)).isoformat()
            inserted = connection.execute('INSERT OR IGNORE INTO posts (id,user_id,title,text,created_at) VALUES (?,?,?,?,?)',
                                          (post, user, title, body, timestamp))
            if not inserted.rowcount:
                continue
            connection.execute('INSERT INTO post_tags (post_id,tag,sort_order) VALUES (?,?,0)', (post, tag))
            for order, number in enumerate(photos):
                file = f'look-{number:02}.webp'
                with Image.open(MEDIA/file) as image:
                    width, height = image.size
                path = '/__course/media/' + file
                connection.execute('INSERT INTO post_images (post_id,url,thumb_url,width,height,sort_order) VALUES (?,?,?,?,?,?)',
                                   (post, path, path, width, height, order))
        comments = (
            ('coat', 2, '卡其和深色下装这一组很适合早晚温差大的通勤日。'),
            ('coat', 4, '衬衫露出领口那一点浅色，叠穿就不会显得太重。'),
            ('blue', 1, '浅蓝配燕麦色很清爽，想试试搭白鞋。'),
        )
        for index, (slug, author, text) in enumerate(comments):
            post_id = 'course_' + slug
            inserted = connection.execute('INSERT OR IGNORE INTO comments (id,post_id,user_id,text,created_at) VALUES (?,?,?,?,?)',
                                          (f'course_note_{index}', post_id, f'course_author_{author + 1}', text, now.isoformat()))
            if inserted.rowcount:
                connection.execute('UPDATE posts SET comment_count=comment_count+1 WHERE id=?', (post_id,))


def read_data(response, statuses=(200,)):
    payload = response.json()
    if response.status_code not in statuses or payload.get('code') != 0:
        raise RuntimeError(f'{response.request.method} {response.request.url.path}: HTTP {response.status_code}, code {payload.get("code")}')
    return payload['data']


def login(client, account):
    session = read_data(client.post('/auth/login', json={key: account[key] for key in ('email','password')}))
    client.headers['Authorization'] = 'Bearer ' + session['token']
    return session['user']


def create_wardrobe(client):
    existing = read_data(client.get('/items', params={'pageSize':100}))
    names = {row['name'] for row in existing['list']}
    for image, name, category, color, warmth, seasons, styles, occasions in GARMENTS:
        if name in names:
            continue
        path = ROOT / 'backend/demo_assets/realistic' / (image + '.png')
        with path.open('rb') as picture:
            upload = read_data(client.post('/uploads/image', files={'file': (path.name, picture, mimetypes.guess_type(path)[0])}), (200,201))
        fields = dict(name=name, category=category, color=color, warmth=warmth, season=seasons, style=styles,
                      occasion=occasions, visibility='private', imageFileId=upload['fileId'])
        read_data(client.post('/items', json=fields), (201,))


def seed_account():
    secret_file = RUNTIME / 'demo-account.json'
    if not secret_file.exists():
        data = {'email':'lin.yu.course@example.test', 'nickname':'林予', 'password':secrets.token_urlsafe(16)}
        fd = os.open(secret_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    account = json.loads(secret_file.read_text(encoding='utf-8'))
    with sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True) as connection:
        user = connection.execute('SELECT id FROM users WHERE email=?',(account['email'],)).fetchone()
    with httpx.Client(base_url='http://127.0.0.1:8002/api/v1', trust_env=False, timeout=15) as client:
        if not user:
            read_data(client.post('/auth/register', json=account), (200,201))
        identity = login(client, account)
        with sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True) as connection:
            assert connection.execute('SELECT id FROM users WHERE email=?',(account['email'],)).fetchone() == (identity['id'],)
        create_wardrobe(client)
        saved = read_data(client.get('/items', params={'pageSize':100}))
        assert {item[1] for item in GARMENTS} <= {row['name'] for row in saved['list']}
        # Close the account only after a genuine refresh and rotation.
        token = read_data(client.post('/auth/refresh'))['token']
        client.headers['Authorization'] = 'Bearer ' + token
        assert read_data(client.get('/me'))['nickname'] == account['nickname']
        read_data(client.post('/auth/logout'))
        print(f'Course wardrobe ready ({saved["total"]} items).')


if __name__ == '__main__':
    seed_community()
    seed_account()
    print('Course community fixtures ready.')
