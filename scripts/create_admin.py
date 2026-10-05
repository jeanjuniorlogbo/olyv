"""Crée un compte administrateur :  python -m scripts.create_admin"""
import getpass
import sys

import psycopg

from app import auth, db, validation
from app.errors import HttpError


def main():
    try:
        email = validation.email(input('E-mail : '))
        phone = validation.phone(input('Téléphone : '))
        password = validation.password(getpass.getpass('Mot de passe (12+ conseillé) : '))
        if password != getpass.getpass('Confirmation : '):
            sys.exit('Les mots de passe ne correspondent pas.')
    except HttpError as error:
        sys.exit(error.message)

    try:
        db.execute(
            """
            INSERT INTO users (u_email, u_phone, u_password, u_role_id)
            SELECT %s, %s, %s, r_id FROM roles WHERE r_type = 'admin'
            """,
            (email, phone, auth.hash_password(password)),
        )
    except psycopg.errors.UniqueViolation:
        sys.exit('E-mail ou téléphone déjà utilisé.')
    print('Administrateur créé.')


if __name__ == '__main__':
    main()
