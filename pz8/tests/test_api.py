import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, ExitStack
from pathlib import Path

from fastapi.testclient import TestClient

from planner.main import create_app
from planner.models.events import EventRead
from planner.models.users import NewUser, User


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / 'nested' / 'planner.db'
        self.url = f'sqlite:///{self.db_path}'
        self.app = create_app(self.url)
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.client = stack.enter_context(TestClient(self.app))
        self.user = {'email': 'fastapi@packt.com', 'password': 'Stro0ng!'}
        self.event = {
            'title': 'FastAPI Book Launch',
            'image': 'https://example.com/book.png',
            'description': 'Обсуждение книги FastAPI',
            'tags': ['python', 'fastapi'],
            'location': 'Google Meet',
        }

    def create_event(self, **changes):
        response = self.client.post('/event/new', json=dict(self.event, **changes))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['id']

    def test_schema_created_on_startup(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({'events', 'users'} <= tables)
            columns = {row[1]: row for row in db.execute('PRAGMA table_info(events)')}
            self.assertEqual(columns['id'][5], 1)
            self.assertEqual(columns['tags'][2], 'JSON')

    def test_registration_and_signin(self):
        response = self.client.post('/user/signup', json=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('password', response.json())
        self.assertEqual(self.client.post('/user/signin', json=self.user).status_code, 200)
        self.assertEqual(self.client.post('/user/signup', json=self.user).status_code, 409)
        wrong_password = dict(self.user, password='incorrect')
        self.assertEqual(self.client.post('/user/signin', json=wrong_password).status_code, 403)
        # A uniqueness conflict must not break later requests.
        self.assertEqual(self.client.post('/user/signin', json=self.user).status_code, 200)

    def test_password_is_hashed_with_unique_salt(self):
        self.client.post('/user/signup', json=self.user)
        second = dict(self.user, email='second@packt.com')
        self.client.post('/user/signup', json=second)
        with closing(sqlite3.connect(self.db_path)) as db:
            hashes = [row[0] for row in db.execute('SELECT password_hash FROM users ORDER BY id')]
        self.assertEqual(len(hashes), 2)
        self.assertNotEqual(hashes[0], hashes[1])
        for encoded in hashes:
            self.assertTrue(encoded.startswith('scrypt$'))
            self.assertNotIn(self.user['password'], encoded)

    def test_unknown_user_and_validation(self):
        self.assertEqual(self.client.post('/user/signin', json=self.user).status_code, 404)
        for payload in ({'email': 'invalid', 'password': 'x'}, {'email': self.user['email']},
                        dict(self.user, password='')):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/user/signup', json=payload).status_code, 422)

    def test_event_lifecycle(self):
        self.assertEqual(self.client.get('/event/').json(), [])
        event_id = self.create_event()
        expected = dict(self.event, id=event_id)
        self.assertEqual(self.client.get(f'/event/{event_id}').json(), expected)
        self.assertEqual(self.client.get('/event/').json(), [expected])
        self.assertEqual(self.client.delete(f'/event/delete/{event_id}').status_code, 200)
        self.assertEqual(self.client.get(f'/event/{event_id}').status_code, 404)
        self.assertEqual(self.client.delete(f'/event/delete/{event_id}').status_code, 404)

    def test_automatic_ids_and_legacy_explicit_id(self):
        first = self.create_event()
        second = self.create_event()
        self.assertGreater(second, first)
        self.create_event(id=100)
        self.assertEqual(self.client.post('/event/new', json=dict(self.event, id=100)).status_code, 409)
        self.assertGreater(self.create_event(), 100)

    def test_partial_update_preserves_other_fields(self):
        event_id = self.create_event()
        response = self.client.put(f'/event/edit/{event_id}', json={'location': 'Hybrid'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(self.event, id=event_id, location='Hybrid'))
        self.assertEqual(self.client.get(f'/event/{event_id}').json(), response.json())
        self.assertEqual(self.client.put('/event/edit/9999', json={'title': 'New'}).status_code, 404)

    def test_update_json_tags_and_empty_values(self):
        event_id = self.create_event()
        changes = {'tags': ['sqlite', 'SQLModel', 'тест'], 'description': '', 'image': ''}
        response = self.client.put(f'/event/edit/{event_id}', json=changes)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(self.event, id=event_id, **changes))
        response = self.client.put(f'/event/edit/{event_id}', json={'tags': []})
        self.assertEqual(response.json()['tags'], [])
        self.assertEqual(self.client.get(f'/event/{event_id}').json()['tags'], [])

    def test_invalid_updates_leave_database_unchanged(self):
        event_id = self.create_event()
        for payload in ({'location': None}, {'tags': None}, {'title': ''},
                        {'id': 42}, {'tags': 'python'}, {'unknown': 'value'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.put(f'/event/edit/{event_id}', json=payload).status_code, 422)
                self.assertEqual(self.client.get(f'/event/{event_id}').json(), dict(self.event, id=event_id))
        self.assertEqual(self.client.put(f'/event/edit/{event_id}', json={}).status_code, 200)

    def test_clear_multiple_events(self):
        self.create_event()
        self.create_event()
        self.client.post('/user/signup', json=self.user)
        self.assertEqual(self.client.delete('/event/').status_code, 200)
        self.assertEqual(self.client.get('/event/').json(), [])
        self.assertEqual(self.client.delete('/event/').status_code, 200)
        self.assertEqual(self.client.post('/user/signin', json=self.user).status_code, 200)

    def test_invalid_events(self):
        for payload in ({}, dict(self.event, id=0), dict(self.event, id=-1),
                        dict(self.event, tags='python'), dict(self.event, title=''),
                        dict(self.event, location=None)):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/event/new', json=payload).status_code, 422)
        for path in ('/event/not-an-id', '/event/0', '/event/-1'):
            self.assertEqual(self.client.get(path).status_code, 422)
        self.assertEqual(self.client.get('/event/').json(), [])

    def test_legacy_routes(self):
        event_id = self.create_event()
        self.assertEqual(self.client.put(f'/event/{event_id}', json={'title': 'Updated'}).status_code, 200)
        self.assertEqual(self.client.delete(f'/event/{event_id}').status_code, 200)

    def test_persistence_across_application_recreation(self):
        # Independent engines and lifespans share only the on-disk SQLite file.
        db_url = f'sqlite:///{Path(self.directory.name) / "restart.db"}'
        with TestClient(create_app(db_url)) as first:
            event_id = first.post('/event/new', json=self.event).json()['id']
            first.post('/user/signup', json=self.user)
            first.put(f'/event/edit/{event_id}', json={'location': 'Hybrid', 'tags': ['sqlite']})
        with TestClient(create_app(db_url)) as second:
            self.assertEqual(second.get(f'/event/{event_id}').json(),
                             dict(self.event, id=event_id, location='Hybrid', tags=['sqlite']))
            self.assertEqual(second.post('/user/signin', json=self.user).status_code, 200)
            second.delete(f'/event/delete/{event_id}')
        with TestClient(create_app(db_url)) as third:
            self.assertEqual(third.get('/event/').json(), [])
            self.assertEqual(third.post('/user/signin', json=self.user).status_code, 200)

    def test_user_events_are_independent_snapshots(self):
        event_id = self.create_event()
        snapshot = dict(self.event, id=event_id)
        user = dict(self.user, events=[snapshot])
        self.assertEqual(self.client.post('/user/signup', json=user).status_code, 200)
        self.client.delete(f'/event/delete/{event_id}')
        with closing(sqlite3.connect(self.db_path)) as db:
            saved = json.loads(db.execute('SELECT events FROM users').fetchone()[0])
        self.assertEqual(saved, [snapshot])

    def test_user_model_defaults_and_public_fields(self):
        first = NewUser(**self.user)
        second = NewUser(email='second@packt.com', password='secret')
        first.events.append(EventRead(**self.event, id=1))
        self.assertEqual(second.events, [])
        self.assertNotIn('password', User.model_validate(first.model_dump()).model_dump())

    def test_docs(self):
        self.assertEqual(self.client.get('/docs').status_code, 200)
        schema = self.client.get('/openapi.json').json()
        self.assertIn('/user/signup', schema['paths'])
        self.assertIn('/event/edit/{id}', schema['paths'])
        self.assertIn('/event/delete/{id}', schema['paths'])
        self.assertNotIn('password_hash', json.dumps(schema))
        self.assertEqual(self.client.get('/', follow_redirects=False).headers['location'], '/docs')


if __name__ == '__main__':
    unittest.main()
