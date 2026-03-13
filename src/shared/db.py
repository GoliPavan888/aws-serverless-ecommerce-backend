from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

from shared.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


DSN = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    conn = psycopg.connect(DSN, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
