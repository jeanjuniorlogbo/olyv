"""Fichiers statiques publics (css, js, images, polices). Jamais de documents médicaux."""
import mimetypes
import re

import config

_DIRS = [config.PUBLIC_DIR / d for d in ('css', 'js', 'images', 'fonts')]
_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
_ALLOWED = {'.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.webp',
            '.svg', '.ico', '.woff', '.woff2'}


def serve_static(filename):
    """(contenu, mime) ou None."""
    if not _NAME.match(filename or ''):
        return None
    if '.' not in filename or '.' + filename.rsplit('.', 1)[1].lower() not in _ALLOWED:
        return None
    for directory in _DIRS:
        base = directory.resolve()
        path = (base / filename).resolve()
        if path.parent == base and path.is_file():
            mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            return path.read_bytes(), mime
    return None
