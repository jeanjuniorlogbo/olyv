"""Configuration : tout vient de l'environnement (fichier .env à la racine)."""
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def _required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'Variable d’environnement manquante : {name}')
    return value


def _flag(name):
    return os.getenv(name, '0') == '1'


DB_DSN = make_conninfo(
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', '5432'),
    dbname=_required('DB_NAME'),
    user=_required('DB_USER'),
    password=_required('DB_PASS'),
)

SECURE_COOKIES = _flag('SECURE_COOKIES')
TRUST_PROXY = _flag('TRUST_PROXY')
SESSION_HOURS = 12
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '7171'))
PUBLIC_DIR = BASE_DIR / 'public'

TIMEZONE = ZoneInfo(os.getenv('TIMEZONE', 'Africa/Porto-Novo'))
STORAGE_DIR = BASE_DIR / 'storage'


def now_local():
    """Heure locale (naïve) du pays de la plateforme."""
    return datetime.now(TIMEZONE).replace(tzinfo=None)
