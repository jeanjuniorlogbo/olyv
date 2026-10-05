"""Créneaux de rendez-vous : calculés côté serveur, jamais fournis par le client."""
from datetime import datetime, timedelta

import config
from app import db

MAX_DAYS_AHEAD = 90


def valid_link(doctor_id, facility_id, day):
    row = db.fetch_one(
        """
        SELECT 1
        FROM doctor_facilities df
        JOIN doctors d ON d.d_id = df.df_doctor_id
        JOIN health_facilities hf ON hf.hf_id = df.df_facility_id
        WHERE df.df_doctor_id = %s AND df.df_facility_id = %s
          AND df.df_status AND NOT df.df_pending
          AND df.df_start_date <= %s AND (df.df_end_date IS NULL OR df.df_end_date >= %s)
          AND d.d_verification_status AND d.d_is_active
          AND hf.hf_status AND hf.hf_verification_status
        """, (doctor_id, facility_id, day, day))
    return row is not None


def free_slots(doctor_id, facility_id, day):
    """[(début, fin)] libres pour ce médecin, cet établissement et ce jour."""
    now = config.now_local()
    if day < now.date() or day > now.date() + timedelta(days=MAX_DAYS_AHEAD):
        return []
    if not valid_link(doctor_id, facility_id, day):
        return []
    availabilities = db.fetch_all(
        """SELECT da_start_time, da_end_time, da_slot_minutes FROM doctor_availabilities
           WHERE da_doctor_id = %s AND da_facility_id = %s AND da_day_of_week = %s AND da_status""",
        (doctor_id, facility_id, day.isoweekday()))
    busy = db.fetch_all(
        """SELECT a_start_time, a_end_time FROM appointments
           WHERE a_doctor_id = %s AND a_date = %s AND a_status IN ('pending', 'confirmed')""",
        (doctor_id, day))
    slots = set()
    for av in availabilities:
        cursor = datetime.combine(day, av['da_start_time'])
        end = datetime.combine(day, av['da_end_time'])
        step = timedelta(minutes=av['da_slot_minutes'])
        while cursor + step <= end:
            start_t, end_t = cursor.time(), (cursor + step).time()
            free = not any(b['a_start_time'] < end_t and b['a_end_time'] > start_t for b in busy)
            if cursor > now and free:
                slots.add((start_t, end_t))
            cursor += step
    return sorted(slots)
