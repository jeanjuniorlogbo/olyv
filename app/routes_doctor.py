"""Espace médecin. Toute donnée médicale passe par require_access()."""
from datetime import timedelta

import psycopg

from app import db, files, records, validation
from app.common import (choice, current_doctor, int_id, notifications_for, notify, ok, parse_date,
                        parse_time)
from app.errors import HttpError
from app.security import can_access, require_access
from app.web import route
import config

BLOOD_GROUPS = ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')
SEVERITIES = ('mild', 'moderate', 'severe')
DOC_TYPES = ('rapport_medical', 'resultat_examen', 'ordonnance', 'certificat', 'autre')
GENDERS = ('male', 'female', 'other', 'prefer_not_to_say')


def _patient_user(pid):
    row = db.fetch_one('SELECT p_user_id FROM patients WHERE p_id = %s', (pid,))
    if row is None:
        raise HttpError(404, 'Patient introuvable.')
    return row['p_user_id']


# ───────────── Tableau de bord ─────────────
@route('GET', '/api/doctor/dashboard', roles=('medecin',))
def dashboard(request):
    uid = request.user['id']
    doctor = db.fetch_one(
        """SELECT d.d_id, d.d_first_name, d.d_last_name, d.d_professional_id, d.d_specialty,
                  d.d_qualifications, d.d_bio, d.d_gender::text AS d_gender, d.d_date_of_birth,
                  d.d_address, d.d_city, d.d_country, d.d_profile_photo_url,
                  d.d_verification_status, d.d_is_active, u.u_email, u.u_phone
           FROM doctors d JOIN users u ON u.u_id = d.d_user_id WHERE d.d_user_id = %s""", (uid,))
    if doctor is None:
        raise HttpError(404, 'Profil médecin introuvable.')
    did = doctor['d_id']
    today = config.now_local().date()

    facilities = db.fetch_all(
        """SELECT df.df_id, df.df_position, df.df_status, df.df_pending, hf.hf_id, hf.hf_name,
                  hf.hf_city, hf.hf_verification_status
           FROM doctor_facilities df JOIN health_facilities hf ON hf.hf_id = df.df_facility_id
           WHERE df.df_doctor_id = %s AND (df.df_pending OR df.df_status)
           ORDER BY df.df_pending DESC, hf.hf_name""", (did,))
    availabilities = db.fetch_all(
        """SELECT da.da_id, da.da_facility_id, hf.hf_name, da.da_day_of_week, da.da_start_time,
                  da.da_end_time, da.da_slot_minutes
           FROM doctor_availabilities da JOIN health_facilities hf ON hf.hf_id = da.da_facility_id
           WHERE da.da_doctor_id = %s AND da.da_status
           ORDER BY da.da_day_of_week, da.da_start_time""", (did,))
    appointments = db.fetch_all(
        """SELECT a.a_id, a.a_patient_id, a.a_date, a.a_start_time, a.a_end_time, a.a_reason,
                  a.a_patient_note, a.a_status::text AS status, a.a_facility_id,
                  p.p_first_name, p.p_last_name, hf.hf_name,
                  EXISTS (SELECT 1 FROM consultations c WHERE c.c_appointment_id = a.a_id) AS has_consultation
           FROM appointments a
           JOIN patients p ON p.p_id = a.a_patient_id
           JOIN health_facilities hf ON hf.hf_id = a.a_facility_id
           WHERE a.a_doctor_id = %s AND a.a_date >= %s
           ORDER BY a.a_date, a.a_start_time LIMIT 300""", (did, today - timedelta(days=30)))
    patients = db.fetch_all(
        """SELECT ma.ma_id, p.p_id, p.p_first_name, p.p_last_name, ma.ma_scopes AS scopes, ma.ma_end_at
           FROM medical_access ma JOIN patients p ON p.p_id = ma.ma_patient_id
           WHERE ma.ma_granted_to_user_id = %s AND ma.ma_kind = 'doctor' AND ma.ma_status = 'active'
                 AND ma.ma_start_at <= now() AND (ma.ma_end_at IS NULL OR ma.ma_end_at > now())
           ORDER BY p.p_last_name, p.p_first_name""", (uid,))
    return ok({'doctor': doctor, 'facilities': facilities, 'availabilities': availabilities,
               'appointments': appointments, 'patients': patients,
               'notifications': notifications_for(uid)})


@route('POST', '/api/doctor/profile', roles=('medecin',))
def update_profile(request):
    data = request.json()
    dob = parse_date(data.get('date_of_birth'), 'La date de naissance', required=False)
    try:
        db.execute(
            """UPDATE doctors SET d_first_name = %s, d_last_name = %s, d_specialty = %s,
                   d_qualifications = %s, d_bio = %s, d_gender = %s, d_date_of_birth = %s,
                   d_address = %s, d_city = %s, d_country = %s WHERE d_user_id = %s""",
            (validation.text(data.get('first_name'), 'Le prénom'),
             validation.text(data.get('last_name'), 'Le nom'),
             validation.text(data.get('specialty'), 'La spécialité', 255),
             validation.text(data.get('qualifications'), 'Les qualifications', 2000, False),
             validation.text(data.get('bio'), 'La présentation', 3000, False),
             choice(data.get('gender'), GENDERS, 'Le genre'), dob,
             validation.text(data.get('address'), 'L’adresse', 500, False),
             validation.text(data.get('city'), 'La ville', 100, False),
             validation.text(data.get('country'), 'Le pays', 100, False), request.user['id']))
        db.execute('UPDATE users SET u_phone = %s WHERE u_id = %s',
                   (validation.phone(data.get('phone')), request.user['id']))
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, 'Ce numéro de téléphone est déjà utilisé.')
    return ok(message='Profil mis à jour.')


# ───────────── Établissements & disponibilités ─────────────
@route('POST', '/api/doctor/invitations/{dfid}/respond', roles=('medecin',))
def respond_invitation(request):
    doctor = current_doctor(request)
    accept = request.json().get('accept')
    if not isinstance(accept, bool):
        raise HttpError(400, 'Réponse invalide.')
    if accept:
        row = db.fetch_one(
            """UPDATE doctor_facilities SET df_status = true, df_pending = false,
                   df_start_date = current_date, df_end_date = NULL
               WHERE df_id = %s AND df_doctor_id = %s AND df_pending RETURNING df_facility_id""",
            (request.params['dfid'], doctor['d_id']))
    else:
        row = db.fetch_one(
            """UPDATE doctor_facilities SET df_pending = false, df_status = false
               WHERE df_id = %s AND df_doctor_id = %s AND df_pending RETURNING df_facility_id""",
            (request.params['dfid'], doctor['d_id']))
    if row is None:
        raise HttpError(404, 'Invitation introuvable.')
    owner = db.fetch_one('SELECT hf_user_id FROM health_facilities WHERE hf_id = %s', (row['df_facility_id'],))
    if owner and owner['hf_user_id']:
        notify(owner['hf_user_id'], 'system', 'Réponse à votre invitation',
               f"Dr {doctor['d_first_name']} {doctor['d_last_name']} a "
               f"{'accepté' if accept else 'refusé'} de rejoindre votre établissement.")
    return ok(message='Réponse enregistrée.')


@route('POST', '/api/doctor/availabilities', roles=('medecin',))
def add_availability(request):
    doctor = current_doctor(request)
    data = request.json()
    facility_id = int_id(data.get('facility_id'), 'L’établissement')
    day = data.get('day_of_week')
    if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 7:
        raise HttpError(400, 'Le jour est invalide.')
    start, end = parse_time(data.get('start_time'), 'L’heure de début'), parse_time(data.get('end_time'), 'L’heure de fin')
    slot = data.get('slot_minutes', 30)
    if isinstance(slot, bool) or not isinstance(slot, int) or not 10 <= slot <= 240:
        raise HttpError(400, 'La durée d’un créneau doit être comprise entre 10 et 240 minutes.')
    if end <= start:
        raise HttpError(400, 'L’heure de fin doit être après l’heure de début.')
    linked = db.fetch_one(
        """SELECT 1 FROM doctor_facilities WHERE df_doctor_id = %s AND df_facility_id = %s
           AND df_status AND NOT df_pending""", (doctor['d_id'], facility_id))
    if linked is None:
        raise HttpError(403, 'Vous n’êtes pas rattaché à cet établissement.')
    overlap = db.fetch_one(
        """SELECT 1 FROM doctor_availabilities WHERE da_doctor_id = %s AND da_day_of_week = %s
           AND da_status AND da_start_time < %s AND da_end_time > %s""",
        (doctor['d_id'], day, end, start))
    if overlap:
        raise HttpError(409, 'Cette plage chevauche une disponibilité existante.')
    db.execute(
        """INSERT INTO doctor_availabilities (da_doctor_id, da_facility_id, da_day_of_week,
               da_start_time, da_end_time, da_slot_minutes) VALUES (%s, %s, %s, %s, %s, %s)""",
        (doctor['d_id'], facility_id, day, start, end, slot))
    return ok(message='Disponibilité ajoutée.', status=201)


@route('POST', '/api/doctor/availabilities/{daid}/delete', roles=('medecin',))
def delete_availability(request):
    doctor = current_doctor(request)
    if not db.execute('DELETE FROM doctor_availabilities WHERE da_id = %s AND da_doctor_id = %s',
                      (request.params['daid'], doctor['d_id'])):
        raise HttpError(404, 'Disponibilité introuvable.')
    return ok(message='Disponibilité supprimée.')


# ───────────── Rendez-vous ─────────────
_ACTIONS = {
    'confirm':  ('pending',   'confirmed', 'Rendez-vous confirmé', 'a confirmé'),
    'reject':   ('pending',   'rejected',  'Rendez-vous refusé', 'a refusé'),
    'complete': ('confirmed', 'completed', 'Rendez-vous terminé', 'a marqué comme terminé'),
    'no_show':  ('confirmed', 'no_show',   'Absence signalée', 'a signalé votre absence à'),
}


@route('POST', '/api/doctor/appointments/{aid}/{action:w}', roles=('medecin',))
def appointment_action(request):
    doctor = current_doctor(request, verified=True)
    action = request.params['action']
    if action not in _ACTIONS:
        raise HttpError(404, 'Action inconnue.')
    from_status, to_status, title, verb = _ACTIONS[action]
    now = config.now_local()
    time_rule = {'confirm': '(a.a_date + a.a_start_time) > %s',
                 'reject': 'TRUE OR %s IS NULL',
                 'complete': 'a.a_date <= %s::date',
                 'no_show': '(a.a_date + a.a_end_time) <= %s'}[action]
    time_arg = now.date() if action == 'complete' else now
    with db.transaction() as cur:
        cur.execute(
            f"""UPDATE appointments a SET a_status = %s
                WHERE a.a_id = %s AND a.a_doctor_id = %s AND a.a_status = %s AND ({time_rule})
                RETURNING a.a_patient_id, a.a_date, a.a_start_time""",
            (to_status, request.params['aid'], doctor['d_id'], from_status, time_arg))
        row = cur.fetchone()
        if row is None:
            raise HttpError(409, 'Action impossible pour ce rendez-vous (statut ou horaire).')
        cur.execute('SELECT p_user_id FROM patients WHERE p_id = %s', (row['a_patient_id'],))
        notify(cur.fetchone()['p_user_id'], 'appointment', title,
               f"Dr {doctor['d_last_name']} {verb} votre rendez-vous du "
               f"{row['a_date'].isoformat()} à {row['a_start_time'].strftime('%H:%M')}.", cur)
    return ok(message=title + '.')


# ───────────── Dossier d'un patient (sous autorisation) ─────────────
@route('GET', '/api/doctor/patients/{pid}/record', roles=('medecin',))
def patient_record(request):
    current_doctor(request, verified=True)
    pid = request.params['pid']
    require_access(request, pid, 'record.read', 'record')
    name = db.fetch_one('SELECT p_first_name, p_last_name, p_date_of_birth, p_gender::text AS p_gender '
                        'FROM patients WHERE p_id = %s', (pid,))
    docs = can_access(request.user, pid, 'documents.read')
    can_write = can_access(request.user, pid, 'record.write')
    data = records.load_record(pid, validated_only=False, documents=docs)
    data.update({'patient': name, 'can_write': can_write,
                 'can_write_documents': can_access(request.user, pid, 'documents.write')})
    return ok(data)


def _own_consultation(cid, pid, doctor_id, need_open=True):
    row = db.fetch_one('SELECT c_id, c_status::text AS status FROM consultations '
                       'WHERE c_id = %s AND c_patient_id = %s AND c_doctor_id = %s', (cid, pid, doctor_id))
    if row is None:
        raise HttpError(404, 'Consultation introuvable.')
    if need_open and row['status'] != 'open':
        raise HttpError(409, 'Cette consultation est clôturée.')
    return row


@route('POST', '/api/doctor/patients/{pid}/consultations', roles=('medecin',))
def create_consultation(request):
    doctor = current_doctor(request, verified=True)
    pid = request.params['pid']
    require_access(request, pid, 'record.write', 'consultation')
    data = request.json()
    reason = validation.text(data.get('reason'), 'Le motif', 2000, required=False)
    appointment_id = data.get('appointment_id')
    if appointment_id is not None:
        appt = db.fetch_one(
            """SELECT a_id, a_facility_id, a_reason, a_status::text AS status FROM appointments
               WHERE a_id = %s AND a_doctor_id = %s AND a_patient_id = %s""",
            (int_id(appointment_id, 'Le rendez-vous'), doctor['d_id'], pid))
        if appt is None:
            raise HttpError(404, 'Rendez-vous introuvable.')
        if appt['status'] != 'confirmed':
            raise HttpError(409, 'Seul un rendez-vous confirmé peut donner lieu à une consultation.')
        facility_id, reason = appt['a_facility_id'], reason or appt['a_reason']
    else:
        facility_id = int_id(data.get('facility_id'), 'L’établissement')
        if db.fetch_one("SELECT 1 FROM doctor_facilities WHERE df_doctor_id = %s AND df_facility_id = %s "
                        "AND df_status AND NOT df_pending", (doctor['d_id'], facility_id)) is None:
            raise HttpError(403, 'Vous n’êtes pas rattaché à cet établissement.')
    try:
        row = db.fetch_one(
            """INSERT INTO consultations (c_patient_id, c_doctor_id, c_facility_id, c_appointment_id, c_reason)
               VALUES (%s, %s, %s, %s, %s) RETURNING c_id""",
            (pid, doctor['d_id'], facility_id, appointment_id, reason))
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, 'Une consultation existe déjà pour ce rendez-vous.')
    return ok({'id': row['c_id']}, 'Consultation créée.', 201)


@route('POST', '/api/doctor/consultations/{cid}', roles=('medecin',))
def save_consultation(request):
    doctor = current_doctor(request, verified=True)
    cid = request.params['cid']
    c = db.fetch_one('SELECT c_patient_id, c_status::text AS status, c_appointment_id, c_conclusion '
                     'FROM consultations WHERE c_id = %s AND c_doctor_id = %s', (cid, doctor['d_id']))
    if c is None:
        raise HttpError(404, 'Consultation introuvable.')
    require_access(request, c['c_patient_id'], 'record.write', 'consultation', cid)
    if c['status'] != 'open':
        raise HttpError(409, 'Cette consultation est clôturée.')
    data = request.json()
    observations = validation.text(data.get('observations'), 'Les observations', 10000, False)
    conclusion = validation.text(data.get('conclusion'), 'La conclusion', 5000, False) or c['c_conclusion']
    close = data.get('close') is True
    if close and not conclusion:
        raise HttpError(400, 'Une conclusion est nécessaire pour clôturer la consultation.')
    with db.transaction() as cur:
        cur.execute(
            """UPDATE consultations SET c_observations = COALESCE(%s, c_observations), c_conclusion = %s,
                   c_status = CASE WHEN %s THEN 'closed'::consultation_status ELSE c_status END,
                   c_closed_at = CASE WHEN %s THEN now() ELSE c_closed_at END WHERE c_id = %s""",
            (observations, conclusion, close, close, cid))
        if close:
            if c['c_appointment_id']:
                cur.execute("UPDATE appointments SET a_status = 'completed' WHERE a_id = %s "
                            "AND a_status = 'confirmed'", (c['c_appointment_id'],))
            cur.execute('SELECT p_user_id FROM patients WHERE p_id = %s', (c['c_patient_id'],))
            notify(cur.fetchone()['p_user_id'], 'medical_access', 'Consultation disponible',
                   f"Dr {doctor['d_last_name']} a clôturé votre consultation : elle est dans votre dossier.", cur)
    return ok(message='Consultation clôturée.' if close else 'Consultation enregistrée.')


def _add_blood_group(cur, ctx, d):
    value = choice(d.get('value'), BLOOD_GROUPS, 'Le groupe sanguin')
    cur.execute('UPDATE medical_records SET mr_blood_group = %s, mr_validated_by = %s, '
                'mr_validated_at = now() WHERE mr_patient_id = %s', (value, ctx['did'], ctx['pid']))


def _add_diagnosis(cur, ctx, d):
    cid = _own_consultation(int_id(d.get('consultation_id'), 'La consultation'), ctx['pid'], ctx['did'])['c_id']
    cur.execute('INSERT INTO diagnoses (dg_consultation_id, dg_created_by, dg_name, dg_description) '
                'VALUES (%s, %s, %s, %s) RETURNING dg_id',
                (cid, ctx['did'], validation.text(d.get('name'), 'Le diagnostic', 255),
                 validation.text(d.get('description'), 'La description', 3000, False)))
    return cur.fetchone()['dg_id']


def _add_allergy(cur, ctx, d):
    cur.execute('INSERT INTO allergies (al_patient_id, al_name, al_description, al_severity, al_created_by) '
                'VALUES (%s, %s, %s, %s, %s) RETURNING al_id',
                (ctx['pid'], validation.text(d.get('name'), 'L’allergie', 255),
                 validation.text(d.get('description'), 'La description', 3000, False),
                 choice(d.get('severity'), SEVERITIES, 'La sévérité', False), ctx['did']))
    return cur.fetchone()['al_id']


def _optional_consultation(d, ctx):
    if d.get('consultation_id') in (None, ''):
        return None
    return _own_consultation(int_id(d.get('consultation_id'), 'La consultation'), ctx['pid'], ctx['did'])['c_id']


def _add_treatment(cur, ctx, d):
    start = parse_date(d.get('start_date'), 'La date de début', False)
    end = parse_date(d.get('end_date'), 'La date de fin', False)
    if start and end and end < start:
        raise HttpError(400, 'La date de fin est avant la date de début.')
    cur.execute('INSERT INTO treatments (tr_patient_id, tr_consultation_id, tr_name, tr_description, '
                'tr_start_date, tr_end_date, tr_created_by) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING tr_id',
                (ctx['pid'], _optional_consultation(d, ctx), validation.text(d.get('name'), 'Le traitement', 255),
                 validation.text(d.get('description'), 'La description', 3000, False), start, end, ctx['did']))
    return cur.fetchone()['tr_id']


def _add_prescription(cur, ctx, d):
    items = d.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 20 or not all(isinstance(i, dict) for i in items):
        raise HttpError(400, 'Ajoutez entre 1 et 20 médicaments.')
    clean = [(validation.text(i.get('medicine_name'), 'Le médicament', 255),
              validation.text(i.get('dosage'), 'La posologie', 100, False),
              validation.text(i.get('frequency'), 'La fréquence', 100, False),
              validation.text(i.get('duration'), 'La durée', 100, False),
              validation.text(i.get('instructions'), 'Les instructions', 1000, False)) for i in items]
    cur.execute('INSERT INTO prescriptions (pr_patient_id, pr_doctor_id, pr_consultation_id, pr_notes) '
                'VALUES (%s, %s, %s, %s) RETURNING pr_id',
                (ctx['pid'], ctx['did'], _optional_consultation(d, ctx),
                 validation.text(d.get('notes'), 'Les notes', 3000, False)))
    prid = cur.fetchone()['pr_id']
    for item in clean:
        cur.execute('INSERT INTO prescription_items (pri_prescription_id, pri_medicine_name, pri_dosage, '
                    'pri_frequency, pri_duration, pri_instructions) VALUES (%s, %s, %s, %s, %s, %s)', (prid,) + item)
    notify(_patient_user(ctx['pid']), 'medical_access', 'Nouvelle ordonnance',
           f"Dr {ctx['dname']} a ajouté une ordonnance à votre dossier.", cur)
    return prid


def _add_exam(cur, ctx, d):
    cur.execute('INSERT INTO medical_exams (me_patient_id, me_doctor_id, me_consultation_id, me_name, me_description) '
                'VALUES (%s, %s, %s, %s, %s) RETURNING me_id',
                (ctx['pid'], ctx['did'], _optional_consultation(d, ctx),
                 validation.text(d.get('name'), 'L’examen', 255),
                 validation.text(d.get('description'), 'La description', 3000, False)))
    return cur.fetchone()['me_id']


def _add_exam_result(cur, ctx, d):
    cur.execute("UPDATE medical_exams SET me_result = %s, me_result_date = now(), me_status = 'completed' "
                "WHERE me_id = %s AND me_patient_id = %s AND me_status <> 'cancelled' RETURNING me_id",
                (validation.text(d.get('result'), 'Le résultat', 10000),
                 int_id(d.get('exam_id'), 'L’examen'), ctx['pid']))
    row = cur.fetchone()
    if row is None:
        raise HttpError(404, 'Examen introuvable.')
    notify(_patient_user(ctx['pid']), 'medical_access', 'Résultat d’examen disponible',
           f"Dr {ctx['dname']} a ajouté un résultat à votre dossier.", cur)
    return row['me_id']


_KINDS = {'blood_group': _add_blood_group, 'diagnosis': _add_diagnosis, 'allergy': _add_allergy,
          'treatment': _add_treatment, 'prescription': _add_prescription, 'exam': _add_exam,
          'exam_result': _add_exam_result}


@route('POST', '/api/doctor/patients/{pid}/records/{kind:w}', roles=('medecin',))
def add_record(request):
    doctor = current_doctor(request, verified=True)
    pid, kind = request.params['pid'], request.params['kind']
    if kind not in _KINDS:
        raise HttpError(404, 'Type d’information inconnu.')
    require_access(request, pid, 'record.write', kind)
    ctx = {'pid': pid, 'did': doctor['d_id'], 'dname': doctor['d_last_name']}
    data = request.json()
    with db.transaction() as cur:
        new_id = _KINDS[kind](cur, ctx, data)
    return ok({'id': new_id}, 'Information enregistrée.', 201)


@route('POST', '/api/doctor/patients/{pid}/documents', roles=('medecin',))
def upload_document(request):
    doctor = current_doctor(request, verified=True)
    pid = request.params['pid']
    require_access(request, pid, 'documents.write', 'document')
    data = request.json(limit=4_500_000)
    doc_type = choice(data.get('type'), DOC_TYPES, 'Le type de document')
    title = validation.text(data.get('title'), 'Le titre', 255)
    raw, ext, mime = files.decode_upload(data.get('content_base64'), {'pdf', 'png', 'jpg'}, 3_000_000)
    consultation_id = _optional_consultation(data, {'pid': pid, 'did': doctor['d_id']})
    key = files.save('documents', raw, ext)
    file_name = validation.text(data.get('file_name'), 'Le nom du fichier', 255, False) or f'document.{ext}'
    with db.transaction() as cur:
        cur.execute(
            """INSERT INTO medical_documents (md_patient_id, md_doctor_id, md_consultation_id, md_type,
                   md_title, md_description, md_storage_key, md_file_name, md_mime_type)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING md_id""",
            (pid, doctor['d_id'], consultation_id, doc_type, title,
             validation.text(data.get('description'), 'La description', 3000, False), key, file_name, mime))
        new_id = cur.fetchone()['md_id']
        notify(_patient_user(pid), 'medical_access', 'Nouveau document',
               f"Dr {doctor['d_last_name']} a ajouté « {title} » à votre dossier.", cur)
    return ok({'id': new_id}, 'Document ajouté.', 201)
