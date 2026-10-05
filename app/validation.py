import re

from app.errors import HttpError

_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')
_PHONE = re.compile(r'^\+?[0-9][0-9 .()-]{5,24}$')


def text(value, label, max_len=100, required=True):
    """Chaîne nettoyée ; refuse tout autre type (ex. {"email": 123})."""
    if value is None or value == '':
        if required:
            raise HttpError(400, f'{label} est obligatoire.')
        return None
    if not isinstance(value, str):
        raise HttpError(400, f'{label} est invalide.')
    value = value.strip()
    if not value:
        if required:
            raise HttpError(400, f'{label} est obligatoire.')
        return None
    if len(value) > max_len:
        raise HttpError(400, f'{label} est trop long.')
    return value


def email(value):
    value = text(value, 'L’adresse e-mail', 255).lower()
    if not _EMAIL.match(value):
        raise HttpError(400, 'Adresse e-mail invalide.')
    return value


def phone(value):
    value = text(value, 'Le téléphone', 30)
    if not _PHONE.match(value):
        raise HttpError(400, 'Numéro de téléphone invalide.')
    return re.sub(r'[ .()-]', '', value)


def password(value):
    if not isinstance(value, str) or not value:
        raise HttpError(400, 'Le mot de passe est obligatoire.')
    if len(value) < 8:
        raise HttpError(400, 'Le mot de passe doit contenir au moins 8 caractères.')
    if len(value) > 128:
        raise HttpError(400, 'Le mot de passe est trop long.')
    return value
