import config
from app.web import html_response, redirect, route

DASHBOARDS = {'patient': '/patient', 'medecin': '/medecin',
              'etablissement': '/etablissement', 'admin': '/admin'}

_PLACEHOLDER = ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Olyvera</title>'
                '<link rel="stylesheet" href="/static/style.css">'
                '<body style="font-family:sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem">'
                '<h1>Espace en cours de développement</h1>'
                '<p>Cet espace sera bientôt disponible.</p>'
                '<button id="logout-button">Se déconnecter</button>'
                '<script src="/static/logout.js"></script></body></html>').encode('utf-8')


def _page(name):
    path = config.PUBLIC_DIR / 'html' / name
    if path.is_file() and path.stat().st_size > 0:
        return html_response(path.read_bytes())
    return html_response(_PLACEHOLDER)


@route('GET', '/', page=True)
def home(request):
    user = request.user
    if user:
        return redirect(DASHBOARDS.get(user['role'], '/login'))
    return _page('accueil.html')


@route('GET', '/login', page=True)
def login_page(request):
    return redirect('/') if request.user else _page('login.html')


@route('GET', '/register', page=True)
def register_page(request):
    return redirect('/') if request.user else _page('register.html')


def _dashboard(role):
    name = role + '.html'

    @route('GET', DASHBOARDS[role], roles=(role,), page=True)
    def view(request):
        return _page(name)


for _role in DASHBOARDS:
    _dashboard(_role)


@route('GET', '/health')
def health(request):
    from app.web import json_response
    return json_response({'status': 'ok'})
