"""执行：python -m unittest discover -s tests -v。所有数据库都建在临时目录。"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from app.modules.account.settings import Settings
from app.core.database import transaction
from app.core.errors import ApiError
from app.core.security import hash_token
from app.main import create_app
from app.modules.account.integrations import Integrations
from app.modules.account.service import create_notification


class Clock:
    def __init__(self):
        self.value = time.time()

    def __call__(self):
        return self.value


class FakeUploads:
    """仅测试使用：模拟团队文件查询契约，不进入运行包默认实现。"""
    def __init__(self):
        self.files = {}

    def resolve_avatar(self, conn, *, user_id, file_id):
        row = self.files.get(file_id)
        if not row or row[0] != user_id:
            raise ApiError(40401,"文件不存在或不可用",404)
        return row[1]


class FakeCommunity:
    def __init__(self):
        self.calls = []

    def list_posts(self, conn, **kwargs):
        self.calls.append(kwargs)
        return {"list": [], "total": 0, "page": kwargs['page'], "pageSize": kwargs['page_size']}


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.settings = Settings(database_path=Path(self.temp.name)/'test.db',rate_limit_enabled=False,color_names=('米白','藏青'))
        self.uploads, self.community = FakeUploads(), FakeCommunity()
        self.app = create_app(self.settings,Integrations(self.community,self.uploads),self.clock)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.addCleanup(self.temp.cleanup)

    def register(self,email='alice@example.com',nickname='晓珊'):
        r=self.client.post('/api/v1/auth/register',json={'email':email,'password':'password123','nickname':nickname})
        self.assertEqual(r.status_code,200,r.text)
        return r

    def login(self,email='alice@example.com',password='password123',client=None):
        client=client or self.client
        r=client.post('/api/v1/auth/login',json={'email':email,'password':password})
        self.assertEqual(r.status_code,200,r.text)
        return r

    def auth(self,token):
        return {'Authorization':'Bearer '+token}

    def account(self,email='alice@example.com'):
        self.register(email)
        data=self.login(email).json()['data']
        return data['user']['id'],data['token']

    def test_register_is_not_login_and_normalizes_email(self):
        r=self.register(' Alice@Example.COM ')
        self.assertIsNone(r.json()['data'])
        self.assertNotIn('set-cookie',r.headers)
        self.assertEqual(self.client.get('/api/v1/me').status_code,401)
        with self.app.state.database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0],0)
            user=conn.execute('SELECT * FROM users').fetchone()
            self.assertEqual(user['email'],'alice@example.com')
            self.assertNotEqual(user['password_hash'],'password123')
        duplicate=self.client.post('/api/v1/auth/register',json={'email':'alice@example.com','nickname':'x','password':'password123'})
        self.assertEqual(duplicate.json()['code'],40901)

    def test_validation_and_login_do_not_leak_secrets(self):
        self.register()
        for body in [
            {'email':'bad','password':'secret','nickname':'x'},
            {'email':'a..b@example.com','password':'password123','nickname':'x'},
            {'email':'x@example.com','password':'password123','nickname':'   '},
            {'email':'x@example.com','password':'password123','nickname':'x','userId':'attacker'},
        ]:
            r=self.client.post('/api/v1/auth/register',json=body)
            self.assertEqual(r.json()['code'],40001)
            self.assertIsNone(r.json()['data'])
        r=self.client.post('/api/v1/auth/login',json={'email':'alice@example.com','password':'WRONG_SECRET'})
        self.assertEqual(r.json()['code'],40101)
        self.assertNotIn('WRONG_SECRET',r.text)
        self.assertNotIn('password_hash',self.login().text)

    def test_cookie_and_refresh_rotation_fixed_expiry(self):
        user_id,token=self.account()
        cookie=self.client.cookies.get('refresh_token')
        response=self.login()
        cookie_header=response.headers['set-cookie']
        self.assertIn('HttpOnly',cookie_header)
        self.assertIn('Path=/api/v1/auth',cookie_header)
        self.assertIn('SameSite=lax',cookie_header)
        token=response.json()['data']['token']
        cookie=self.client.cookies.get('refresh_token')
        self.clock.value+=7201
        self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(token)).status_code,401)
        renewed=self.client.post('/api/v1/auth/refresh')
        self.assertEqual(renewed.status_code,200,renewed.text)
        new=renewed.json()['data']['token']
        self.assertNotEqual(cookie,self.client.cookies.get('refresh_token'))
        self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(new)).status_code,200)
        self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(token)).status_code,401)
        with TestClient(self.app) as other:
            replay=other.post('/api/v1/auth/refresh',headers={'Cookie':'refresh_token='+cookie})
            self.assertEqual(replay.status_code,401)
        with self.app.state.database.connection() as conn:
            session=conn.execute('SELECT * FROM auth_sessions WHERE access_token_hash=?',(hash_token(new),)).fetchone()
            cutoff=session['refresh_expires_at']
        self.clock.value=cutoff-30
        r=self.client.post('/api/v1/auth/refresh')
        self.assertEqual(r.json()['data']['expiresIn'],30)
        self.clock.value=cutoff+1
        self.assertEqual(self.client.post('/api/v1/auth/refresh').status_code,401)

    def test_refresh_concurrent_replay_only_one_succeeds(self):
        self.account()
        cookie=self.client.cookies.get('refresh_token')
        def send(_):
            with TestClient(self.app) as c:
                return c.post('/api/v1/auth/refresh',headers={'Cookie':'refresh_token='+cookie}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(send,range(2)))
        self.assertEqual(sorted(results),[200,401])

    def test_patch_email_keeps_all_sessions_and_identity(self):
        uid,token=self.account()
        with TestClient(self.app) as device2:
            t2=self.login(client=device2).json()['data']['token']
            r=self.client.patch('/api/v1/me',headers=self.auth(token),json={'email':'new@example.com'})
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['data']['id'],uid)
            self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(token)).json()['data']['email'],'new@example.com')
            self.assertEqual(device2.get('/api/v1/me',headers=self.auth(t2)).status_code,200)
            self.assertEqual(device2.post('/api/v1/auth/refresh').status_code,200)
        self.assertEqual(self.client.post('/api/v1/auth/login',json={'email':'alice@example.com','password':'password123'}).status_code,401)
        self.login('new@example.com')

    def test_patch_protects_fields_and_atomic_avatar_updates(self):
        uid,token=self.account()
        self.register('bob@example.com')
        for data,code in [({'nickname':None},40001),({'id':'other'},40001),({'password_hash':'x'},40001),({'email':'bob@example.com'},40901)]:
            r=self.client.patch('/api/v1/me',headers=self.auth(token),json=data)
            self.assertEqual(r.json()['code'],code,r.text)
        self.uploads.files['file1']=(uid,'/public-avatar/file1.png')
        self.uploads.files['file2']=('other','/public-avatar/file2.png')
        r=self.client.patch('/api/v1/me',headers=self.auth(token),json={'avatarFileId':'file1'})
        self.assertEqual(r.json()['data']['avatar_url'],'/public-avatar/file1.png')
        r=self.client.patch('/api/v1/me',headers=self.auth(token),json={'nickname':'不应该保存','avatarFileId':'file2'})
        self.assertEqual(r.status_code,404)
        self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(token)).json()['data']['nickname'],'晓珊')

    def test_change_password_requires_old_and_revokes_all_devices(self):
        uid,token=self.account()
        with TestClient(self.app) as device2:
            token2=self.login(client=device2).json()['data']['token']
            wrong=self.client.post('/api/v1/me/change-password',headers=self.auth(token),json={'oldPassword':'wrong','newPassword':'newpassword123'})
            self.assertEqual(wrong.json()['code'],40001)
            self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(token)).status_code,200)
            changed=self.client.post('/api/v1/me/change-password',headers=self.auth(token),json={'oldPassword':'password123','newPassword':'newpassword123'})
            self.assertEqual(changed.status_code,200,changed.text)
            self.assertIsNone(changed.json()['data'])
            self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(token)).status_code,401)
            self.assertEqual(device2.get('/api/v1/me',headers=self.auth(token2)).status_code,401)
            self.assertEqual(device2.post('/api/v1/auth/refresh').status_code,401)
        self.login(password='newpassword123')

    def test_forgot_password_no_login_and_only_target_sessions_revoked(self):
        _,alice=self.account()
        self.register('bob@example.com')
        with TestClient(self.app) as bob,TestClient(self.app) as anonymous:
            btoken=self.login('bob@example.com',client=bob).json()['data']['token']
            response=anonymous.post('/api/v1/auth/forgot-password',json={'email':'alice@example.com','newPassword':'resetpass123'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertNotIn('set-cookie',response.headers)
            self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(alice)).status_code,401)
            self.assertEqual(self.client.post('/api/v1/auth/refresh').status_code,401)
            self.assertEqual(bob.get('/api/v1/me',headers=self.auth(btoken)).status_code,200)
            self.assertEqual(bob.post('/api/v1/auth/refresh').status_code,200)
        self.login(password='resetpass123')

    def test_logout_expired_access_and_other_device_survives(self):
        _,token=self.account()
        with TestClient(self.app) as other:
            token2=self.login(client=other).json()['data']['token']
            self.clock.value+=7201
            r=self.client.post('/api/v1/auth/logout',headers=self.auth(token))
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(self.client.post('/api/v1/auth/refresh').status_code,401)
            self.assertEqual(other.post('/api/v1/auth/refresh').status_code,200)
            self.assertEqual(self.client.post('/api/v1/auth/logout').status_code,200)

    def test_logout_mismatched_sessions_does_not_revoke(self):
        _,a=self.account()
        with TestClient(self.app) as other:
            b=self.login(client=other).json()['data']['token']
            r=other.post('/api/v1/auth/logout',headers=self.auth(a))
            self.assertEqual(r.json()['code'],40001)
            self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(a)).status_code,200)
            self.assertEqual(other.get('/api/v1/me',headers=self.auth(b)).status_code,200)

    def test_follow_counts_notifications_and_owner_privacy(self):
        aid,a=self.account()
        self.register('bob@example.com')
        with TestClient(self.app) as bob:
            login=self.login('bob@example.com',client=bob).json()['data']
            bid,b=login['user']['id'],login['token']
            for _ in range(2):
                self.assertEqual(self.client.post(f'/api/v1/users/{bid}/follow',headers=self.auth(a)).status_code,200)
            self.assertEqual(self.client.post(f'/api/v1/users/{aid}/follow',headers=self.auth(a)).json()['code'],40001)
            following=self.client.get('/api/v1/me/following',headers=self.auth(a)).json()['data']
            self.assertEqual(following['total'],1)
            self.assertNotIn('email',following['list'][0])
            notifications=bob.get('/api/v1/notifications',headers=self.auth(b)).json()['data']
            self.assertEqual(notifications['total'],1)
            nid=notifications['list'][0]['id']
            self.assertEqual(self.client.put(f'/api/v1/notifications/{nid}/read',headers=self.auth(a)).status_code,404)
            for _ in range(2):
                self.assertEqual(bob.put(f'/api/v1/notifications/{nid}/read',headers=self.auth(b)).status_code,200)
            for _ in range(2):
                self.client.delete(f'/api/v1/users/{bid}/follow',headers=self.auth(a))
            self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(a)).json()['data']['following_count'],0)
            self.assertEqual(bob.get('/api/v1/me',headers=self.auth(b)).json()['data']['follower_count'],0)
        self.assertEqual(self.client.get('/api/v1/me/following?page=0',headers=self.auth(a)).json()['code'],40001)

    def test_community_notification_idempotency_and_no_self_notify(self):
        aid,a=self.account()
        self.register('bob@example.com')
        with self.app.state.database.connection() as conn:
            bid=conn.execute('SELECT id FROM users WHERE email=?',('bob@example.com',)).fetchone()[0]
            with transaction(conn):
                args=dict(receiver_id=aid,sender_id=bid,kind='like',target_type='post',target_id='post1',event_key='event1',now=self.clock())
                self.assertTrue(create_notification(conn,**args))
                self.assertFalse(create_notification(conn,**args))
                self.assertFalse(create_notification(conn,**{**args,'sender_id':aid,'event_key':'self'}))
        self.assertEqual(self.client.get('/api/v1/notifications',headers=self.auth(a)).json()['data']['total'],1)

    def test_preferences_dictionaries_and_gateway_dispatch(self):
        _,a=self.account()
        self.assertEqual(self.client.get('/api/v1/me/style-preferences',headers=self.auth(a)).json()['data']['styles'],[])
        body={'styles':['casual'],'avoid_colors':['米白'],'notes':'不喜欢紧身'}
        self.assertEqual(self.client.put('/api/v1/me/style-preferences',headers=self.auth(a),json=body).json()['data'],body)
        self.assertEqual(self.client.put('/api/v1/me/style-preferences',headers=self.auth(a),json={'styles':[]}).status_code,400)
        self.assertEqual(self.client.put('/api/v1/me/style-preferences',headers=self.auth(a),json={**body,'styles':['y2k']}).status_code,400)
        self.assertEqual(self.client.get('/api/v1/dict',headers=self.auth(a)).json()['data']['colors'][0]['value'],'米白')
        for kind in ['posts','likes','favorites']:
            r=self.client.get('/api/v1/me/'+kind+'?page=2&pageSize=5',headers=self.auth(a))
            self.assertEqual(r.json()['data']['page'],2)
            self.assertEqual(self.community.calls[-1]['kind'],kind)
        self.assertEqual(self.client.get('/api/v1/me/favorites?pageSize=101',headers=self.auth(a)).status_code,400)

    def test_missing_integrations_explicit_and_no_partial_profile_save(self):
        self.app.state.integrations=Integrations()
        _,a=self.account()
        self.assertEqual(self.client.get('/api/v1/me/favorites',headers=self.auth(a)).status_code,503)
        response=self.client.patch('/api/v1/me',headers=self.auth(a),json={'nickname':'不能保存','avatarFileId':'file1'})
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.client.get('/api/v1/me',headers=self.auth(a)).json()['data']['nickname'],'晓珊')

    def test_cors_errors_and_rate_limiting(self):
        self.app.state.settings  # 固定设置用于生成Cookie；限流读取create_app闭包。
        other_app=create_app(replace(self.settings,rate_limit_enabled=True))
        with TestClient(other_app) as c:
            for _ in range(10):
                r=c.post('/api/v1/auth/login',json={'email':'unknown@example.com','password':'x'})
                self.assertEqual(r.status_code,401)
            r=c.post('/api/v1/auth/login',json={'email':'unknown@example.com','password':'x'},headers={'Origin':'http://localhost:5173'})
            self.assertEqual(r.status_code,429,r.text)
            self.assertEqual(r.json()['code'],42901)
            self.assertEqual(r.headers['access-control-allow-origin'],'http://localhost:5173')
            self.assertEqual(r.headers['access-control-allow-credentials'],'true')
            r=c.post('/api/v1/auth/refresh',headers={'Origin':'https://evil.example'})
            self.assertEqual(r.status_code,403)
            self.assertTrue(r.json()['requestId'].startswith('req_'))
            self.assertEqual(c.get('/api/v1/nonexistent').json()['code'],40401)

    def test_unexpected_error_is_enveloped_without_secret(self):
        _,a=self.account()
        class BrokenCommunity:
            def list_posts(self,*args,**kwargs):
                raise RuntimeError('PRIVATE_SECRET_TOKEN')
        self.app.state.integrations.community=BrokenCommunity()
        r=self.client.get('/api/v1/me/posts',headers=self.auth(a))
        self.assertEqual(r.status_code,500)
        self.assertEqual(r.json()['code'],50001)
        self.assertNotIn('PRIVATE_SECRET_TOKEN',r.text)
        self.assertIsNone(r.json()['data'])
        self.assertEqual(r.json()['requestId'],r.headers['x-request-id'])

    def test_database_reopen_keeps_user_session_and_preferences(self):
        _,a=self.account()
        self.client.put('/api/v1/me/style-preferences',headers=self.auth(a),json={'styles':['minimal'],'avoid_colors':[],'notes':'保存测试'})
        restarted=create_app(self.settings,clock=self.clock)
        with TestClient(restarted) as c:
            self.assertEqual(c.get('/api/v1/me',headers=self.auth(a)).status_code,200)
            self.assertEqual(c.get('/api/v1/me/style-preferences',headers=self.auth(a)).json()['data']['notes'],'保存测试')


if __name__ == '__main__':
    unittest.main()
