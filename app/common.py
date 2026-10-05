"""Aides partagées par les routes."""
import re
from datetime import date, time

from app import db
from app.errors import HttpError
from app.web import json_response


def ok(data=None, message=None, status=200):
    body = {'success': True}
    if message:
        body['message'] = message
    if data is not None:
        body['data'] = data
    return json_response(body, status)


def notify(user_id, kind, title, message, cur=None):
    sql = ('INSERT INTO notifications (n_user_id, n_type, n_title, n_message) '
           'VALUES (%s, %s, %s, %s)')
    params = (user_id, kind, title, message)
    if cur is not None:
        cur.execute(sql, params)
    else:
        db.execute(sql, params)


def like(value):
    """Motif ILIKE sûr (échappe % _ \\) ou None."""
    value = (value or '').strip()[:100]
    if not value:
        return None
    return '%' + re.sub(r'([\\%_])', r'\\\1', value) + '%'


def parse_date(value, label='La date', required=True):
    if value in (None, ''):
        if required:
            raise HttpError(400, f'{label} est obligatoire.')
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise HttpError(400, f'{label} est invalide.')


def parse_time(value, label='L’heure'):
    try:
        parts = value.split(':')
        return time(int(parts[0]), int(parts[1]))
    except (AttributeError, ValueError, IndexError):
        raise HttpError(400, f'{label} est invalide.')


def choice(value, allowed, label, required=True):
    if value in (None, ''):
        if required:
            raise HttpError(400, f'{label} est obligatoire.')
        return None
    if value not in allowed:
        raise HttpError(400, f'{label} est invalide.')
    return value


def int_id(value, label):
    if isinstance(value, bool):
        raise HttpError(400, f'{label} est invalide.')
    try:
        ivalue = int(value)
    except (ValueError, TypeError):
        raise HttpError(400, f'{label} est invalide.')
    if ivalue <=0:
        raise HttpError(400, f'{label} est invalide.')
    return ivalue


def current_patient(request):
    row = db.fetch_one('SELECT p_id, p_first_name, p_last_name FROM patients WHERE p_user_id = %s',
                       (request.user['id'],))
    if row is None:
        raise HttpError(404, 'Dossier patient introuvable.')
    return row


def current_doctor(request, verified=False):
    row = db.fetch_one(
        """SELECT d_id, d_first_name, d_last_name, d_verification_status, d_is_active
           FROM doctors WHERE d_user_id = %s""", (request.user['id'],))
    if row is None:
        raise HttpError(404, 'Profil médecin introuvable.')
    if verified and not (row['d_verification_status'] and row['d_is_active']):
        raise HttpError(403, 'Votre compte médecin doit être vérifié par un administrateur.')
    return row


def current_facility(request):
    row = db.fetch_one('SELECT hf_id, hf_name FROM health_facilities WHERE hf_user_id = %s',
                       (request.user['id'],))
    if row is None:
        raise HttpError(404, 'Établissement introuvable.')
    return row


def notifications_for(user_id, limit=50):
    return db.fetch_all(
        """SELECT n_id, n_type::text AS type, n_title, n_message, n_is_read, n_created_at
           FROM notifications WHERE n_user_id = %s ORDER BY n_created_at DESC LIMIT %s""",
        (user_id, limit))


def setting(key, default=''):
    row = db.fetch_one('SELECT ps_value FROM platform_settings WHERE ps_key = %s', (key,))
    return row['ps_value'] if row else default
