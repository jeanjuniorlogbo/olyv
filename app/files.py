"""Stockage privé de fichiers (documents médicaux, photos) hors de public/."""
import base64
import binascii
import re
import uuid

import config
from app.errors import HttpError

_MAGIC = ((b'%PDF', 'pdf', 'application/pdf'),
          (b'\x89PNG\r\n\x1a\n', 'png', 'image/png'),
          (b'\xff\xd8\xff', 'jpg', 'image/jpeg'))
_KEY = re.compile(r'^[0-9a-f]{32}\.(pdf|png|jpg)$')
MIME_BY_EXT = {ext: mime for _, ext, mime in _MAGIC}


def decode_upload(content_base64, allowed, max_bytes):
    """Décode et valide (signature réelle du fichier, pas l'extension déclarée)."""
    if not isinstance(content_base64, str) or not content_base64:
        raise HttpError(400, 'Fichier manquant.')
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HttpError(400, 'Fichier invalide.')
    if len(raw) > max_bytes:
        raise HttpError(413, f'Fichier trop volumineux (max {max_bytes // 1000} Ko).')
    for magic, ext, mime in _MAGIC:
        if raw.startswith(magic) and ext in allowed:
            return raw, ext, mime
    raise HttpError(415, 'Format non accepté (' + ', '.join(sorted(allowed)) + ').')


def save(folder, raw, ext):
    directory = config.STORAGE_DIR / folder
    directory.mkdir(parents=True, exist_ok=True)
    key = f'{uuid.uuid4().hex}.{ext}'
    (directory / key).write_bytes(raw)
    return key


def read(folder, key):
    if not _KEY.match(key or ''):
        return None
    path = config.STORAGE_DIR / folder / key
    return path.read_bytes() if path.is_file() else None


def remove(folder, key):
    if _KEY.match(key or ''):
        (config.STORAGE_DIR / folder / key).unlink(missing_ok=True)
