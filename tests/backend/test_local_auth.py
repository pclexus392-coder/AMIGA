"""Real bcrypt/JWT authentication against isolated SQLite; no Google/AWS calls."""
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
from io import StringIO, BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import jwt
from sqlalchemy import select, text, func
from backend.application import create_app
from backend.auth_tokens import signing_key, verify_token
from backend.local_auth import setup_admin, hash_password, verify_password, prepare_owner_setup
from backend.models import User, LocalCredential, Role, Membership, Client, Setting, AuthSession, Audit, WorkRequest
from test_api import pdf_bytes

PASSWORD = 'Fictional-AMIGA-Password!'


class LocalAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = hash_password(PASSWORD)

    def setUp(self):
        root = Path(__file__).resolve().parents[2] / '.runtime-temp'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.temp.name)
        self.options = dict(TESTING=True, START_QUEUE_WORKER=False, SECRET_KEY='test-key-local-only',
            DATABASE_URL='sqlite:///' + (self.path / 'local.db').as_posix(), UPLOAD_DIR=self.path / 'documents',
            AUTH_METHOD='local_password', GOOGLE_CLIENT_ID='', ADMIN_BOOTSTRAP_EMAIL='first.owner@example.test')
        self.app = create_app(self.options)
        self.db = self.app.extensions['amiga_db']
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.extensions['amiga_engine'].dispose()
        self.temp.cleanup()

    def post(self, path, data, client=None):
        client = client or self.client
        token = client.get('/api/auth/csrf').json['data']['csrf_token']
        return client.post(path, json=data, headers={'X-CSRF-Token': token})

    def login(self, email='first.owner@example.test/atmin', password=PASSWORD, client=None):
        return self.post('/api/auth/login', {'email_input': email, 'password': password}, client)

    def setup_owner(self):
        with redirect_stdout(StringIO()):
            return setup_admin(self.app, Mock(side_effect=[PASSWORD, PASSWORD]))

    def seed(self, identifier, client_id):
        with self.db.begin() as db:
            db.add(User(id=identifier, email=identifier+'@example.test', display_name=identifier, account_status='ACTIVE'))
            if not db.get(Client, client_id):
                db.add(Client(id=client_id, name='Klien '+client_id))
            db.flush()
            db.add(LocalCredential(user_id=identifier, password_hash=self.encoded))
            db.add(Role(user_id=identifier, role='CLIENT_OWNER'))
            db.add(Membership(user_id=identifier, client_id=client_id))

    def test_local_is_available_without_google_and_requires_csrf(self):
        config = self.client.get('/api/auth/csrf').json['data']
        self.assertTrue(config['auth_configured'])
        self.assertEqual(config['auth_method'], 'local_password')
        self.assertEqual(config['google_client_id'], '')
        self.assertEqual(self.client.post('/api/auth/register', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/auth/login', json={}).status_code, 403)
        self.assertEqual(self.client.get('/api/requests').status_code, 401)
        self.assertEqual(self.post('/api/auth/google', {}).status_code, 503)

    def test_registration_hashes_password_and_suffix_never_grants_admin(self):
        response = self.post('/api/auth/register', {'email_input':'New.User+amiga@example.test /atmin', 'password':PASSWORD, 'display_name':'New User'})
        self.assertEqual(response.status_code, 201, response.json)
        data = response.json['data']
        self.assertEqual(data['user']['email'], 'new.user+amiga@example.test')
        self.assertEqual(data['portal'], 'pending')
        self.assertEqual(data['user']['roles'], [])
        self.assertNotIn(PASSWORD, response.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/requests').status_code, 403)
        with self.db() as db:
            credential = db.get(LocalCredential, data['user']['id'])
            self.assertTrue(credential.password_hash.startswith('$2b$12$'))
            self.assertTrue(verify_password(PASSWORD, credential.password_hash))
            self.assertEqual(credential.admin_bootstrap_allowed, 0)
            self.assertEqual(db.get(Setting, 'bootstrap_consumed').value, '0')
            self.assertNotIn(PASSWORD, repr(list(db.scalars(select(Audit.changes)))))

    def test_normal_registration_creates_private_client_workspace_without_staff_roles(self):
        first=self.post('/api/auth/register',{'email_input':'normal@example.test','password':PASSWORD,'display_name':'Normal Client','roles':['SYSTEM_ADMIN'],'client_ids':['A']})
        self.assertEqual(first.status_code,201,first.json)
        data=first.json['data']
        self.assertEqual(data['portal'],'client')
        self.assertEqual(data['user']['roles'],['CLIENT_OWNER'])
        self.assertEqual(data['user']['account_status'],'ACTIVE')
        self.assertEqual(len(data['user']['clients']),1)
        other=self.app.test_client()
        second=self.post('/api/auth/register',{'email_input':'second@example.test','password':PASSWORD},other).json['data']
        self.assertNotEqual(data['user']['clients'][0]['id'],second['user']['clients'][0]['id'])
        self.assertEqual(self.client.get('/api/admin/users').status_code,403)
        self.assertEqual(self.client.get('/api/requests').status_code,200)
        self.assertEqual(self.login(email='normal@example.test/view').status_code,403)
        self.assertEqual(self.login(email='normal@example.test').json['data']['portal'],'client')

    def test_view_requires_one_admin_approval_without_client_assignment(self):
        self.assert_reviewer_activation('/VIEW')

    def test_review_requires_one_admin_approval_without_client_assignment(self):
        self.assert_reviewer_activation('/ReViEw')

    def assert_reviewer_activation(self, suffix):
        response=self.post('/api/auth/register',{'email_input':'Reviewer.Test+amiga@example.test '+suffix,'password':PASSWORD})
        self.assertEqual(response.status_code,201,response.json)
        user=response.json['data']['user']
        self.assertEqual(user['email'],'reviewer.test+amiga@example.test')
        self.assertEqual(user['account_status'],'PENDING_REVIEWER')
        self.assertEqual(user['requested_role'],'FINANCE_REVIEWER')
        self.assertEqual(user['roles'],[])
        self.assertEqual(self.client.get('/api/requests').status_code,403)
        self.setup_owner()
        admin=self.app.test_client()
        self.assertEqual(self.login(client=admin).status_code,200)
        with self.db.begin() as db:
            db.add(Client(id='A',name='Klien A'))
        csrf=admin.get('/api/auth/csrf').json['data']['csrf_token']
        activated=admin.patch('/api/admin/users/'+user['id'],json={'account_status':'ACTIVE','roles':['FINANCE_REVIEWER'],'client_ids':[]},headers={'X-CSRF-Token':csrf})
        self.assertEqual(activated.status_code,200,activated.json)
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.assertEqual(self.login(email=user['email']).json['data']['portal'],'reviewer')
        self.assertEqual(self.client.get('/api/tasks').status_code,200)
        self.assertEqual(self.login(email=user['email']+'/view').json['data']['user']['roles'],['FINANCE_REVIEWER'])
        self.assertEqual(self.login(email=user['email']+'/review').json['data']['user']['roles'],['FINANCE_REVIEWER'])

    def test_unknown_or_stacked_suffix_is_rejected_before_account_creation(self):
        for email in ['new@example.test/admin','new@example.test/atmin/view','new@example.test/view/atmin',
                      'new@example.test/review/atmin','new@example.test/review/view','new@example.test/atmin/review']:
            response=self.post('/api/auth/register',{'email_input':email,'password':PASSWORD})
            self.assertEqual(response.status_code,422)

    def test_owner_cannot_register_publicly_or_claim_admin_by_email(self):
        response = self.post('/api/auth/register', {'email_input':'first.owner@example.test/atmin', 'password':PASSWORD})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json['error']['code'], 'OWNER_SETUP_REQUIRED')
        self.assertEqual(self.login().status_code, 401)
        with self.db() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 0)

    def test_launcher_link_allows_owner_to_choose_password_in_form_once(self):
        token = prepare_owner_setup(self.app)
        self.assertIsNotNone(token)
        config = self.client.get('/api/auth/csrf').json
        self.assertNotIn(token, repr(config))
        response = self.post('/api/auth/owner-setup', {'setup_token':token})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['email_input'], 'first.owner@example.test/atmin')
        config=self.client.get('/api/auth/csrf').json['data']
        self.assertEqual(config['owner_setup_email_input'],'first.owner@example.test/atmin')
        self.assertNotIn(token,repr(config))
        with self.db() as db:
            self.assertNotIn(token, db.get(Setting,'owner_setup').value)
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 0)
        payload = {'email_input':'first.owner@example.test/atmin', 'display_name':'First Owner', 'password':PASSWORD}
        response = self.post('/api/auth/register', payload)
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['data']['portal'], 'admin')
        self.assertEqual(response.json['data']['user']['roles'], ['SYSTEM_ADMIN'])
        self.assertEqual(self.client.get('/api/admin/users').status_code, 200)
        self.assertNotIn('owner_setup_email_input',self.client.get('/api/auth/csrf').json['data'])
        self.post('/api/auth/logout', {})
        self.assertEqual(self.login(email='first.owner@example.test').json['data']['portal'], 'admin')
        self.assertEqual(self.post('/api/auth/register', payload).status_code, 403)
        self.assertEqual(self.post('/api/auth/owner-setup', {'setup_token':token}).status_code, 403)
        self.assertIsNone(prepare_owner_setup(self.app))
        with self.db() as db:
            self.assertEqual(db.get(Setting, 'owner_setup').value, '')
            credential=db.scalar(select(LocalCredential))
            self.assertTrue(verify_password(PASSWORD, credential.password_hash))

    def test_setup_token_wrong_expired_rotated_and_other_email_are_rejected(self):
        first = prepare_owner_setup(self.app)
        second = prepare_owner_setup(self.app)
        self.assertNotEqual(first, second)
        for token in (None, 'invalid', first, 'x'*43):
            self.assertEqual(self.post('/api/auth/owner-setup', {'setup_token':token}).status_code, 403)
            response=self.post('/api/auth/register', {'email_input':'first.owner@example.test/atmin', 'password':PASSWORD, 'setup_token':token})
            self.assertEqual(response.status_code, 403)
        response=self.post('/api/auth/register', {'email_input':'other@example.test/atmin', 'password':PASSWORD, 'setup_token':second})
        self.assertEqual(response.status_code, 403)
        with self.db.begin() as db:
            import json
            record=db.get(Setting,'owner_setup')
            value=json.loads(record.value)
            value['expires_at']='2000-01-01T00:00:00.000000Z'
            record.value=json.dumps(value)
        self.assertEqual(self.post('/api/auth/owner-setup', {'setup_token':second}).status_code, 403)
        with self.db() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)),0)

    def test_setup_validation_failure_keeps_token_and_requires_csrf_and_marker(self):
        token=prepare_owner_setup(self.app)
        self.assertEqual(self.client.post('/api/auth/owner-setup',json={'setup_token':token}).status_code,403)
        payload={'email_input':'first.owner@example.test','password':PASSWORD,'setup_token':token}
        self.assertEqual(self.post('/api/auth/register',payload).status_code,422)
        payload.update(email_input='first.owner@example.test/atmin',password='short')
        self.assertEqual(self.post('/api/auth/register',payload).status_code,422)
        self.assertEqual(self.post('/api/auth/owner-setup',{'setup_token':token}).status_code,200)
        payload['password']=PASSWORD
        self.assertEqual(self.post('/api/auth/register',payload).status_code,201)

    def test_simultaneous_owner_registration_consumes_capability_once(self):
        from concurrent.futures import ThreadPoolExecutor
        token=prepare_owner_setup(self.app)
        payload={'email_input':'first.owner@example.test/atmin','password':PASSWORD,'setup_token':token}
        def register_once(_):
            return self.post('/api/auth/register',payload,self.app.test_client()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(register_once,range(2))),[201,403])
        with self.db() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Role).where(Role.role=='SYSTEM_ADMIN')),1)

    def test_local_assets_do_not_cache_old_login_and_health_identifies_auth_method(self):
        for path in ('/login','/portal/src/js/api-client.js'):
            response=self.client.get(path)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            response.close()
        self.assertEqual(self.client.get('/health').json['auth_method'],'local_password')

    def test_trusted_setup_then_suffix_activates_once_and_plain_email_returns_admin(self):
        self.assertTrue(self.setup_owner())
        reader = Mock(side_effect=AssertionError('Must not prompt again'))
        self.assertFalse(setup_admin(self.app, reader))
        reader.assert_not_called()
        response = self.login(email='first.owner@example.test')
        self.assertEqual(response.json['data']['portal'], 'pending')
        response = self.login()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['user']['roles'], ['SYSTEM_ADMIN'])
        self.assertEqual(response.json['data']['portal'], 'admin')
        self.assertEqual(self.client.get('/api/admin/users').status_code, 200)
        self.post('/api/auth/logout', {})
        response = self.login(email='first.owner@example.test')
        self.assertEqual(response.json['data']['portal'], 'admin')
        with self.db() as db:
            self.assertEqual(db.get(Setting,'bootstrap_consumed').value, '1')
            self.assertEqual(db.scalar(select(LocalCredential)).admin_bootstrap_allowed, 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Role).where(Role.role=='SYSTEM_ADMIN')), 1)

    def test_wrong_password_lockout_persists_and_expires(self):
        self.setup_owner()
        self.assertEqual(self.login(password='wrong-password!').json['error']['code'], 'INVALID_CREDENTIALS')
        for _ in range(4):
            self.assertEqual(self.login(password='wrong-password!').status_code, 401)
        self.assertEqual(self.login().status_code, 429)
        with self.db.begin() as db:
            credential = db.scalar(select(LocalCredential))
            self.assertEqual(credential.failed_attempts, 5)
            self.assertIsNotNone(credential.locked_until)
            credential.locked_until = '2000-01-01T00:00:00.000000Z'
        self.assertEqual(self.login().status_code, 200)
        with self.db() as db:
            credential = db.scalar(select(LocalCredential))
            self.assertEqual(credential.failed_attempts, 0)
            self.assertIsNone(credential.locked_until)

    def test_jwt_is_signed_expires_and_logout_revokes_replayed_cookie(self):
        self.setup_owner()
        old_csrf = self.client.get('/api/auth/csrf').json['data']['csrf_token']
        response = self.login()
        self.assertNotEqual(old_csrf, response.json['data']['csrf_token'])
        cookie = self.client.get_cookie('amiga_session')
        self.assertTrue(cookie.http_only)
        self.assertEqual(cookie.same_site, 'Lax')
        with self.client.session_transaction() as session:
            original = session['auth']
            claims = verify_token(original, self.app.config)
            self.assertEqual(claims['sub'], response.json['data']['user']['id'])
            self.assertNotIn('password', claims)
            session['auth'] = original[:-8]+'tampered'
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
        with self.client.session_transaction() as session:
            session['auth'] = jwt.encode({**claims, 'exp':datetime.now(timezone.utc)-timedelta(seconds=5)}, signing_key(self.app.config), algorithm='HS256')
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        old_cookie = self.client.get_cookie('amiga_session').value
        self.assertEqual(self.post('/api/auth/logout', {}).status_code, 200)
        replay = self.app.test_client()
        replay.set_cookie('amiga_session', old_cookie)
        self.assertEqual(replay.get('/api/auth/me').status_code, 401)
        self.assertNotIn(original, response.get_data(as_text=True))

    def test_duplicate_email_password_limits_and_google_account_cannot_be_taken_over(self):
        for password in ['short', 'a'*73, '界'*25, None]:
            self.assertEqual(self.post('/api/auth/register', {'email_input':'a@example.test', 'password':password}).status_code, 422)
        self.seed('existing', 'A')
        self.assertEqual(self.post('/api/auth/register', {'email_input':'existing@example.test', 'password':PASSWORD}).status_code, 409)
        with self.db.begin() as db:
            db.add(User(id='google', email='google@example.test', google_sub='verified-sub', display_name='G', account_status='ACTIVE'))
        self.assertEqual(self.post('/api/auth/register', {'email_input':'google@example.test', 'password':PASSWORD}).status_code, 409)
        self.assertEqual(self.login(email='google@example.test').status_code, 401)

    def test_local_jwt_uses_server_ownership_and_tenant_filters(self):
        self.seed('alice', 'A')
        self.seed('bob', 'B')
        with self.db.begin() as db:
            db.add(WorkRequest(id='bob-request', client_id='B', uploaded_by='bob', request_type='Invoice', channel='Portal', request_date='2026-01-01', deadline='2026-01-05', updated_at='2026-01-01T00:00:00Z'))
        self.assertEqual(self.login(email='alice@example.test').status_code, 200)
        self.assertEqual(self.client.get('/api/requests').json['data']['total'], 0)
        self.assertEqual(self.client.get('/api/requests/bob-request').status_code, 404)
        csrf = self.client.get('/api/auth/csrf').json['data']['csrf_token']
        self.assertEqual(self.client.get('/api/admin/users').status_code, 403)
        data = {'client_id':'A', 'uploaded_by':'bob', 'user_id':'bob', 'request_type':'Invoice', 'channel':'Portal',
                'request_date':'2026-01-01', 'deadline':'2026-01-05', 'invoice_file':(BytesIO(pdf_bytes()),'invoice.pdf')}
        response = self.client.post('/api/requests', data=data, headers={'X-CSRF-Token':csrf})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['data']['uploaded_by'], 'alice')
        with self.db.begin() as db:
            db.get(User,'alice').account_status='DISABLED'
        self.assertEqual(self.client.get('/api/auth/me').status_code, 403)
        self.assertEqual(self.login(email='alice@example.test').status_code, 403)

    def test_setup_mismatch_or_existing_other_admin_never_changes_accounts(self):
        with redirect_stdout(StringIO()), self.assertRaises(ValueError):
            setup_admin(self.app, Mock(side_effect=[PASSWORD,'different-password']))
        with self.db.begin() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)),0)
            db.add(User(id='other-admin', email='other@example.test', display_name='Other', account_status='ACTIVE'))
            db.flush()
            db.add(Role(user_id='other-admin', role='SYSTEM_ADMIN'))
        reader=Mock(side_effect=AssertionError('Must not prompt'))
        with self.assertRaises(ValueError):
            setup_admin(self.app, reader)
        reader.assert_not_called()

    def test_v1_upgrade_is_additive_and_sessions_survive_restart(self):
        self.setup_owner()
        self.login()
        with self.db.begin() as db:
            user_id = db.scalar(select(User.id))
            db.get(Setting, 'schema_version').value='1'
            db.execute(text('CREATE TABLE legacy_sample (id INTEGER PRIMARY KEY, value TEXT)'))
            db.execute(text("INSERT INTO legacy_sample VALUES (1,'preserved')"))
        restarted = create_app(self.options)
        try:
            with restarted.extensions['amiga_db']() as db:
                self.assertEqual(db.get(Setting,'schema_version').value, '4')
                self.assertEqual(db.execute(text('SELECT value FROM legacy_sample')).scalar(), 'preserved')
                self.assertTrue(verify_password(PASSWORD, db.get(LocalCredential, user_id).password_hash))
            client = restarted.test_client()
            client.set_cookie('amiga_session', self.client.get_cookie('amiga_session').value)
            self.assertEqual(client.get('/api/auth/me').status_code, 200)
        finally:
            restarted.extensions['amiga_engine'].dispose()
