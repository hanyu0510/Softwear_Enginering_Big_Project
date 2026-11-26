"""合并回归：真实账号凭据供衣橱、社区共用，旧数据库不丢数据。"""
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.modules.account.settings import Settings


class SharedBackendTests(unittest.TestCase):
    def test_shared_identity_and_existing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shared.db"
            conn = sqlite3.connect(path)
            conn.executescript((Path(__file__).resolve().parents[1] / "sql/schema.sql").read_text())
            conn.execute("INSERT INTO users(id,nickname,bio,created_at) VALUES('old_author','原作者','保留简介','2026-01-01')")
            conn.execute("INSERT INTO posts(id,user_id,title,text,created_at) VALUES('old_post','old_author','原帖子','保留正文','2026-01-01')")
            conn.commit()
            conn.close()
            app = create_app(Settings(database_path=path, rate_limit_enabled=False))
            try:
                with TestClient(app) as client:
                    response = client.post('/api/v1/auth/register', json={"email": "one@example.com", "password": "password123", "nickname": "测试"})
                    self.assertEqual(response.status_code, 200, response.text)
                    login = client.post('/api/v1/auth/login', json={"email": "one@example.com", "password": "password123"}).json()['data']
                    headers = {"Authorization": "Bearer " + login['token']}
                    uid = login['user']['id']
                    self.assertEqual(client.get('/api/v1/posts').json()['data']['list'][0]['id'], 'old_post')
                    self.assertEqual(client.get('/api/v1/users/old_author').json()['data']['bio'], '保留简介')
                    self.assertEqual(client.get('/api/v1/posts?scope=following', headers=headers).status_code, 200)
                    image = BytesIO()
                    Image.new('RGB', (32, 32), '#123456').save(image, 'JPEG')
                    uploaded = client.post('/api/v1/uploads/image', headers=headers, files={'file': ('test.jpg', image.getvalue(), 'image/jpeg')})
                    self.assertEqual(uploaded.status_code, 200, uploaded.text)
                    self.assertEqual(client.get('/api/v1/items', headers=headers).status_code, 200)
                    self.assertEqual(client.put('/api/v1/users/old_author/follow', headers=headers).status_code, 200)
                    self.assertEqual(client.get('/api/v1/me', headers=headers).json()['data']['following_count'], 1)
                    self.assertEqual(client.get('/api/v1/posts?scope=following', headers=headers).json()['data']['total'], 1)
                    self.assertEqual(client.delete('/api/v1/users/old_author/follow', headers=headers).status_code, 200)
                    self.assertEqual(client.get('/api/v1/me', headers=headers).json()['data']['following_count'], 0)
                    with app.state.database.connection() as check:
                        self.assertEqual(check.execute('SELECT owner_id FROM uploaded_files').fetchone()[0], uid)
                        self.assertEqual(check.execute("SELECT text FROM posts WHERE id='old_post'").fetchone()[0], '保留正文')
                    client.post('/api/v1/auth/logout', headers=headers)
                    self.assertEqual(client.get('/api/v1/items', headers=headers).status_code, 401)
                    self.assertEqual(client.get('/api/v1/posts?scope=following', headers=headers).status_code, 401)
            finally:
                app.state.orm_engine.dispose()
