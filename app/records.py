"""Lecture du dossier médical. Appeler UNIQUEMENT après un contrôle d'accès."""
from app import db

# Vue « patient / personne de confiance » : rien de ce qui dépend d'une consultation non clôturée.
_VALID = "(x.{col} IS NULL OR c.c_status = 'closed')"


def _visible(col, validated_only):
    return _VALID.format(col=col) if validated_only else 'TRUE'


def load_record(pid, validated_only=True, documents=True):
    doc = "d.d_first_name || ' ' || d.d_last_name"
    record = db.fetch_one(
        f"""SELECT mr.mr_blood_group AS blood_group, mr.mr_validated_at AS validated_at,
                   {doc} AS validated_by
            FROM medical_records mr LEFT JOIN doctors d ON d.d_id = mr.mr_validated_by
            WHERE mr.mr_patient_id = %s""", (pid,))

    consultations = db.fetch_all(
        f"""SELECT c.c_id, c.c_date, c.c_status::text AS status, c.c_reason, c.c_observations,
                   c.c_conclusion, c.c_closed_at, c.c_appointment_id, {doc} AS doctor,
                   d.d_specialty, hf.hf_name
            FROM consultations c
            JOIN doctors d ON d.d_id = c.c_doctor_id
            JOIN health_facilities hf ON hf.hf_id = c.c_facility_id
            WHERE c.c_patient_id = %s {"AND c.c_status = 'closed'" if validated_only else ''}
            ORDER BY c.c_date DESC""", (pid,))

    diagnoses = db.fetch_all(
        f"""SELECT x.dg_id, x.dg_consultation_id, x.dg_name, x.dg_description, x.dg_created_at,
                   {doc} AS doctor
            FROM diagnoses x
            JOIN consultations c ON c.c_id = x.dg_consultation_id
            JOIN doctors d ON d.d_id = x.dg_created_by
            WHERE c.c_patient_id = %s {"AND c.c_status = 'closed'" if validated_only else ''}
            ORDER BY x.dg_created_at DESC""", (pid,))

    allergies = db.fetch_all(
        f"""SELECT x.al_id, x.al_name, x.al_description, x.al_severity::text AS severity,
                   x.al_status, x.al_created_at, {doc} AS doctor
            FROM allergies x JOIN doctors d ON d.d_id = x.al_created_by
            WHERE x.al_patient_id = %s ORDER BY x.al_created_at DESC""", (pid,))

    treatments = db.fetch_all(
        f"""SELECT x.tr_id, x.tr_consultation_id, x.tr_name, x.tr_description, x.tr_start_date,
                   x.tr_end_date, x.tr_status, x.tr_created_at, {doc} AS doctor
            FROM treatments x
            JOIN doctors d ON d.d_id = x.tr_created_by
            LEFT JOIN consultations c ON c.c_id = x.tr_consultation_id
            WHERE x.tr_patient_id = %s AND {_visible('tr_consultation_id', validated_only)}
            ORDER BY x.tr_created_at DESC""", (pid,))

    prescriptions = db.fetch_all(
        f"""SELECT x.pr_id, x.pr_consultation_id, x.pr_date, x.pr_notes, {doc} AS doctor,
                   d.d_specialty
            FROM prescriptions x
            JOIN doctors d ON d.d_id = x.pr_doctor_id
            LEFT JOIN consultations c ON c.c_id = x.pr_consultation_id
            WHERE x.pr_patient_id = %s AND {_visible('pr_consultation_id', validated_only)}
            ORDER BY x.pr_date DESC""", (pid,))
    if prescriptions:
        items = db.fetch_all(
            """SELECT pri_prescription_id, pri_medicine_name, pri_dosage, pri_frequency,
                      pri_duration, pri_instructions
               FROM prescription_items WHERE pri_prescription_id = ANY(%s) ORDER BY pri_id""",
            ([p['pr_id'] for p in prescriptions],))
        for p in prescriptions:
            p['items'] = [i for i in items if i['pri_prescription_id'] == p['pr_id']]

    exams = db.fetch_all(
        f"""SELECT x.me_id, x.me_consultation_id, x.me_name, x.me_description, x.me_requested_at,
                   x.me_result, x.me_result_date, x.me_status::text AS status, {doc} AS doctor
            FROM medical_exams x
            JOIN doctors d ON d.d_id = x.me_doctor_id
            LEFT JOIN consultations c ON c.c_id = x.me_consultation_id
            WHERE x.me_patient_id = %s AND {_visible('me_consultation_id', validated_only)}
            ORDER BY x.me_requested_at DESC""", (pid,))

    docs = []
    if documents:
        docs = db.fetch_all(
            f"""SELECT x.md_id, x.md_type::text AS type, x.md_title, x.md_description,
                       x.md_file_name, x.md_created_at, {doc} AS doctor
                FROM medical_documents x
                LEFT JOIN doctors d ON d.d_id = x.md_doctor_id
                LEFT JOIN consultations c ON c.c_id = x.md_consultation_id
                WHERE x.md_patient_id = %s AND {_visible('md_consultation_id', validated_only)}
                ORDER BY x.md_created_at DESC""", (pid,))

    return {'record': record, 'consultations': consultations, 'diagnoses': diagnoses,
            'allergies': allergies, 'treatments': treatments, 'prescriptions': prescriptions,
            'exams': exams, 'documents': docs}
