"""Scénario complet : professionnels, vérification, rendez-vous, accès au dossier, famille, admin."""
import base64
import unittest
from datetime import timedelta

try:                                   # python -m unittest tests.test_flows
    from tests.test_core import call, reset_state, session_cookie
except ImportError:                    # python -m unittest discover -s tests
    from test_core import call, reset_state, session_cookie

import config                          # noqa: E402  (après test_core : variables d'environnement)
from app import auth, db               # noqa: E402

PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 64).decode()
PW = 'motdepasse1'


def login(email, role=None):
    status, headers, data, _ = call('POST', '/login', {'email': email, 'password': PW})
    assert status == 200, data
    return session_cookie(headers)


def post(path, body, cookie, ct=True):
    return call('POST', path, body, cookie=cookie)


def get(path, cookie):
    return call('GET', path, cookie=cookie)


class FullFlow(unittest.TestCase):
    def setUp(self):
        reset_state()
        db.execute('TRUNCATE platform_settings')
        db.execute("INSERT INTO platform_settings VALUES ('registration_open', '1')")

    def ok(self, response, expected=200):
        self.assertEqual(response[0], expected, response[2])
        return response[2]

    def test_everything(self):
        # ── comptes
        role = db.fetch_one("SELECT r_id FROM roles WHERE r_type = 'admin'")['r_id']
        db.execute("INSERT INTO users (u_email, u_phone, u_password, u_role_id) VALUES ('admin@x.com', '+22900000', %s, %s)",
                   (auth.hash_password(PW), role))
        admin = login('admin@x.com')
        # ── les comptes pro ne sont créés que par un administrateur, et sont déjà vérifiés
        self.ok(post('/api/admin/doctors', {'last_name': 'Kone', 'first_name': 'Ali', 'email': 'dr@x.com',
                'phone': '+22991000001', 'password': PW, 'professional_id': 'MED-1',
                'specialty': 'Cardiologie'}, admin), 201)
        self.ok(post('/api/admin/facilities', {'name': 'Clinique Soleil', 'facility_type': 'clinique',
                'email': 'clinique@x.com', 'phone': '+22991000002', 'password': PW, 'address': '1 rue A',
                'city': 'Cotonou', 'country': 'Bénin'}, admin), 201)
        self.assertEqual(post('/api/admin/doctors', {'last_name': 'K', 'first_name': 'A', 'email': 'dr2@x.com',
                'phone': '+22991000009', 'password': PW, 'professional_id': 'MED-1', 'specialty': 'X'},
                admin)[0], 409)   # identifiant pro déjà pris
        self.assertEqual(post('/api/admin/doctors', {'last_name': 'K'}, admin)[0], 400)
        for n, email in ((1, 'a@x.com'), (2, 'b@x.com')):
            self.ok(call('POST', '/register', {'last_name': 'Pat', 'first_name': f'P{n}', 'email': email,
                    'phone': f'+2299200000{n}', 'password': PW, 'password_confirmation': PW, 'terms': True}), 201)
        doctor, facility = login('dr@x.com'), login('clinique@x.com')
        pa, pb = login('a@x.com'), login('b@x.com')

        # ── comptes pro créés par l'admin : déjà vérifiés, visibles dès la création
        self.assertEqual(self.ok(get('/api/admin/dashboard', admin))['data']['stats']['doctors_pending'], 0)
        self.assertEqual(get('/api/admin/dashboard', pa)[0], 403)
        self.assertGreater(len(self.ok(get('/api/notifications', doctor))['data']), 0)

        # ── invitation → acceptation → disponibilités
        self.ok(post('/api/facility/doctors/invite', {'professional_id': 'MED-1', 'position': 'Chef'}, facility), 201)
        self.assertEqual(post('/api/facility/doctors/invite', {'professional_id': 'MED-1'}, facility)[0], 409)
        self.assertEqual(self.ok(get('/api/doctors', pa))['data'], [])            # invitation non acceptée
        dfid = self.ok(get('/api/doctor/dashboard', doctor))['data']['facilities'][0]['df_id']
        self.ok(post(f'/api/doctor/invitations/{dfid}/respond', {'accept': True}, doctor))
        day = config.now_local().date() + timedelta(days=3)
        self.ok(post('/api/doctor/availabilities', {'facility_id': 1, 'day_of_week': day.isoweekday(),
                'start_time': '09:00', 'end_time': '11:00', 'slot_minutes': 30}, doctor), 201)
        self.assertEqual(post('/api/doctor/availabilities', {'facility_id': 1, 'day_of_week': day.isoweekday(),
                         'start_time': '10:00', 'end_time': '12:00'}, doctor)[0], 409)   # chevauchement

        # ── recherche & créneaux
        found = self.ok(get('/api/doctors?q=cardio', pa))['data']
        self.assertEqual(found[0]['facilities'][0]['name'], 'Clinique Soleil')
        self.assertEqual(self.ok(get('/api/doctors?q=%25', pa))['data'], [])           # % échappé
        self.assertEqual(len(self.ok(get('/api/facilities?city=coto', pa))['data']), 1)
        slots_url = f'/api/doctors/1/slots?facility_id=1&date={day.isoformat()}'
        self.assertEqual(len(self.ok(get(slots_url, pa))['data']), 4)
        booking = {'doctor_id': 1, 'facility_id': 1, 'date': day.isoformat(), 'start_time': '09:00',
                   'reason': 'Douleurs thoraciques'}
        aid = self.ok(post('/api/patient/appointments', booking, pa), 201)['data']['id']
        self.assertEqual(len(self.ok(get(slots_url, pa))['data']), 3)
        self.assertEqual(post('/api/patient/appointments', booking, pb)[0], 409)        # créneau pris
        self.assertEqual(post('/api/patient/appointments', dict(booking, start_time='09:10'), pb)[0], 409)  # hors grille
        self.assertEqual(post('/api/patient/appointments', dict(booking, date='2020-01-01'), pb)[0], 409)  # passé

        # ── le médecin traite la demande
        self.ok(post(f'/api/doctor/appointments/{aid}/confirm', {}, doctor))
        self.assertEqual(post(f'/api/doctor/appointments/{aid}/confirm', {}, doctor)[0], 409)
        self.assertEqual(post(f'/api/doctor/appointments/{aid}/complete', {}, doctor)[0], 409)   # futur

        # ── SANS autorisation : accès refusé et tracé
        self.assertEqual(get('/api/doctor/patients/1/record', doctor)[0], 403)
        dash = self.ok(get('/api/patient/dashboard', pa))['data']
        denied = [l for l in dash['access_logs'] if l['result'] == 'denied']
        self.assertEqual(denied[0]['actor_name'], 'Ali Kone')
        self.assertFalse({'ip', 'alog_ip_address', 'alog_user_agent'} & set(denied[0]))

        # ── autorisation → écriture médicale
        self.assertEqual(post('/api/patient/access', {'kind': 'doctor', 'professional_id': 'MED-1', 'scopes': ['bidon']}, pa)[0], 400)
        self.ok(post('/api/patient/access', {'kind': 'doctor', 'professional_id': 'MED-1', 'days': 30,
                'scopes': ['record.read', 'record.write', 'documents.read', 'documents.write']}, pa), 201)
        rec = self.ok(get('/api/doctor/patients/1/record', doctor))['data']
        self.assertTrue(rec['can_write'])
        cid = self.ok(post('/api/doctor/patients/1/consultations', {'appointment_id': aid}, doctor), 201)['data']['id']
        self.assertEqual(post('/api/doctor/patients/1/consultations', {'appointment_id': aid}, doctor)[0], 409)
        base = '/api/doctor/patients/1/records/'
        self.ok(post(base + 'blood_group', {'value': 'O+'}, doctor), 201)
        self.assertEqual(post(base + 'blood_group', {'value': 'Z'}, doctor)[0], 400)
        self.ok(post(base + 'allergy', {'name': 'Pénicilline', 'severity': 'severe'}, doctor), 201)
        self.ok(post(base + 'diagnosis', {'consultation_id': cid, 'name': 'Angine'}, doctor), 201)
        self.ok(post(base + 'prescription', {'consultation_id': cid, 'items': [
            {'medicine_name': 'Amoxicilline', 'dosage': '500 mg', 'frequency': '3/j', 'duration': '7 j'}]}, doctor), 201)
        self.assertEqual(post(base + 'prescription', {'items': []}, doctor)[0], 400)
        exam_id = self.ok(post(base + 'exam', {'name': 'Bilan sanguin'}, doctor), 201)['data']['id']
        self.ok(post(base + 'exam_result', {'exam_id': exam_id, 'result': 'Normal'}, doctor), 201)
        doc_id = self.ok(post('/api/doctor/patients/1/documents', {'type': 'rapport_medical', 'title': 'Rapport',
                'file_name': 'rapport.png', 'content_base64': PNG}, doctor), 201)['data']['id']
        self.assertEqual(post('/api/doctor/patients/1/documents', {'type': 'autre', 'title': 'x',
                         'content_base64': base64.b64encode(b'MZ-exe').decode()}, doctor)[0], 415)  # signature invalide

        # ── le patient ne voit pas une consultation non clôturée
        dash = self.ok(get('/api/patient/dashboard', pa))['data']
        self.assertEqual((len(dash['consultations']), len(dash['diagnoses']), len(dash['prescriptions'])), (0, 0, 0))
        self.assertEqual(len(dash['allergies']), 1)
        self.assertEqual(post(f'/api/doctor/consultations/{cid}', {'close': True}, doctor)[0], 400)   # conclusion requise
        self.ok(post(f'/api/doctor/consultations/{cid}', {'observations': 'RAS', 'conclusion': 'Angine', 'close': True}, doctor))
        self.assertEqual(post(f'/api/doctor/consultations/{cid}', {'conclusion': 'x'}, doctor)[0], 409)   # clôturée
        dash = self.ok(get('/api/patient/dashboard', pa))['data']
        self.assertEqual((len(dash['consultations']), len(dash['diagnoses']), len(dash['prescriptions'])), (1, 1, 1))
        self.assertEqual(dash['prescriptions'][0]['items'][0]['pri_medicine_name'], 'Amoxicilline')
        self.assertEqual(dash['record']['blood_group'], 'O+')
        self.assertEqual(dash['appointments'][0]['status'], 'completed')
        self.assertEqual(len(dash['exams']), 1)
        status, _, _, raw = get(f'/api/documents/{doc_id}/download', pa)
        self.assertEqual((status, raw[:4]), (200, b'\x89PNG'))
        self.assertEqual(get(f'/api/documents/{doc_id}/download', pb)[0], 403)           # autre patient
        self.assertEqual(get(f'/api/documents/{doc_id}/download', admin)[0], 403)        # admin : jamais
        self.assertEqual(post('/api/doctor/patients/1/records/allergy', {'name': 'x'}, pa)[0], 403)  # patient n'écrit pas

        # ── révocation immédiate
        mid = dash['access'][0]['ma_id']
        self.ok(post(f'/api/patient/access/{mid}/revoke', {}, pa))
        self.assertEqual(get('/api/doctor/patients/1/record', doctor)[0], 403)
        self.assertEqual(get(f'/api/documents/{doc_id}/download', doctor)[0], 403)
        self.assertEqual(post(base + 'allergy', {'name': 'x'}, doctor)[0], 403)

        # ── famille : aucune fuite de coordonnées, aucun accès médical implicite
        self.ok(post('/api/patient/family', {'identifier': 'b@x.com', 'relationship': 'Frère'}, pa), 201)
        self.assertEqual(post('/api/patient/family', {'identifier': 'b@x.com', 'relationship': 'Frère'}, pa)[0], 409)
        self.assertEqual(post('/api/patient/family', {'identifier': 'a@x.com', 'relationship': 'Moi'}, pa)[0], 400)
        fid = self.ok(get('/api/patient/dashboard', pb))['data']['family'][0]['fr_id']
        self.assertEqual(post(f'/api/patient/family/{fid}/respond', {'accept': True}, pa)[0], 404)  # pas le destinataire
        self.ok(post(f'/api/patient/family/{fid}/respond', {'accept': True}, pb))
        fam = self.ok(get('/api/patient/dashboard', pa))['data']['family'][0]
        self.assertEqual(fam['status'], 'accepted')
        self.assertFalse({'u_email', 'u_phone', 'phone', 'email'} & set(fam))
        self.assertEqual(get('/api/patient/shared/1/record', pb)[0], 403)                # lien familial ≠ accès
        self.assertEqual(post('/api/patient/access', {'kind': 'trusted_person', 'identifier': 'b@x.com',
                         'scopes': ['record.write']}, pa)[0], 400)
        self.ok(post('/api/patient/access', {'kind': 'trusted_person', 'identifier': 'b@x.com',
                'scopes': ['record.read']}, pa), 201)
        shared = self.ok(get('/api/patient/shared/1/record', pb))['data']
        self.assertEqual(shared['record']['blood_group'], 'O+')

        # ── annulation
        day2 = day + timedelta(days=7)
        self.ok(post('/api/patient/appointments', dict(booking, date=day2.isoformat(), start_time='10:00'), pa), 201)
        aid2 = db.fetch_one('SELECT max(a_id) m FROM appointments')['m']
        self.ok(post(f'/api/patient/appointments/{aid2}/cancel', {}, pa))
        self.assertEqual(post(f'/api/patient/appointments/{aid2}/cancel', {}, pa)[0], 409)
        self.assertEqual(post(f'/api/patient/appointments/{aid2}/cancel', {}, pb)[0], 409)  # pas le sien
        self.assertEqual(len(self.ok(get(f'/api/doctors/1/slots?facility_id=1&date={day2.isoformat()}', pa))['data']), 4)

        # ── compte : mot de passe, photo, notifications, signalement
        other_session = login('a@x.com', 'patient')
        self.assertEqual(post('/api/account/password', {'current_password': 'faux', 'new_password': 'nouveaumdp1',
                         'new_password_confirmation': 'nouveaumdp1'}, pa)[0], 403)
        self.ok(post('/api/account/password', {'current_password': PW, 'new_password': 'nouveaumdp1',
                'new_password_confirmation': 'nouveaumdp1'}, pa))
        self.assertEqual(get('/api/me', other_session)[0], 401)
        self.assertEqual(get('/api/me', pa)[0], 200)
        url = self.ok(post('/api/account/photo', {'content_base64': PNG}, pb))['data']['url']
        self.assertEqual(get(url, pb)[0], 200)
        self.ok(post('/api/notifications/read', {'all': True}, doctor))
        self.assertTrue(all(n['n_is_read'] for n in self.ok(get('/api/notifications', doctor))['data']))
        self.ok(post('/api/reports', {'reported_user_id': 2, 'subject': 'Abus', 'description': 'Détails'}, pa), 201)
        self.assertEqual(len(self.ok(get('/api/admin/dashboard', admin))['data']['reports']), 1)

        # ── admin : suspension = déconnexion immédiate ; journal sans contenu médical
        doctor_uid = db.fetch_one("SELECT d_user_id u FROM doctors")['u']
        self.assertEqual(get('/api/doctor/dashboard', doctor)[0], 200)
        self.ok(post(f'/api/admin/users/{doctor_uid}/status', {'active': False}, admin))
        self.assertEqual(get('/api/doctor/dashboard', doctor)[0], 401)
        self.assertEqual(call('POST', '/login', {'email': 'dr@x.com', 'password': PW, 'role': 'medecin'})[0], 401)
        me = db.fetch_one("SELECT u_id FROM users WHERE u_email = 'admin@x.com'")['u_id']
        self.assertEqual(post(f'/api/admin/users/{me}/status', {'active': False}, admin)[0], 400)   # pas soi-même
        actions = {l['action'] for l in self.ok(get('/api/admin/logs', admin))['data']}
        self.assertTrue({'admin.user.deactivate', 'record.read', 'login'} <= actions)
        self.ok(post('/api/admin/settings', {'key': 'registration_open', 'value': '0'}, admin))
        self.assertEqual(call('POST', '/register', {'x': 1})[0], 403)                    # inscriptions fermées
        self.assertEqual(post('/api/admin/settings', {'key': 'Bad Key', 'value': 'x'}, admin)[0], 400)


if __name__ == '__main__':
    unittest.main()
