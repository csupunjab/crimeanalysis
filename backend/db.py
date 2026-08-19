import psycopg2
import psycopg2.extras
from contextlib import contextmanager

import config


@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.PG_DATABASE,
    )
    try:
        yield conn
    finally:
        conn.close()


def query(sql, params=None):
    """Run a SELECT and return a list of dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None
