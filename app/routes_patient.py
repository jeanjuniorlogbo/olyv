"""Espace patient."""
import psycopg

from app import db, records, scheduling, validation
from app.common import (choice, current_patient, like, notifications_for, notify, ok, parse_date,
                        parse_time, int_id)
from app.errors import HttpError
from app.security import SCOPES, can_access, log_access, require_access
from app.web import route
import config

GENDERS = ('male', 'female', 'other', 'prefer_not_to_say')
READ_ONLY_SCOPES = ('record.read', 'documents.read')
MAX_PENDING = 5


def _expire_grants():
    db.execute("UPDATE medical_access SET ma_status = 'expired' "
               "WHERE ma_status = 'active' AND ma_end_at IS NOT NULL AND ma_end_at <= now()")


def _find_patient(identifier):
    """Patient par identifiant numérique, e-mail ou téléphone."""
    if identifier.isdigit() and len(identifier) <= 9:
        where, param = 'u.u_id = %s', int(identifier)
    elif '@' in identifier:
        where, param = 'lower(u.u_email) = %s', identifier.lower()
    else:
        where, param = 'u.u_phone = %s', validation.phone(identifier)
    return db.fetch_one(
        f"""SELECT u.u_id, p.p_id, p.p_first_name, p.p_last_name
            FROM users u JOIN patients p ON p.p_user_id = u.u_id
            WHERE u.u_is_active AND {where}""", (param,))


@route('GET', '/api/patient/dashboard', roles=('patient',))
def dashboard(request):
    _expire_grants()
    uid = request.user['id']
    patient = db.fetch_one(
        """SELECT p.p_id, p.p_first_name, p.p_last_name, p.p_date_of_birth,
                  p.p_gender::text AS p_gender, p.p_address, p.p_city, p.p_country,
                  p.p_profile_photo_url, u.u_email, u.u_phone
           FROM patients p JOIN users u ON u.u_id = p.p_user_id WHERE p.p_user_id = %s""", (uid,))
    if patient is None:
        raise HttpError(404, 'Dossier patient introuvable.')
    pid = patient['p_id']

    appointments = db.fetch_all(
        """SELECT a.a_id, a.a_date, a.a_start_time, a.a_end_time, a.a_reason,
                  a.a_status::text AS status, a.a_patient_note,
                  a.a_doctor_id AS doctor_id, a.a_facility_id AS facility_id,
                  d.d_first_name, d.d_last_name, d.d_specialty,
                  hf.hf_name, hf.hf_address, hf.hf_city, hf.hf_phone
           FROM appointments a
           JOIN doctors d ON d.d_id = a.a_doctor_id
           JOIN health_facilities hf ON hf.hf_id = a.a_facility_id
           WHERE a.a_patient_id = %s ORDER BY a.a_date DESC, a.a_start_time DESC LIMIT 200""",
        (pid,))

    family = db.fetch_all(
        """SELECT fr.fr_id, fr.fr_relationship, fr.fr_status::text AS status,
                  fr.fr_created_at, 'sent' AS direction, p2.p_first_name, p2.p_last_name
           FROM family_relationships fr JOIN patients p2 ON p2.p_user_id = fr.fr_related_user_id
           WHERE fr.fr_patient_id = %s AND fr.fr_status IN ('pending', 'accepted')
           UNION ALL
           SELECT fr.fr_id, fr.fr_relationship, fr.fr_status::text, fr.fr_created_at,
                  'received', p1.p_first_name, p1.p_last_name
           FROM family_relationships fr JOIN patients p1 ON p1.p_id = fr.fr_patient_id
           WHERE fr.fr_related_user_id = %s AND fr.fr_status IN ('pending', 'accepted')
           ORDER BY fr_created_at DESC""", (pid, uid))

    access = db.fetch_all(
        """SELECT ma.ma_id, ma.ma_kind::text AS kind, ma.ma_status::text AS status,
                  ma.ma_scopes AS scopes, ma.ma_start_at, ma.ma_end_at,
                  COALESCE(d.d_first_name || ' ' || d.d_last_name,
                           p.p_first_name || ' ' || p.p_last_name) AS name, d.d_specialty
           FROM medical_access ma
           LEFT JOIN doctors d ON d.d_user_id = ma.ma_granted_to_user_id
           LEFT JOIN patients p ON p.p_user_id = ma.ma_granted_to_user_id
           WHERE ma.ma_patient_id = %s
           ORDER BY (ma.ma_status = 'active') DESC, ma.ma_created_at DESC LIMIT 100""", (pid,))

    # Journal : qui, quoi, quand, résultat. Jamais d'IP ni de user-agent.
    access_logs = db.fetch_all(
        """SELECT l.alog_id, l.alog_action AS action, l.alog_resource AS resource,
                  l.alog_result AS result, l.alog_created_at AS created_at,
                  r.r_type::text AS actor_role,
                  COALESCE(d.d_first_name || ' ' || d.d_last_name,
                           pp.p_first_name || ' ' || pp.p_last_name) AS actor_name
           FROM access_logs l
           LEFT JOIN users u ON u.u_id = l.alog_user_id
           LEFT JOIN roles r ON r.r_id = u.u_role_id
           LEFT JOIN doctors d ON d.d_user_id = u.u_id
           LEFT JOIN patients pp ON pp.p_user_id = u.u_id
           WHERE l.alog_patient_id = %s AND l.alog_action NOT LIKE 'account.%%'
                 AND l.alog_user_id IS DISTINCT FROM %s
           ORDER BY l.alog_created_at DESC LIMIT 100""", (pid, uid))

    shared = db.fetch_all(
        """SELECT ma.ma_patient_id AS patient_id, p.p_first_name, p.p_last_name,
                  ma.ma_scopes AS scopes, ma.ma_end_at
           FROM medical_access ma JOIN patients p ON p.p_id = ma.ma_patient_id
           WHERE ma.ma_granted_to_user_id = %s AND ma.ma_status = 'active'
                 AND ma.ma_kind = 'trusted_person' AND ma.ma_start_at <= now()
                 AND (ma.ma_end_at IS NULL OR ma.ma_end_at > now())""", (uid,))

    data = {'patient': patient, 'appointments': appointments, 'family': family, 'access': access,
            'access_logs': access_logs, 'shared': shared,
            'notifications': notifications_for(uid)}
    data.update(records.load_record(pid, validated_only=True))
    return ok(data)


@route('GET', '/api/patient/shared/{pid}/record', roles=('patient',))
def shared_record(request):
    pid = request.params['pid']
    require_access(request, pid, 'record.read', 'record')
    docs = can_access(request.user, pid, 'documents.read')
    return ok(records.load_record(pid, validated_only=True, documents=docs))


@route('POST', '/api/patient/profile', roles=('patient',))
def update_profile(request):
    data = request.json()
    dob = parse_date(data.get('date_of_birth'), 'La date de naissance', required=False)
    if dob and dob > config.now_local().date():
        raise HttpError(400, 'La date de naissance est invalide.')
    try:
        db.execute(
            """UPDATE patients SET p_first_name = %s, p_last_name = %s, p_date_of_birth = %s,
                   p_gender = %s, p_address = %s, p_city = %s, p_country = %s WHERE p_user_id = %s""",
            (validation.text(data.get('first_name'), 'Le prénom'),
             validation.text(data.get('last_name'), 'Le nom'), dob,
             choice(data.get('gender'), GENDERS, 'Le genre'),
             validation.text(data.get('address'), 'L’adresse', 500, False),
             validation.text(data.get('city'), 'La ville', 100, False),
             validation.text(data.get('country'), 'Le pays', 100, False), request.user['id']))
        db.execute('UPDATE users SET u_phone = %s WHERE u_id = %s',
                   (validation.phone(data.get('phone')), request.user['id']))
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, 'Ce numéro de téléphone est déjà utilisé.')
    return ok(message='Profil mis à jour.')


@route('GET', '/api/doctors', roles=('patient',))
def search_doctors(request):
    q, city = like(request.query.get('q')), like(request.query.get('city'))
    rows = db.fetch_all(
        """SELECT d.d_id, d.d_first_name, d.d_last_name, d.d_specialty, d.d_qualifications, d.d_bio,
                  d.d_profile_photo_url,
                  json_agg(json_build_object('id', hf.hf_id, 'name', hf.hf_name,
                                             'city', hf.hf_city, 'address', hf.hf_address)
                           ORDER BY hf.hf_name) AS facilities
           FROM doctors d
           JOIN doctor_facilities df ON df.df_doctor_id = d.d_id AND df.df_status AND NOT df.df_pending
                AND df.df_start_date <= current_date
                AND (df.df_end_date IS NULL OR df.df_end_date >= current_date)
           JOIN health_facilities hf ON hf.hf_id = df.df_facility_id AND hf.hf_status
                AND hf.hf_verification_status
           WHERE d.d_verification_status AND d.d_is_active
             AND (%(q)s::text IS NULL OR (d.d_first_name || ' ' || d.d_last_name || ' ' || d.d_specialty)
                  ILIKE %(q)s::text)
             AND (%(city)s::text IS NULL OR hf.hf_city ILIKE %(city)s::text)
           GROUP BY d.d_id ORDER BY d.d_last_name, d.d_first_name LIMIT 50""",
        {'q': q, 'city': city})
    return ok(rows)


@route('GET', '/api/facilities', roles=('patient',))
def search_facilities(request):
    q, city = like(request.query.get('q')), like(request.query.get('city'))
    rows = db.fetch_all(
        """SELECT hf.hf_id, hf.hf_name, hf.hf_type::text AS type, hf.hf_phone, hf.hf_address,
                  hf.hf_city, hf.hf_description, hf.hf_services, hf.hf_specialties,
                  hf.hf_opening_hours, hf.hf_logo_url,
                  (SELECT count(*) FROM doctor_facilities df JOIN doctors d ON d.d_id = df.df_doctor_id
                   WHERE df.df_facility_id = hf.hf_id AND df.df_status AND NOT df.df_pending
                         AND d.d_verification_status AND d.d_is_active) AS doctors_count
           FROM health_facilities hf
           WHERE hf.hf_status AND hf.hf_verification_status
             AND (%(q)s::text IS NULL OR (hf.hf_name || ' ' || COALESCE(hf.hf_specialties, ''))
                  ILIKE %(q)s::text)
             AND (%(city)s::text IS NULL OR hf.hf_city ILIKE %(city)s::text)
           ORDER BY hf.hf_name LIMIT 50""", {'q': q, 'city': city})
    return ok(rows)


@route('GET', '/api/doctors/{doctor_id}/slots', roles=('patient',))
def doctor_slots(request):
    try:
        facility_id = int(request.query.get('facility_id', ''))
    except ValueError:
        raise HttpError(400, 'L’établissement est invalide.')
    day = parse_date(request.query.get('date'))
    slots = scheduling.free_slots(request.params['doctor_id'], facility_id, day)
    return ok([{'start': s.strftime('%H:%M'), 'end': e.strftime('%H:%M')} for s, e in slots])


@route('POST', '/api/patient/appointments', roles=('patient',))
def book_appointment(request):
    patient = current_patient(request)
    data = request.json()
    doctor_id = int_id(data.get('doctor_id'), 'Le médecin')
    facility_id = int_id(data.get('facility_id'), 'L’établissement')
    day = parse_date(data.get('date'))
    start = parse_time(data.get('start_time'), 'L’heure')
    reason = validation.text(data.get('reason'), 'Le motif', 1000)
    note = validation.text(data.get('patient_note'), 'La note', 2000, required=False)

    slot = next(((s, e) for s, e in scheduling.free_slots(doctor_id, facility_id, day)
                 if s == start), None)
    if slot is None:
        raise HttpError(409, 'Ce créneau n’est plus disponible.')
    pending = db.fetch_one("SELECT count(*) AS c FROM appointments WHERE a_patient_id = %s "
                           "AND a_status = 'pending'", (patient['p_id'],))['c']
    if pending >= MAX_PENDING:
        raise HttpError(429, f'Vous avez déjà {MAX_PENDING} demandes en attente.')
    clash = db.fetch_one(
        """SELECT 1 FROM appointments WHERE a_patient_id = %s AND a_date = %s
           AND a_status IN ('pending', 'confirmed') AND a_start_time < %s AND a_end_time > %s""",
        (patient['p_id'], day, slot[1], slot[0]))
    if clash:
        raise HttpError(409, 'Vous avez déjà un rendez-vous sur ce créneau.')
    try:
        with db.transaction() as cur:
            cur.execute(
                """INSERT INTO appointments (a_patient_id, a_doctor_id, a_facility_id, a_date,
                       a_start_time, a_end_time, a_reason, a_patient_note)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING a_id""",
                (patient['p_id'], doctor_id, facility_id, day, slot[0], slot[1], reason, note))
            appointment_id = cur.fetchone()['a_id']
            cur.execute('SELECT d_user_id FROM doctors WHERE d_id = %s', (doctor_id,))
            notify(cur.fetchone()['d_user_id'], 'appointment', 'Nouvelle demande de rendez-vous',
                   f"{patient['p_first_name']} {patient['p_last_name']} — {day.isoformat()} "
                   f"à {slot[0].strftime('%H:%M')}.", cur)
    except psycopg.errors.ExclusionViolation:
        raise HttpError(409, 'Ce créneau vient d’être pris.')
    return ok({'id': appointment_id}, 'Demande de rendez-vous envoyée.', 201)


@route('POST', '/api/patient/appointments/{aid}/cancel', roles=('patient',))
def cancel_appointment(request):
    patient = current_patient(request)
    with db.transaction() as cur:
        cur.execute(
            """UPDATE appointments SET a_status = 'cancelled'
               WHERE a_id = %s AND a_patient_id = %s AND a_status IN ('pending', 'confirmed')
                 AND (a_date + a_start_time) > %s
               RETURNING a_doctor_id, a_date, a_start_time""",
            (request.params['aid'], patient['p_id'], config.now_local()))
        row = cur.fetchone()
        if row is None:
            raise HttpError(409, 'Ce rendez-vous ne peut plus être annulé.')
        cur.execute('SELECT d_user_id FROM doctors WHERE d_id = %s', (row['a_doctor_id'],))
        notify(cur.fetchone()['d_user_id'], 'appointment', 'Rendez-vous annulé',
               f"{patient['p_first_name']} {patient['p_last_name']} a annulé le "
               f"{row['a_date'].isoformat()} à {row['a_start_time'].strftime('%H:%M')}.", cur)
    return ok(message='Rendez-vous annulé.')


@route('POST', '/api/patient/family', roles=('patient',))
def family_request(request):
    patient = current_patient(request)
    data = request.json()
    identifier = validation.text(data.get('identifier'), 'L’identifiant', 255)
    relationship = validation.text(data.get('relationship'), 'Le lien familial', 50)
    target = _find_patient(identifier)
    if target is None:
        raise HttpError(404, 'Aucun patient trouvé avec cet identifiant.')
    if target['p_id'] == patient['p_id']:
        raise HttpError(400, 'Vous ne pouvez pas vous ajouter vous-même.')
    active = db.fetch_one(
        """SELECT 1 FROM family_relationships
           WHERE fr_status IN ('pending', 'accepted')
             AND ((fr_patient_id = %s AND fr_related_user_id = %s)
               OR (fr_patient_id = %s AND fr_related_user_id = %s))""",
        (patient['p_id'], target['u_id'], target['p_id'], request.user['id']))
    if active:
        raise HttpError(409, 'Une relation ou une demande existe déjà avec ce patient.')
    db.execute(
        """INSERT INTO family_relationships (fr_patient_id, fr_related_user_id, fr_relationship)
           VALUES (%s, %s, %s)
           ON CONFLICT (fr_patient_id, fr_related_user_id)
           DO UPDATE SET fr_status = 'pending', fr_relationship = EXCLUDED.fr_relationship""",
        (patient['p_id'], target['u_id'], relationship))
    notify(target['u_id'], 'family', 'Demande de lien familial',
           f"{patient['p_first_name']} {patient['p_last_name']} souhaite vous ajouter comme "
           f"« {relationship} ». Cela ne donne aucun accès médical.")
    return ok(message='Demande envoyée.', status=201)


@route('POST', '/api/patient/family/{fid}/respond', roles=('patient',))
def family_respond(request):
    patient = current_patient(request)
    accept = request.json().get('accept')
    if not isinstance(accept, bool):
        raise HttpError(400, 'Réponse invalide.')
    row = db.fetch_one(
        """UPDATE family_relationships SET fr_status = %s
           WHERE fr_id = %s AND fr_related_user_id = %s AND fr_status = 'pending'
           RETURNING fr_patient_id""",
        ('accepted' if accept else 'rejected', request.params['fid'], request.user['id']))
    if row is None:
        raise HttpError(404, 'Demande introuvable.')
    requester = db.fetch_one('SELECT p_user_id FROM patients WHERE p_id = %s', (row['fr_patient_id'],))
    notify(requester['p_user_id'], 'family',
           'Demande acceptée' if accept else 'Demande refusée',
           f"{patient['p_first_name']} {patient['p_last_name']} a "
           f"{'accepté' if accept else 'refusé'} votre demande de lien familial.")
    return ok(message='Réponse enregistrée.')


@route('POST', '/api/patient/family/{fid}/remove', roles=('patient',))
def family_remove(request):
    patient = current_patient(request)
    changed = db.execute(
        """UPDATE family_relationships SET fr_status = 'removed'
           WHERE fr_id = %s AND fr_status IN ('pending', 'accepted')
             AND (fr_patient_id = %s OR fr_related_user_id = %s)""",
        (request.params['fid'], patient['p_id'], request.user['id']))
    if not changed:
        raise HttpError(404, 'Relation introuvable.')
    return ok(message='Relation supprimée.')


@route('POST', '/api/patient/access', roles=('patient',))
def grant_access(request):
    patient = current_patient(request)
    uid = request.user['id']
    data = request.json()
    kind = choice(data.get('kind'), ('doctor', 'trusted_person'), 'Le type d’autorisation')
    scopes = data.get('scopes')
    if (not isinstance(scopes, list) or not scopes
            or any(s not in SCOPES for s in scopes)):
        raise HttpError(400, 'Choisissez au moins une portée valide.')
    scopes = sorted(set(scopes))
    days = data.get('days')
    if days is not None and (isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 365):
        raise HttpError(400, 'La durée doit être comprise entre 1 et 365 jours.')

    if kind == 'doctor':
        target = db.fetch_one(
            """SELECT d_user_id AS u_id, d_first_name, d_last_name FROM doctors
               WHERE d_professional_id = %s AND d_verification_status AND d_is_active""",
            (validation.text(data.get('professional_id'), 'L’identifiant professionnel', 100),))
    else:
        if any(s not in READ_ONLY_SCOPES for s in scopes):
            raise HttpError(400, 'Une personne de confiance ne peut avoir qu’un accès en lecture.')
        target = _find_patient(validation.text(data.get('identifier'), 'L’identifiant', 255))
    if target is None:
        raise HttpError(404, 'Bénéficiaire introuvable.')
    if target['u_id'] == uid:
        raise HttpError(400, 'Vous avez déjà accès à votre propre dossier.')

    _expire_grants()
    params = (scopes, days, days, patient['p_id'], target['u_id'])
    with db.transaction() as cur:
        cur.execute(
            """UPDATE medical_access SET ma_scopes = %s,
                   ma_end_at = CASE WHEN %s::int IS NULL THEN NULL
                                    ELSE now() + make_interval(days => %s::int) END
               WHERE ma_patient_id = %s AND ma_granted_to_user_id = %s AND ma_status = 'active'
               RETURNING ma_id""", params)
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """INSERT INTO medical_access (ma_patient_id, ma_granted_to_user_id,
                       ma_granted_by_user_id, ma_kind, ma_scopes, ma_end_at)
                   VALUES (%s, %s, %s, %s, %s,
                           CASE WHEN %s::int IS NULL THEN NULL
                                ELSE now() + make_interval(days => %s::int) END)
                   RETURNING ma_id""",
                (patient['p_id'], target['u_id'], uid, kind, scopes, days, days))
            row = cur.fetchone()
        notify(target['u_id'], 'medical_access', 'Accès à un dossier médical',
               f"{patient['p_first_name']} {patient['p_last_name']} vous a autorisé à consulter "
               f"son dossier ({', '.join(scopes)}).", cur)
    log_access(request, uid, patient['p_id'], 'access.grant', 'medical_access', row['ma_id'])
    return ok({'id': row['ma_id']}, 'Autorisation enregistrée.', 201)


@route('POST', '/api/patient/access/{mid}/revoke', roles=('patient',))
def revoke_access(request):
    patient = current_patient(request)
    row = db.fetch_one(
        """UPDATE medical_access SET ma_status = 'revoked', ma_end_at = now()
           WHERE ma_id = %s AND ma_patient_id = %s AND ma_status = 'active'
           RETURNING ma_granted_to_user_id""", (request.params['mid'], patient['p_id']))
    if row is None:
        raise HttpError(404, 'Autorisation introuvable.')
    notify(row['ma_granted_to_user_id'], 'medical_access', 'Accès retiré',
           f"{patient['p_first_name']} {patient['p_last_name']} a retiré votre accès à son dossier.")
    log_access(request, request.user['id'], patient['p_id'], 'access.revoke',
               'medical_access', request.params['mid'])
    return ok(message='Accès retiré immédiatement.')
