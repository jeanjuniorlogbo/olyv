class HttpError(Exception):
    """Erreur destinée au client : statut HTTP + message lisible."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class DatabaseError(Exception):
    """Erreur base de données (détails uniquement dans les logs)."""
