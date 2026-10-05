"""Inscription et authentification (Argon2)."""
import secrets
import string

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

try:
    from argon2.exceptions import InvalidHashError
except ImportError:
    InvalidHashError = VerificationError

from app import db
from app.errors import HttpError

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash('mot-de-passe-factice-pour-egaliser-les-temps')


def _verify(password_hash, password):
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def hash_password(password):
    return _hasher.hash(password)


def register_patient(last_name, first_name, email, phone, password):
    """Crée compte + fiche patient + dossier médical vide, en UNE transaction."""
    password_hash = hash_password(password)
    try:
        with db.transaction() as cur:
            cur.execute("SELECT r_id FROM roles WHERE r_type = 'patient'")
            role_id = cur.fetchone()['r_id']

            cur.execute(
                """
                INSERT INTO users (u_email, u_phone, u_password, u_role_id)
                VALUES (%s, %s, %s, %s) RETURNING u_id
                """,
                (email, phone, password_hash, role_id),
            )
            user_id = cur.fetchone()['u_id']

            cur.execute(
                """
                INSERT INTO patients (p_user_id, p_first_name, p_last_name)
                VALUES (%s, %s, %s) RETURNING p_id
                """,
                (user_id, first_name, last_name),
            )
            patient_id = cur.fetchone()['p_id']

            cur.execute('INSERT INTO medical_records (mr_patient_id) VALUES (%s)', (patient_id,))
            cur.execute(
                """
                INSERT INTO notifications (n_user_id, n_type, n_title, n_message)
                VALUES (%s, 'system', 'Bienvenue sur Olyvera',
                        'Votre espace personnel est prêt.')
                """,
                (user_id,),
            )
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, 'Cet e-mail ou ce numéro de téléphone est déjà utilisé.')
    return {'user_id': user_id, 'patient_id': patient_id}


def authenticate(email, password):
    """Utilisateur {id, email} ou None. Même coût de calcul si l'e-mail est inconnu."""
    row = db.fetch_one(
        """
        SELECT u.u_id, u.u_email, u.u_password, u.u_is_active, r.r_type
        FROM users u
        JOIN roles r ON r.r_id = u.u_role_id
        WHERE lower(u.u_email) = %s
        """,
        (email,),
    )
    if row is None:
        _verify(_DUMMY_HASH, password)
        return None
    if not _verify(row['u_password'], password) or not row['u_is_active']:
        return None
    if _hasher.check_needs_rehash(row['u_password']):
        db.execute('UPDATE users SET u_password = %s WHERE u_id = %s',
                   (hash_password(password), row['u_id']))
    db.execute('UPDATE users SET u_last_login_at = now() WHERE u_id = %s', (row['u_id'],))
    return {'id': row['u_id'], 'email': row['u_email'], 'role': row['r_type']}


def check_password(user_id, password):
    row = db.fetch_one('SELECT u_password FROM users WHERE u_id = %s', (user_id,))
    return row is not None and _verify(row['u_password'], password)


def set_password(user_id, new_password):
    db.execute('UPDATE users SET u_password = %s WHERE u_id = %s',
               (hash_password(new_password), user_id))


_TAKEN = 'Cet e-mail, ce numéro ou cet identifiant est déjà utilisé.'


def _insert_user(cur, role, email, phone, password_hash):
    cur.execute("SELECT r_id FROM roles WHERE r_type = %s", (role,))
    role_id = cur.fetchone()['r_id']
    cur.execute(
        """INSERT INTO users (u_email, u_phone, u_password, u_role_id)
           VALUES (%s, %s, %s, %s) RETURNING u_id""", (email, phone, password_hash, role_id))
    return cur.fetchone()['u_id']


_PASSWORD_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits


def generate_password(length=12):
    """Mot de passe aléatoire affiché une seule fois à l'administrateur."""
    return ''.join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def admin_create_doctor(last_name, first_name, email, phone, professional_id, specialty,
                        password=None):
    """Crée un compte médecin, déjà vérifié : seul un administrateur peut appeler ceci.

    Si `password` n'est pas fourni, un mot de passe est généré et renvoyé en clair
    (une seule fois) pour que l'administrateur le communique au titulaire du compte.
    """
    generated = password is None
    password = password or generate_password()
    password_hash = hash_password(password)
    try:
        with db.transaction() as cur:
            user_id = _insert_user(cur, 'medecin', email, phone, password_hash)
            cur.execute(
                """INSERT INTO doctors (d_user_id, d_first_name, d_last_name,
                                        d_professional_id, d_specialty,
                                        d_verification_status, d_is_active)
                   VALUES (%s, %s, %s, %s, %s, true, true)""",
                (user_id, first_name, last_name, professional_id, specialty))
            cur.execute(
                """INSERT INTO notifications (n_user_id, n_type, n_title, n_message)
                   VALUES (%s, 'system', 'Bienvenue sur Olyvera',
                           'Votre compte médecin a été créé par un administrateur et est actif.')""",
                (user_id,))
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, _TAKEN)
    return {'user_id': user_id, 'password': password if generated else None}


def admin_create_facility(name, ftype, email, phone, address, city, country, password=None):
    """Crée un compte établissement, déjà vérifié : seul un administrateur peut appeler ceci."""
    generated = password is None
    password = password or generate_password()
    password_hash = hash_password(password)
    try:
        with db.transaction() as cur:
            user_id = _insert_user(cur, 'etablissement', email, phone, password_hash)
            cur.execute(
                """INSERT INTO health_facilities (hf_user_id, hf_name, hf_type, hf_phone, hf_email,
                                                  hf_address, hf_city, hf_country,
                                                  hf_verification_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)""",
                (user_id, name, ftype, phone, email, address, city, country))
            cur.execute(
                """INSERT INTO notifications (n_user_id, n_type, n_title, n_message)
                   VALUES (%s, 'system', 'Bienvenue sur Olyvera',
                           'Votre compte établissement a été créé par un administrateur et est actif.')""",
                (user_id,))
    except psycopg.errors.UniqueViolation:
        raise HttpError(409, _TAKEN)
    return {'user_id': user_id, 'password': password if generated else None}


def admin_reset_password(user_id, password=None):
    """Réinitialise le mot de passe d'un compte (médecin, établissement, patient…).

    Renvoie le mot de passe en clair quand il a été généré automatiquement, pour que
    l'administrateur le communique au titulaire. Les sessions existantes sont fermées.
    """
    generated = password is None
    password = password or generate_password()
    with db.transaction() as cur:
        cur.execute('UPDATE users SET u_password = %s WHERE u_id = %s RETURNING u_id',
                   (hash_password(password), user_id))
        if cur.fetchone() is None:
            raise HttpError(404, 'Utilisateur introuvable.')
        cur.execute('DELETE FROM sessions WHERE s_user_id = %s', (user_id,))
        cur.execute(
            """INSERT INTO notifications (n_user_id, n_type, n_title, n_message)
               VALUES (%s, 'system', 'Mot de passe réinitialisé',
                       'Votre mot de passe a été réinitialisé par un administrateur.')""",
            (user_id,))
    return password if generated else None
