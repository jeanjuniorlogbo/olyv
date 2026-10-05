"""Noyau HTTP : requête, réponse, routeur à décorateurs, erreurs, en-têtes de sécurité."""
import ipaddress
import json
import logging
import re
from datetime import date, datetime, time
from decimal import Decimal
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs, urlparse

import config
from app import sessions
from app.errors import DatabaseError, HttpError
from app.static import serve_static

log = logging.getLogger('Olyvera')

JSON = 'application/json; charset=utf-8'
HTML = 'text/html; charset=utf-8'
MAX_BODY = 1_000_000
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
ROUTES = {}         
PATTERNS = []        
_UNSET = object()

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def client_ip(environ):
    candidate = environ.get('REMOTE_ADDR')
    if config.TRUST_PROXY:
        forwarded = environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        candidate = forwarded or candidate
    try:
        return str(ipaddress.ip_address(candidate))
    except (ValueError, TypeError):
        return None


class Request:
    def __init__(self, environ):
        self.environ = environ
        self.method = environ.get('REQUEST_METHOD', 'GET').upper()
        self.path = environ.get('PATH_INFO', '/') or '/'
        self.ip = client_ip(environ)
        self.user_agent = environ.get('HTTP_USER_AGENT', '')[:500]
        self._user = _UNSET
        self._json = _UNSET
        self.params = {}
        query = parse_qs(environ.get('QUERY_STRING', ''), keep_blank_values=False)
        self.query = {k: v[0] for k, v in query.items()}

    @property
    def token(self):
        try:
            cookie = SimpleCookie(self.environ.get('HTTP_COOKIE', ''))
        except CookieError:
            return None
        morsel = cookie.get(sessions.COOKIE)
        return morsel.value if morsel else None

    @property
    def user(self):
        if self._user is _UNSET:
            self._user = sessions.get_user(self.token)
        return self._user

    def json(self, limit=MAX_BODY):
        if self._json is _UNSET:
            if not self.environ.get('CONTENT_TYPE', '').startswith('application/json'):
                raise HttpError(415, 'Content-Type application/json requis.')
            try:
                length = int(self.environ.get('CONTENT_LENGTH') or 0)
            except ValueError:
                length = 0
            if length <= 0:
                raise HttpError(400, 'Aucune donnée reçue.')
            if length > limit:
                raise HttpError(413, 'Requête trop volumineuse.')
            try:
                data = json.loads(self.environ['wsgi.input'].read(length).decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                raise HttpError(400, 'Données JSON invalides.')
            if not isinstance(data, dict):
                raise HttpError(400, 'Format de données invalide.')
            self._json = data
        return self._json


class Response:
    def __init__(self, body=b'', status=200, content_type=HTML, headers=None):
        self.body = body
        self.status = status
        self.content_type = content_type
        self.headers = list(headers or [])


def _encode(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'value') and hasattr(value, 'name'):     
        return value.value
    return str(value)                                          


def json_response(data, status=200, headers=None):
    body = json.dumps(data, default=_encode, ensure_ascii=False).encode('utf-8')
    return Response(body, status, JSON, headers)


def html_response(body, status=200):
    return Response(body, status, HTML)


def redirect(location, headers=None):
    return Response(b'', 302, HTML, [('Location', location)] + list(headers or []))


def route(method, path, roles=None, page=False):
    """roles=None : public · roles=() : tout utilisateur connecté · roles=('patient',) : ces rôles.

    page=True : redirection vers /login au lieu d'une erreur JSON 401/403.
    """
    def decorator(function):
        entry = (function, roles, page)
        if '{' in path:
            regex = re.sub(r'\{(\w+):w\}', r'(?P<\1>[A-Za-z0-9._-]+)', path)
            regex = re.sub(r'\{(\w+)\}', r'(?P<\1>[0-9]{1,9})', regex)
            PATTERNS.append((method, re.compile('^' + regex + '$'), path, entry))
        else:
            ROUTES[(method, path)] = entry
        return function
    return decorator


def _same_origin(request):
    origin = request.environ.get('HTTP_ORIGIN')
    if not origin:
        return True
    return urlparse(origin).netloc == request.environ.get('HTTP_HOST')


def _dispatch(request):
    entry = ROUTES.get((request.method, request.path))
    if entry is None:
        for method, regex, _, candidate in PATTERNS:
            found = regex.match(request.path)
            if found and method == request.method:
                request.params = {k: int(v) if v.isdigit() else v for k, v in found.groupdict().items()}
                entry = candidate
                break

    if entry is None:
        if request.method == 'GET' and request.path.startswith('/static/'):
            found = serve_static(request.path[len('/static/'):])
            if found is None:
                raise HttpError(404, 'Ressource introuvable.')
            return Response(found[0], 200, found[1], [('Cache-Control', 'public, max-age=300')])
        known = any(p == request.path for (_, p) in ROUTES) or any(
            regex.match(request.path) for _, regex, _, _ in PATTERNS)
        if known:
            raise HttpError(405, 'Méthode non autorisée.')
        raise HttpError(404, 'Page introuvable.')

    if request.method in UNSAFE_METHODS and not _same_origin(request):
        raise HttpError(403, 'Origine de la requête refusée.')

    function, roles, page = entry
    if roles is not None:
        user = request.user
        if user is None:
            if page:
                return redirect('/login')
            raise HttpError(401, 'Authentification requise.')
        if roles and user['role'] not in roles:
            if page:
                return redirect('/')
            raise HttpError(403, 'Accès interdit.')
    return function(request)


def _error_response(request, status, message):
    wants_json = (request.path.startswith('/api/') or request.method != 'GET'
                  or 'application/json' in request.environ.get('HTTP_ACCEPT', ''))
    if wants_json:
        return json_response({'success': False, 'message': message}, status)
    body = f'<h1>{status} — {message}</h1><p><a href="/">Retour à l’accueil</a></p>'
    return html_response(body.encode('utf-8'), status)


def _add_security_headers(response, request):
    names = {name.lower() for name, _ in response.headers}
    extra = [
        ('X-Content-Type-Options', 'nosniff'),
        ('X-Frame-Options', 'DENY'),
        ('Referrer-Policy', 'same-origin'),
        ('Permissions-Policy', 'camera=(), microphone=(), geolocation=()'),
        ('Content-Security-Policy', CSP),
    ]
    if config.SECURE_COOKIES:
        extra.append(('Strict-Transport-Security', 'max-age=31536000; includeSubDomains'))
    if 'cache-control' not in names:
        extra.append(('Cache-Control', 'no-store'))
    response.headers.extend(extra)


def application(environ, start_response):
    request = Request(environ)
    try:
        response = _dispatch(request)
    except HttpError as error:
        response = _error_response(request, error.status, error.message)
    except DatabaseError:
        log.exception('Erreur base de données : %s %s', request.method, request.path)
        response = _error_response(request, 503, 'Service momentanément indisponible.')
    except Exception:
        log.exception('Erreur non gérée : %s %s', request.method, request.path)
        response = _error_response(request, 500, 'Erreur interne du serveur.')

    _add_security_headers(response, request)
    status_line = f'{response.status} {HTTPStatus(response.status).phrase}'
    headers = [('Content-Type', response.content_type),
               ('Content-Length', str(len(response.body)))] + response.headers
    start_response(status_line, headers)
    return [response.body]
