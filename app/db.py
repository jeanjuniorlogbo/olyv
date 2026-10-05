"""Accès PostgreSQL : pool de connexions + transactions."""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import config
from app.errors import DatabaseError

_pool = None


def pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            config.DB_DSN,
            min_size=1,
            max_size=10,
            kwargs={'row_factory': dict_row},
            open=True,
        )
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def transaction():
    """Un curseur dans UNE transaction : commit à la sortie, rollback si erreur.

    Les violations d'unicité et de chevauchement sont relayées telles quelles
    (le code métier choisit le message) ; toute autre erreur SQL devient
    DatabaseError.
    """
    try:
        with pool().connection() as conn:
            with conn.cursor() as cur:
                yield cur
    except (psycopg.errors.UniqueViolation, psycopg.errors.ExclusionViolation):
        raise
    except psycopg.Error as error:
        raise DatabaseError(str(error)) from error


def fetch_all(sql, params=None):
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql, params=None):
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=None):
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.rowcount
