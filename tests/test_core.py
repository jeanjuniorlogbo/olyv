"""Tests : python -m unittest discover -s tests -v
Nécessite une base de test (variables DB_* de l'environnement) où schema.sql est chargé.
ATTENTION : vide les tables utilisateurs de cette base."""
import io
import json
import os
import unittest

for key, value in {'DB_NAME': 'Olyvera_test', 'DB_USER': 'Olyvera_app', 'DB_PASS': 'testpass'}.items():
    os.environ.setdefault(key, value)

import psycopg                                             # noqa: E402
from app import (auth, db, routes_account, routes_admin, routes_auth, routes_doctor,    # noqa: E402,F401
                 routes_facility, routes_pages, routes_patient, security)
from app.security import RateLimiter, can_access           # noqa: E402
from app.web import application                            # noqa: E402


def call(method, path, body=None, cookie=None, headers=None, json_ct=True):
    raw = json.dumps(body).encode() if body is not None else b''
    path, _, query = path.partition('?')
    environ = {
        'REQUEST_METHOD': method, 'PATH_INFO': path, 'QUERY_STRING': query, 'REMOTE_ADDR': '127.0.0.1',
        'HTTP_HOST': 'localhost:7171', 'wsgi.input': io.BytesIO(raw),
        'CONTENT_LENGTH': str(len(raw)),
        'CONTENT_TYPE': 'application/json' if json_ct else 'text/plain',
    }
    if cookie:
        environ['HTTP_COOKIE'] = cookie
    environ.update(headers or {})
    out = {}
    body_out = application(environ, lambda status, hdrs: out.update(status=status, headers=hdrs))
    data = b''.join(body_out)
    hdrs = {}
    for name, value in out['headers']:
        hdrs.setdefault(name.lower(), []).append(value)
    try:
        parsed = json.loads(data)
    except ValueError:
        parsed = None
    return int(out['status'][:3]), hdrs, parsed, data


PATIENT = {'last_name': 'Diallo', 'first_name': 'Awa', 'email': 'Awa@Example.com',
           'phone': '+229 97 00 00 01', 'password': 'motdepasse1',
           'password_confirmation': 'motdepasse1', 'terms': True}


def reset_state():
    db.execute('TRUNCATE users, sessions, access_logs, notifications RESTART IDENTITY CASCADE')
    db.execute("""INSERT INTO platform_settings (ps_key, ps_value) VALUES ('registration_open', '1')
                  ON CONFLICT (ps_key) DO UPDATE SET ps_value = '1'""")
    for limiter in (routes_auth._login_by_account, routes_auth._login_by_ip, routes_auth._register_by_ip):
        limiter._hits.clear()


def session_cookie(headers):
    return headers['set-cookie'][0].split(';')[0]


class UnitTests(unittest.TestCase):
    def test_rate_limiter(self):
        limiter = RateLimiter(2, 60)
        limiter.hit('a'); self.assertFalse(limiter.blocked('a'))
        limiter.hit('a'); self.assertTrue(limiter.blocked('a'))
        limiter.reset('a'); self.assertFalse(limiter.blocked('a'))

    def test_static_traversal_and_types(self):
        for path in ('/static/../config.py', '/static/..%2fconfig.py', '/static/.env',
                     '/static/schema.sql', '/static/a/b.css', '/static/inexistant.css'):
            self.assertEqual(call('GET', path)[0], 404, path)
        self.assertEqual(call('GET', '/static/style.css')[0], 200)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        reset_state()

    def test_pages_headers_and_errors(self):
        status, headers, _, body = call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('content-security-policy', headers)
        self.assertEqual(headers['cache-control'], ['no-store'])
        self.assertNotIn(b'Traceback', body)
        self.assertEqual(call('GET', '/patient')[:1] + (call('GET', '/patient')[1]['location'],), (302, ['/login']))
        self.assertEqual(call('GET', '/api/me')[0], 401)
        self.assertEqual(call('GET', '/inexistant')[0], 404)
        self.assertEqual(call('PUT', '/login')[0], 405)

    def test_register_creates_full_patient(self):
        status, _, data, _ = call('POST', '/register', PATIENT)
        self.assertEqual(status, 201, data)
        row = db.fetch_one("""SELECT p.p_first_name, p.p_last_name, p.p_gender::text g, u.u_email,
                              (SELECT count(*) FROM medical_records WHERE mr_patient_id = p.p_id) mr,
                              (SELECT count(*) FROM notifications WHERE n_user_id = u.u_id) n
                              FROM patients p JOIN users u ON u.u_id = p.p_user_id""")
        self.assertEqual((row['p_first_name'], row['p_last_name'], row['u_email']),
                         ('Awa', 'Diallo', 'awa@example.com'))
        self.assertEqual((row['mr'], row['n']), (1, 1))
        # doublon e-mail (casse différente) puis doublon téléphone : 409, jamais 500
        self.assertEqual(call('POST', '/register', PATIENT)[0], 409)
        other = dict(PATIENT, email='autre@example.com')
        self.assertEqual(call('POST', '/register', other)[0], 409)

    def test_register_rejects_bad_input(self):
        for patch in ({'email': 123}, {'email': 'pas-un-email'}, {'last_name': ['x']},
                      {'password': 'court', 'password_confirmation': 'court'},
                      {'password_confirmation': 'autre'}, {'terms': False}, {'phone': 'abc'}):
            status, _, data, _ = call('POST', '/register', dict(PATIENT, **patch))
            self.assertEqual(status, 400, (patch, data))
        self.assertEqual(db.fetch_one('SELECT count(*) c FROM users')['c'], 0)
        self.assertEqual(call('POST', '/register', PATIENT, json_ct=False)[0], 415)
        self.assertEqual(call('POST', '/register', PATIENT,
                              headers={'HTTP_ORIGIN': 'http://evil.example'})[0], 403)

    def _login(self, password='motdepasse1'):
        return call('POST', '/login', {'email': 'awa@example.com', 'password': password})

    def test_login_session_roles_logout(self):
        call('POST', '/register', PATIENT)
        status, headers, _, _ = self._login()
        self.assertEqual(status, 200)
        cookie_header = headers['set-cookie'][0]
        self.assertIn('HttpOnly', cookie_header)
        cookie = session_cookie(headers)
        token = cookie.split('=', 1)[1]
        stored = db.fetch_one('SELECT s_token FROM sessions')['s_token']
        self.assertNotEqual(stored, token)                       # seul le hash est en base

        self.assertEqual(call('GET', '/api/me', cookie=cookie)[2]['data']['role'], 'patient')
        self.assertEqual(call('GET', '/', cookie=cookie)[1]['location'], ['/patient'])
        self.assertEqual(call('GET', '/patient', cookie=cookie)[0], 200)
        self.assertEqual(call('GET', '/medecin', cookie=cookie)[1]['location'], ['/'])
        self.assertEqual(call('GET', '/login', cookie=cookie)[1]['location'], ['/'])

        db.execute('UPDATE users SET u_is_active = false')       # compte suspendu : session morte
        self.assertEqual(call('GET', '/api/me', cookie=cookie)[0], 401)
        db.execute('UPDATE users SET u_is_active = true')
        self.assertEqual(call('GET', '/api/me', cookie=cookie)[0], 200)

        self.assertEqual(call('POST', '/logout', cookie=cookie)[0], 200)
        self.assertEqual(call('GET', '/api/me', cookie=cookie)[0], 401)

    def test_login_failures_and_rate_limit(self):
        call('POST', '/register', PATIENT)
        for _ in range(5):
            self.assertEqual(self._login('faux-mdp')[0], 401)
        self.assertEqual(self._login('faux-mdp')[0], 429)
        self.assertEqual(self._login()[0], 429)                  # même le bon mot de passe
        self.assertEqual(call('POST', '/login', {'email': 5, 'password': 'x'})[0], 400)
        denied = db.fetch_one("SELECT count(*) c FROM access_logs WHERE alog_action='login' AND alog_result='denied'")
        self.assertGreaterEqual(denied['c'], 5)                  # échecs tracés

    def _make_doctor(self, verified=True):
        role = db.fetch_one("SELECT r_id FROM roles WHERE r_type='medecin'")['r_id']
        user = db.fetch_one("INSERT INTO users (u_email,u_phone,u_password,u_role_id) VALUES ('dr@x.com','+22900',%s,%s) RETURNING u_id",
                            (auth.hash_password('x' * 10), role))
        db.execute("INSERT INTO doctors (d_user_id,d_first_name,d_last_name,d_professional_id,d_specialty,d_verification_status) VALUES (%s,'A','B','PRO1','Cardio',%s)",
                   (user['u_id'], verified))
        return {'id': user['u_id'], 'email': 'dr@x.com', 'role': 'medecin'}

    def test_can_access_rules(self):
        created = auth.register_patient('Diallo', 'Awa', 'awa@example.com', '+22997000001', 'motdepasse1')
        pid, puid = created['patient_id'], created['user_id']
        other = auth.register_patient('Autre', 'Bob', 'bob@example.com', '+22997000002', 'motdepasse1')
        patient = {'id': puid, 'email': '', 'role': 'patient'}
        stranger = {'id': other['user_id'], 'email': '', 'role': 'patient'}
        doctor = self._make_doctor()

        self.assertTrue(can_access(patient, pid, 'record.read'))
        self.assertFalse(can_access(patient, pid, 'record.write'))     # le patient n'écrit pas le médical
        self.assertFalse(can_access(stranger, pid, 'record.read'))     # famille/inconnu : rien
        self.assertFalse(can_access(doctor, pid, 'record.read'))       # pas d'autorisation
        self.assertFalse(can_access({'id': 1, 'email': '', 'role': 'admin'}, pid, 'record.read'))
        self.assertFalse(can_access(doctor, pid, 'nimporte.quoi'))

        db.execute("INSERT INTO medical_access (ma_patient_id,ma_granted_to_user_id,ma_granted_by_user_id,ma_scopes) VALUES (%s,%s,%s,%s)",
                   (pid, doctor['id'], puid, ['record.read']))
        self.assertTrue(can_access(doctor, pid, 'record.read'))
        self.assertFalse(can_access(doctor, pid, 'record.write'))      # portée limitée
        db.execute("UPDATE doctors SET d_verification_status=false")
        self.assertFalse(can_access(doctor, pid, 'record.read'))       # médecin non vérifié
        db.execute("UPDATE doctors SET d_verification_status=true")
        db.execute("UPDATE medical_access SET ma_status='revoked'")
        self.assertFalse(can_access(doctor, pid, 'record.read'))       # révocation immédiate

        # personne de confiance : lecture seule, même avec la portée d'écriture accordée
        db.execute("INSERT INTO medical_access (ma_patient_id,ma_granted_to_user_id,ma_granted_by_user_id,ma_kind,ma_scopes) VALUES (%s,%s,%s,'trusted_person',%s)",
                   (pid, stranger['id'], puid, ['record.read', 'record.write']))
        self.assertTrue(can_access(stranger, pid, 'record.read'))
        self.assertFalse(can_access(stranger, pid, 'record.write'))

    def test_database_guarantees(self):
        created = auth.register_patient('D', 'A', 'awa@example.com', '+22997000001', 'motdepasse1')
        doctor = self._make_doctor()
        d = db.fetch_one('SELECT d_id FROM doctors')['d_id']
        db.execute("INSERT INTO health_facilities (hf_name,hf_type,hf_phone,hf_address,hf_city,hf_country) VALUES ('C','clinique','1','a','c','BJ')")
        insert = """INSERT INTO appointments (a_patient_id,a_doctor_id,a_facility_id,a_date,a_start_time,a_end_time,a_reason)
                    VALUES (%s,%s,1,'2030-01-07',%s,%s,'test')"""
        db.execute(insert, (created['patient_id'], d, '09:00', '09:30'))
        db.execute(insert, (created['patient_id'], d, '09:30', '10:00'))          # contigu : autorisé
        with self.assertRaises(psycopg.errors.ExclusionViolation):                # chevauchement : refusé
            db.execute(insert, (created['patient_id'], d, '09:15', '09:45'))
        db.execute("UPDATE appointments SET a_status='cancelled' WHERE a_start_time='09:00'")
        db.execute(insert, (created['patient_id'], d, '09:00', '09:20'))          # créneau libéré

        before = db.fetch_one('SELECT p_updated_at t FROM patients')['t']
        db.execute("UPDATE patients SET p_city='Cotonou'")
        self.assertGreater(db.fetch_one('SELECT p_updated_at t FROM patients')['t'], before)

        security.log_access(type('R', (), {'ip': '10.0.0.1', 'user_agent': 'ua'})(), None, None, 't', 'r')
        with self.assertRaises(Exception):
            db.execute('DELETE FROM access_logs')                                 # journal en ajout seul
        with self.assertRaises(Exception):
            db.execute("UPDATE access_logs SET alog_result='x'")


if __name__ == '__main__':
    unittest.main()
