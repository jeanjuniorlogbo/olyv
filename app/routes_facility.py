"""Espace établissement de santé."""
import psycopg

from app import db, validation
from app.common import choice, current_facility, notifications_for, notify, ok
from app.errors import HttpError
from app.web import route
import config

TYPES = ('hopital', 'clinique', 'cabinet', 'centre_de_sante')


@route('GET', '/api/facility/dashboard', roles=('etablissement',))
def dashboard(request):
    uid = request.user['id']
    facility = db.fetch_one(
        """SELECT hf_id, hf_name, hf_type::text AS hf_type, hf_phone, hf_email, hf_address, hf_city,
                  hf_country, hf_description, hf_services, hf_specialties, hf_opening_hours,
                  hf_logo_url, hf_status, hf_verification_status
           FROM health_facilities WHERE hf_user_id = %s""", (uid,))
    if facility is None:
        raise HttpError(404, 'Établissement introuvable.')
    fid = facility['hf_id']
    doctors = db.fetch_all(
        """SELECT df.df_id, df.df_position, df.df_status, df.df_pending, df.df_start_date,
                  d.d_id, d.d_first_name, d.d_last_name, d.d_specialty, d.d_professional_id,
                  d.d_qualifications, d.d_verification_status
           FROM doctor_facilities df JOIN doctors d ON d.d_id = df.df_doctor_id
           WHERE df.df_facility_id = %s AND (df.df_pending OR df.df_status)
           ORDER BY df.df_pending DESC, d.d_last_name""", (fid,))
    today = config.now_local().date()
    appointments = db.fetch_all(
        """SELECT a.a_id, a.a_date, a.a_start_time, a.a_end_time, a.a_reason, a.a_status::text AS status,
                  p.p_first_name, p.p_last_name, d.d_first_name, d.d_last_name, d.d_specialty
           FROM appointments a
           JOIN patients p ON p.p_id = a.a_patient_id
           JOIN doctors d ON d.d_id = a.a_doctor_id
           WHERE a.a_facility_id = %s AND a.a_date >= %s - 30
           ORDER BY a.a_date, a.a_start_time LIMIT 400""", (fid, today))
    return ok({'facility': facility, 'doctors': doctors, 'appointments': appointments,
               'notifications': notifications_for(uid)})


@route('POST', '/api/facility/profile', roles=('etablissement',))
def update_profile(request):
    facility = current_facility(request)
    data = request.json()
    try:
        db.execute(
            """UPDATE health_facilities SET hf_name = %s, hf_type = %s, hf_phone = %s, hf_email = %s,
                   hf_address = %s, hf_city = %s, hf_country = %s, hf_description = %s,
                   hf_services = %s, hf_specialties = %s, hf_opening_hours = %s WHERE hf_id = %s""",
            (validation.text(data.get('name'), 'Le nom', 255),
             choice(data.get('type'), TYPES, 'Le type'), validation.phone(data.get('phone')),
             validation.email(data.get('email')) if data.get('email') else None,
             validation.text(data.get('address'), 'L’adresse', 500),
             validation.text(data.get('city'), 'La ville'), validation.text(data.get('country'), 'Le pays'),
             validation.text(data.get('description'), 'La description', 3000, False),
             validation.text(data.get('services'), 'Les services', 2000, False),
             validation.text(data.get('specialties'), 'Les spécialités', 2000, False),
             validation.text(data.get('opening_hours'), 'Les horaires', 1000, False), facility['hf_id']))
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, 'Ce téléphone ou cet e-mail est déjà utilisé par un autre établissement.')
    return ok(message='Établissement mis à jour.')


@route('POST', '/api/facility/doctors/invite', roles=('etablissement',))
def invite_doctor(request):
    facility = current_facility(request)
    data = request.json()
    professional_id = validation.text(data.get('professional_id'), 'L’identifiant professionnel')
    position = validation.text(data.get('position'), 'Le poste', 100, False)
    doctor = db.fetch_one('SELECT d_id, d_user_id FROM doctors WHERE d_professional_id = %s AND d_is_active',
                          (professional_id,))
    if doctor is None:
        raise HttpError(404, 'Aucun médecin actif avec cet identifiant professionnel.')
    existing = db.fetch_one('SELECT df_status, df_pending FROM doctor_facilities '
                            'WHERE df_doctor_id = %s AND df_facility_id = %s', (doctor['d_id'], facility['hf_id']))
    if existing and (existing['df_status'] or existing['df_pending']):
        raise HttpError(409, 'Ce médecin est déjà rattaché ou invité.')
    with db.transaction() as cur:
        cur.execute(
            """INSERT INTO doctor_facilities (df_doctor_id, df_facility_id, df_position, df_status, df_pending)
               VALUES (%s, %s, %s, false, true)
               ON CONFLICT (df_doctor_id, df_facility_id)
               DO UPDATE SET df_position = EXCLUDED.df_position, df_status = false, df_pending = true""",
            (doctor['d_id'], facility['hf_id'], position))
        notify(doctor['d_user_id'], 'system', 'Invitation d’un établissement',
               f"{facility['hf_name']} vous invite à rejoindre son équipe.", cur)
    return ok(message='Invitation envoyée.', status=201)


@route('POST', '/api/facility/doctors/{dfid}/remove', roles=('etablissement',))
def remove_doctor(request):
    facility = current_facility(request)
    row = db.fetch_one(
        """UPDATE doctor_facilities SET df_status = false, df_pending = false, df_end_date = current_date
           WHERE df_id = %s AND df_facility_id = %s AND (df_status OR df_pending)
           RETURNING df_doctor_id""", (request.params['dfid'], facility['hf_id']))
    if row is None:
        raise HttpError(404, 'Rattachement introuvable.')
    db.execute('UPDATE doctor_availabilities SET da_status = false WHERE da_doctor_id = %s AND da_facility_id = %s',
               (row['df_doctor_id'], facility['hf_id']))
    return ok(message='Médecin retiré de l’établissement.')


@route('POST', '/api/facility/appointments/{aid}/cancel', roles=('etablissement',))
def cancel_appointment(request):
    facility = current_facility(request)
    with db.transaction() as cur:
        cur.execute(
            """UPDATE appointments SET a_status = 'cancelled'
               WHERE a_id = %s AND a_facility_id = %s AND a_status IN ('pending', 'confirmed')
                 AND (a_date + a_start_time) > %s
               RETURNING a_patient_id, a_doctor_id, a_date, a_start_time""",
            (request.params['aid'], facility['hf_id'], config.now_local()))
        row = cur.fetchone()
        if row is None:
            raise HttpError(409, 'Ce rendez-vous ne peut plus être annulé.')
        when = f"{row['a_date'].isoformat()} à {row['a_start_time'].strftime('%H:%M')}"
        cur.execute('SELECT p_user_id FROM patients WHERE p_id = %s', (row['a_patient_id'],))
        notify(cur.fetchone()['p_user_id'], 'appointment', 'Rendez-vous annulé',
               f"{facility['hf_name']} a annulé votre rendez-vous du {when}.", cur)
        cur.execute('SELECT d_user_id FROM doctors WHERE d_id = %s', (row['a_doctor_id'],))
        notify(cur.fetchone()['d_user_id'], 'appointment', 'Rendez-vous annulé',
               f"{facility['hf_name']} a annulé le rendez-vous du {when}.", cur)
    return ok(message='Rendez-vous annulé.')
