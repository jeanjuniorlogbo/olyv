"""Fonctions communes à tous les rôles : notifications, mot de passe, photo, signalements, documents."""
from app import auth, db, files, sessions, validation
from app.common import int_id, notifications_for, ok
from app.errors import HttpError
from app.security import RateLimiter, log_access, require_access
from app.web import Response, route

_password_attempts = RateLimiter(limit=5, window_seconds=15 * 60)


@route('GET', '/api/notifications', roles=())
def list_notifications(request):
    return ok(notifications_for(request.user['id'], 100))


@route('POST', '/api/notifications/read', roles=())
def read_notifications(request):
    data = request.json()
    uid = request.user['id']
    if data.get('all') is True:
        db.execute('UPDATE notifications SET n_is_read = true, n_read_at = now() '
                   'WHERE n_user_id = %s AND NOT n_is_read', (uid,))
    else:
        db.execute('UPDATE notifications SET n_is_read = true, n_read_at = now() '
                   'WHERE n_id = %s AND n_user_id = %s AND NOT n_is_read',
                   (int_id(data.get('id'), 'La notification'), uid))
    return ok(message='Notifications mises à jour.')


@route('POST', '/api/account/password', roles=())
def change_password(request):
    uid = request.user['id']
    if _password_attempts.blocked(str(uid)):
        raise HttpError(429, 'Trop de tentatives. Réessayez plus tard.')
    data = request.json()
    current, new = data.get('current_password'), validation.password(data.get('new_password'))
    if new != data.get('new_password_confirmation'):
        raise HttpError(400, 'Les mots de passe ne correspondent pas.')
    if not isinstance(current, str) or not auth.check_password(uid, current):
        _password_attempts.hit(str(uid))
        raise HttpError(403, 'Mot de passe actuel incorrect.')
    auth.set_password(uid, new)
    sessions.destroy_others(uid, request.token)          # déconnecte les autres appareils
    log_access(request, uid, None, 'account.password_change', 'user', uid)
    return ok(message='Mot de passe modifié. Les autres appareils ont été déconnectés.')


_PHOTO_COLUMNS = {
    'patient': ('patients', 'p_profile_photo_url', 'p_user_id'),
    'medecin': ('doctors', 'd_profile_photo_url', 'd_user_id'),
    'etablissement': ('health_facilities', 'hf_logo_url', 'hf_user_id'),
}


@route('POST', '/api/account/photo', roles=('patient', 'medecin', 'etablissement'))
def upload_photo(request):
    table, column, owner = _PHOTO_COLUMNS[request.user['role']]
    raw, ext, _ = files.decode_upload(request.json(limit=700_000).get('content_base64'),
                                      {'png', 'jpg'}, 400_000)
    key = files.save('photos', raw, ext)
    old = db.fetch_one(f'SELECT {column} AS url FROM {table} WHERE {owner} = %s', (request.user['id'],))
    db.execute(f'UPDATE {table} SET {column} = %s WHERE {owner} = %s',
               (f'/api/photos/{key}', request.user['id']))
    if old and old['url'] and old['url'].startswith('/api/photos/'):
        files.remove('photos', old['url'].rsplit('/', 1)[1])
    return ok({'url': f'/api/photos/{key}'}, 'Photo mise à jour.')


@route('GET', '/api/photos/{key:w}', roles=())
def get_photo(request):
    key = request.params['key']
    raw = files.read('photos', key)
    if raw is None:
        raise HttpError(404, 'Photo introuvable.')
    return Response(raw, 200, files.MIME_BY_EXT[key.rsplit('.', 1)[1]],
                    [('Cache-Control', 'private, max-age=300')])


@route('POST', '/api/reports', roles=())
def create_report(request):
    data = request.json()
    reported = data.get('reported_user_id')
    if reported is not None:
        reported = int_id(reported, 'L’utilisateur signalé')
        if db.fetch_one('SELECT 1 FROM users WHERE u_id = %s', (reported,)) is None:
            raise HttpError(404, 'Utilisateur introuvable.')
    db.execute(
        """INSERT INTO reports (rp_reporter_user_id, rp_reported_user_id, rp_subject, rp_description)
           VALUES (%s, %s, %s, %s)""",
        (request.user['id'], reported, validation.text(data.get('subject'), 'Le sujet', 255),
         validation.text(data.get('description'), 'La description', 5000)))
    return ok(message='Signalement envoyé à l’équipe Olyvera.', status=201)


@route('GET', '/api/documents/{doc_id}/download', roles=('patient', 'medecin'))
def download_document(request):
    doc = db.fetch_one(
        """SELECT md_id, md_patient_id, md_storage_key, md_file_name, md_mime_type
           FROM medical_documents WHERE md_id = %s""", (request.params['doc_id'],))
    if doc is None:
        raise HttpError(404, 'Document introuvable.')
    require_access(request, doc['md_patient_id'], 'documents.read', 'document', doc['md_id'])
    raw = files.read('documents', doc['md_storage_key'])
    if raw is None:
        raise HttpError(404, 'Fichier introuvable.')
    ext = doc['md_storage_key'].rsplit('.', 1)[1]
    name = ''.join(c for c in (doc['md_file_name'] or f'document.{ext}') if c.isalnum() or c in '._- ')
    return Response(raw, 200, doc['md_mime_type'] or files.MIME_BY_EXT[ext],
                    [('Content-Disposition', f'attachment; filename="{name}"')])
