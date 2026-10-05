"""Sessions serveur. Le cookie contient le jeton ; la base ne stocke que son hash."""
import hashlib
import secrets

import config
from app import db

COOKIE = 'Olyvera_session'


def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create(user_id):
    token = secrets.token_urlsafe(48)
    db.execute(
        """
        INSERT INTO sessions (s_token, s_user_id, s_expires_at)
        VALUES (%s, %s, now() + make_interval(hours => %s))
        """,
        (_hash(token), user_id, config.SESSION_HOURS),
    )
    db.execute(
        'DELETE FROM sessions WHERE s_user_id = %s AND s_expires_at < now()',
        (user_id,),
    )
    return token


def get_user(token):
    """Utilisateur de la session, ou None (expirée, inconnue, compte désactivé)."""
    if not token:
        return None
    row = db.fetch_one(
        """
        SELECT u.u_id, u.u_email, r.r_type
        FROM sessions s
        JOIN users u ON u.u_id = s.s_user_id
        JOIN roles r ON r.r_id = u.u_role_id
        WHERE s.s_token = %s
          AND s.s_expires_at > now()
          AND u.u_is_active
        """,
        (_hash(token),),
    )
    if row is None:
        return None
    return {'id': row['u_id'], 'email': row['u_email'], 'role': row['r_type']}


def destroy(token):
    if token:
        db.execute('DELETE FROM sessions WHERE s_token = %s', (_hash(token),))


def set_cookie(token):
    parts = [f'{COOKIE}={token}', 'HttpOnly', 'SameSite=Lax', 'Path=/',
             f'Max-Age={config.SESSION_HOURS * 3600}']
    if config.SECURE_COOKIES:
        parts.append('Secure')
    return ('Set-Cookie', '; '.join(parts))


def clear_cookie():
    parts = [f'{COOKIE}=', 'HttpOnly', 'SameSite=Lax', 'Path=/', 'Max-Age=0']
    if config.SECURE_COOKIES:
        parts.append('Secure')
    return ('Set-Cookie', '; '.join(parts))


def destroy_others(user_id, keep_token):
    db.execute('DELETE FROM sessions WHERE s_user_id = %s AND s_token <> %s',
               (user_id, _hash(keep_token or '')))
