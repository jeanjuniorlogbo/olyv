"""Espace administrateur : comptes, vérifications, signalements, journaux, paramètres.
Aucune route ici ne lit de contenu médical, et il n'existe aucun moyen d'en obtenir
(can_access() refuse toujours le rôle admin)."""
import re

from app import auth, db, validation
from app.common import choice, int_id, like, notifications_for, notify, ok
from app.errors import HttpError
from app.security import log_access
from app.web import route

ROLES = ('patient', 'medecin', 'etablissement', 'admin')
REPORT_STATUSES = ('pending', 'reviewing', 'resolved', 'dismissed')
FACILITY_TYPES = ('hopital', 'clinique', 'cabinet', 'centre_de_sante')
_SETTING_KEY = re.compile(r'^[a-z_]{2,60}$')
PAGE = 50


@route('POST', '/api/admin/doctors', roles=('admin',))
def create_doctor(request):
    """Seul un administrateur peut créer un compte médecin. Compte déjà vérifié."""
    data = request.json()
    email = validation.email(data.get('email'))
    phone = validation.phone(data.get('phone'))
    password = validation.password(data['password']) if data.get('password') else None
    result = auth.admin_create_doctor(
        validation.text(data.get('last_name'), 'Le nom'),
        validation.text(data.get('first_name'), 'Le prénom'),
        email, phone,
        validation.text(data.get('professional_id'), 'L’identifiant professionnel'),
        validation.text(data.get('specialty'), 'La spécialité', 255),
        password)
    log_access(request, request.user['id'], None, 'admin.doctor.create', 'user', result['user_id'])
    return ok(result, 'Compte médecin créé.', 201)


@route('POST', '/api/admin/facilities', roles=('admin',))
def create_facility(request):
    """Seul un administrateur peut créer un compte établissement. Compte déjà vérifié."""
    data = request.json()
    email = validation.email(data.get('email'))
    phone = validation.phone(data.get('phone'))
    ftype = choice(data.get('facility_type'), FACILITY_TYPES, 'Le type d’établissement')
    password = validation.password(data['password']) if data.get('password') else None
    result = auth.admin_create_facility(
        validation.text(data.get('name'), 'Le nom de l’établissement', 255), ftype,
        email, phone,
        validation.text(data.get('address'), 'L’adresse', 500),
        validation.text(data.get('city'), 'La ville'),
        validation.text(data.get('country'), 'Le pays'),
        password)
    log_access(request, request.user['id'], None, 'admin.facility.create', 'user', result['user_id'])
    return ok(result, 'Compte établissement créé.', 201)


@route('POST', '/api/admin/users/{uid}/reset-password', roles=('admin',))
def reset_password(request):
    """Réinitialise le mot de passe d’un utilisateur ; le déconnecte immédiatement."""
    target = int_id(request.params['uid'], 'L’utilisateur')
    if target == request.user['id']:
        raise HttpError(400, 'Utilisez le changement de mot de passe de votre propre compte.')
    data = request.json()
    password = validation.password(data['password']) if data.get('password') else None
    new_password = auth.admin_reset_password(target, password)
    log_access(request, request.user['id'], None, 'admin.user.reset_password', 'user', target)
    return ok({'password': new_password}, 'Mot de passe réinitialisé.')


@route('GET', '/api/admin/dashboard', roles=('admin',))
def dashboard(request):
    stats = db.fetch_one(
        """SELECT
             (SELECT count(*) FROM users WHERE u_is_active) AS active_users,
             (SELECT count(*) FROM users WHERE NOT u_is_active) AS inactive_users,
             (SELECT count(*) FROM patients) AS patients,
             (SELECT count(*) FROM doctors WHERE d_verification_status) AS doctors,
             (SELECT count(*) FROM health_facilities WHERE hf_verification_status) AS facilities,
             (SELECT count(*) FROM doctors WHERE NOT d_verification_status) AS doctors_pending,
             (SELECT count(*) FROM health_facilities WHERE NOT hf_verification_status) AS facilities_pending,
             (SELECT count(*) FROM reports WHERE rp_status IN ('pending', 'reviewing')) AS reports_open,
             (SELECT count(*) FROM appointments WHERE a_date >= current_date
                     AND a_status IN ('pending', 'confirmed')) AS appointments_upcoming""")
    doctors = db.fetch_all(
        """SELECT d.d_id, d.d_first_name, d.d_last_name, d.d_professional_id, d.d_specialty,
                  d.d_verification_status, d.d_is_active, u.u_email, d.d_created_at
           FROM doctors d JOIN users u ON u.u_id = d.d_user_id
           ORDER BY d.d_verification_status, d.d_created_at DESC LIMIT 100""")
    facilities = db.fetch_all(
        """SELECT hf.hf_id, hf.hf_name, hf.hf_type::text AS hf_type, hf.hf_city, hf.hf_phone,
                  hf.hf_verification_status, hf.hf_status, hf.hf_created_at
           FROM health_facilities hf
           ORDER BY hf.hf_verification_status, hf.hf_created_at DESC LIMIT 100""")
    reports = db.fetch_all(
        """SELECT r.rp_id, r.rp_subject, r.rp_description, r.rp_status::text AS status, r.rp_created_at,
                  r.rp_reported_user_id, u1.u_email AS reporter_email, u2.u_email AS reported_email
           FROM reports r JOIN users u1 ON u1.u_id = r.rp_reporter_user_id
           LEFT JOIN users u2 ON u2.u_id = r.rp_reported_user_id
           ORDER BY (r.rp_status IN ('pending', 'reviewing')) DESC, r.rp_created_at DESC LIMIT 100""")
    settings = db.fetch_all('SELECT ps_key, ps_value FROM platform_settings ORDER BY ps_key')
    return ok({'stats': stats, 'doctors': doctors, 'facilities': facilities, 'reports': reports,
               'settings': settings, 'notifications': notifications_for(request.user['id'])})


@route('GET', '/api/admin/users', roles=('admin',))
def list_users(request):
    role = request.query.get('role')
    if role:
        choice(role, ROLES, 'Le rôle')
    try:
        page = max(1, int(request.query.get('page', '1')))
    except ValueError:
        page = 1
    rows = db.fetch_all(
        """SELECT u.u_id, u.u_email, u.u_phone, r.r_type::text AS role, u.u_is_active,
                  u.u_created_at, u.u_last_login_at
           FROM users u JOIN roles r ON r.r_id = u.u_role_id
           WHERE (%(q)s::text IS NULL OR u.u_email ILIKE %(q)s::text OR u.u_phone ILIKE %(q)s::text)
             AND (%(role)s::text IS NULL OR r.r_type::text = %(role)s::text)
           ORDER BY u.u_created_at DESC LIMIT %(limit)s OFFSET %(offset)s""",
        {'q': like(request.query.get('q')), 'role': role or None, 'limit': PAGE + 1,
         'offset': (page - 1) * PAGE})
    return ok({'users': rows[:PAGE], 'has_more': len(rows) > PAGE, 'page': page})


@route('POST', '/api/admin/users/{uid}/status', roles=('admin',))
def set_user_status(request):
    target = request.params['uid']
    active = request.json().get('active')
    if not isinstance(active, bool):
        raise HttpError(400, 'Statut invalide.')
    if target == request.user['id']:
        raise HttpError(400, 'Vous ne pouvez pas modifier votre propre compte.')
    with db.transaction() as cur:
        cur.execute('UPDATE users SET u_is_active = %s WHERE u_id = %s', (active, target))
        if cur.rowcount == 0:
            raise HttpError(404, 'Utilisateur introuvable.')
        if not active:
            cur.execute('DELETE FROM sessions WHERE s_user_id = %s', (target,))
    log_access(request, request.user['id'], None,
               'admin.user.activate' if active else 'admin.user.deactivate', 'user', target)
    return ok(message='Compte activé.' if active else 'Compte désactivé et déconnecté.')


def _verify(request, table, id_col, flag_col, user_col, entity_id, label):
    verified = request.json().get('verified')
    if not isinstance(verified, bool):
        raise HttpError(400, 'Valeur invalide.')
    row = db.fetch_one(f'UPDATE {table} SET {flag_col} = %s WHERE {id_col} = %s RETURNING {user_col} AS uid',
                       (verified, entity_id))
    if row is None:
        raise HttpError(404, f'{label} introuvable.')
    if row['uid']:
        notify(row['uid'], 'system', 'Vérification de votre compte',
               f'Votre {label.lower()} a été {"validé" if verified else "suspendu"} par un administrateur.')
    log_access(request, request.user['id'], None,
               f'admin.{table}.{"verify" if verified else "unverify"}', table, entity_id)
    return ok(message='Vérification enregistrée.')


@route('POST', '/api/admin/doctors/{did}/verify', roles=('admin',))
def verify_doctor(request):
    return _verify(request, 'doctors', 'd_id', 'd_verification_status', 'd_user_id',
                   request.params['did'], 'Médecin')


@route('POST', '/api/admin/facilities/{fid}/verify', roles=('admin',))
def verify_facility(request):
    return _verify(request, 'health_facilities', 'hf_id', 'hf_verification_status', 'hf_user_id',
                   request.params['fid'], 'Établissement')


@route('POST', '/api/admin/reports/{rid}/status', roles=('admin',))
def set_report_status(request):
    status = choice(request.json().get('status'), REPORT_STATUSES, 'Le statut')
    if not db.execute('UPDATE reports SET rp_status = %s WHERE rp_id = %s', (status, request.params['rid'])):
        raise HttpError(404, 'Signalement introuvable.')
    log_access(request, request.user['id'], None, 'admin.report.status', 'report', request.params['rid'])
    return ok(message='Signalement mis à jour.')


@route('GET', '/api/admin/logs', roles=('admin',))
def technical_logs(request):
    """Journal technique : qui/quoi/quand/résultat, sans contenu médical."""
    rows = db.fetch_all(
        """SELECT l.alog_id, l.alog_created_at AS created_at, l.alog_action AS action,
                  l.alog_resource AS resource, l.alog_result AS result, l.alog_patient_id AS patient_id,
                  u.u_email AS actor_email, host(l.alog_ip_address) AS ip
           FROM access_logs l LEFT JOIN users u ON u.u_id = l.alog_user_id
           ORDER BY l.alog_created_at DESC LIMIT 200""")
    return ok(rows)


@route('POST', '/api/admin/settings', roles=('admin',))
def save_setting(request):
    data = request.json()
    key, value = data.get('key'), data.get('value')
    if not isinstance(key, str) or not _SETTING_KEY.match(key):
        raise HttpError(400, 'Clé invalide.')
    if not isinstance(value, str) or len(value) > 1000:
        raise HttpError(400, 'Valeur invalide.')
    if key == 'registration_open' and value not in ('0', '1'):
        raise HttpError(400, 'registration_open doit valoir 0 ou 1.')
    db.execute("""INSERT INTO platform_settings (ps_key, ps_value) VALUES (%s, %s)
                  ON CONFLICT (ps_key) DO UPDATE SET ps_value = EXCLUDED.ps_value, ps_updated_at = now()""",
               (key, value.strip()))
    log_access(request, request.user['id'], None, 'admin.setting', 'settings', None)
    return ok(message='Paramètre enregistré.')
