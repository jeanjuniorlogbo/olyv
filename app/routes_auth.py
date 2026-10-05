from app import auth, sessions, validation
from app.errors import HttpError
from app.security import RateLimiter, log_access
from app.common import setting
from app.web import json_response, route

_login_by_account = RateLimiter(limit=5, window_seconds=15 * 60)
_login_by_ip = RateLimiter(limit=30, window_seconds=15 * 60)
_register_by_ip = RateLimiter(limit=10, window_seconds=60 * 60)


def _register_guard(request):
    if setting('registration_open', '1') != '1':
        raise HttpError(403, 'Les inscriptions sont temporairement fermées.')
    ip_key = request.ip or 'inconnue'
    if _register_by_ip.blocked(ip_key):
        raise HttpError(429, 'Trop de tentatives. Réessayez plus tard.')
    _register_by_ip.hit(ip_key)
    return request.json()


def _account_fields(data):
    email = validation.email(data.get('email'))
    phone = validation.phone(data.get('phone'))
    password = validation.password(data.get('password'))
    if password != data.get('password_confirmation'):
        raise HttpError(400, 'Les mots de passe ne correspondent pas.')
    if data.get('terms') is not True:
        raise HttpError(400, 'Vous devez accepter les conditions d’utilisation.')
    return email, phone, password


@route('POST', '/register')
def register(request):
    data = _register_guard(request)
    last_name = validation.text(data.get('last_name'), 'Le nom')
    first_name = validation.text(data.get('first_name'), 'Le prénom')
    email, phone, password = _account_fields(data)

    created = auth.register_patient(last_name, first_name, email, phone, password)
    log_access(request, created['user_id'], created['patient_id'],
               'account.register', 'user', created['user_id'])
    return json_response({'success': True, 'message': 'Compte créé avec succès.',
                          'redirect': '/login'}, 201)


@route('POST', '/login')
def login(request):
    data = request.json()
    email = validation.text(data.get('email'), 'L’adresse e-mail', 255)
    password = data.get('password')
    if not isinstance(password, str) or not password or len(password) > 128:
        raise HttpError(400, 'Tous les champs sont obligatoires.')

    email = email.lower()
    ip_key = request.ip or 'inconnue'
    account_key = f'{ip_key}|{email}'
    if _login_by_account.blocked(account_key) or _login_by_ip.blocked(ip_key):
        raise HttpError(429, 'Trop de tentatives. Réessayez dans quelques minutes.')

    user = auth.authenticate(email, password)
    if user is None:
        _login_by_account.hit(account_key)
        _login_by_ip.hit(ip_key)
        log_access(request, None, None, 'login', 'session', None, 'denied')
        raise HttpError(401, 'Identifiants incorrects.')

    _login_by_account.reset(account_key)
    token = sessions.create(user['id'])
    log_access(request, user['id'], None, 'login', 'session', None, 'allowed')
    return json_response({'success': True, 'message': 'Connexion réussie.', 'redirect': '/'},
                         headers=[sessions.set_cookie(token)])


@route('POST', '/logout')
def logout(request):
    sessions.destroy(request.token)
    return json_response({'success': True, 'message': 'Déconnexion réussie.',
                          'redirect': '/login'}, headers=[sessions.clear_cookie()])


@route('GET', '/api/me', roles=())
def me(request):
    return json_response({'success': True, 'data': request.user})
