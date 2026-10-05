"""Sécurité : limitation de tentatives, autorisations médicales, journalisation."""
import threading
import time
from collections import deque

from app import db
from app.errors import HttpError


class RateLimiter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = {}
        self._lock = threading.Lock()

    def _queue(self, key, now):
        queue = self._hits.get(key)
        if queue is None:
            return None
        while queue and queue[0] <= now - self.window:
            queue.popleft()
        if not queue:
            del self._hits[key]
            return None
        return queue

    def blocked(self, key):
        with self._lock:
            queue = self._queue(key, time.monotonic())
            return queue is not None and len(queue) >= self.limit

    def hit(self, key):
        with self._lock:
            now = time.monotonic()
            if len(self._hits) > 10000:
                for stale in list(self._hits):
                    self._queue(stale, now)
            self._hits.setdefault(key, deque()).append(now)

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)


def has_permission(user, permission):
    row = db.fetch_one(
        """
        SELECT 1
        FROM role_permissions rp
        JOIN roles r ON r.r_id = rp.rp_role_id
        JOIN permissions p ON p.pm_id = rp.rp_permission_id
        WHERE r.r_type = %s AND p.pm_name = %s
        """,
        (user['role'], permission),
    )
    return row is not None


SCOPES = ('record.read', 'record.write', 'documents.read', 'documents.write')


def can_access(user, patient_id, scope):
    """Règle UNIQUE d'accès aux données médicales.

    - le patient lit ses propres données, ne les écrit jamais ;
    - un médecin vérifié n'accède que sous autorisation active du patient,
      dans les limites de la portée accordée ;
    - une personne de confiance : lecture seule, sous autorisation active ;
    - admin, établissement, lien familial, rendez-vous : aucun accès.
    """
    if scope not in SCOPES:
        return False
    role = user['role']
    is_write = scope.endswith('.write')

    if role == 'patient':
        own = db.fetch_one(
            'SELECT 1 FROM patients WHERE p_id = %s AND p_user_id = %s',
            (patient_id, user['id']),
        )
        if own is not None:
            return not is_write

    if role not in ('patient', 'medecin'):
        return False
    if is_write and role != 'medecin':
        return False

    row = db.fetch_one(
        """
        SELECT 1
        FROM medical_access ma
        LEFT JOIN doctors d ON d.d_user_id = ma.ma_granted_to_user_id
        WHERE ma.ma_patient_id = %s
          AND ma.ma_granted_to_user_id = %s
          AND ma.ma_status = 'active'
          AND ma.ma_start_at <= now()
          AND (ma.ma_end_at IS NULL OR ma.ma_end_at > now())
          AND %s = ANY (ma.ma_scopes)
          AND (%s <> 'medecin' OR (d.d_verification_status AND d.d_is_active))
        """,
        (patient_id, user['id'], scope, role),
    )
    return row is not None


def log_access(request, user_id, patient_id, action, resource,
               resource_id=None, result='allowed'):
    """Écrit dans le journal. Une erreur ici remonte : on ne sert pas sans tracer."""
    db.execute(
        """
        INSERT INTO access_logs (
            alog_user_id, alog_patient_id, alog_action, alog_resource,
            alog_resource_id, alog_result, alog_ip_address, alog_user_agent
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::inet, %s)
        """,
        (user_id, patient_id, action, resource, resource_id, result,
         request.ip, request.user_agent),
    )


def require_access(request, patient_id, scope, resource, resource_id=None):
    """À appeler avant TOUTE lecture/écriture de donnée médicale."""
    user = request.user
    if user is None:
        raise HttpError(401, 'Authentification requise.')
    allowed = can_access(user, patient_id, scope)
    log_access(request, user['id'], patient_id, scope, resource, resource_id,
               'allowed' if allowed else 'denied')
    if not allowed:
        raise HttpError(403, 'Accès non autorisé.')
