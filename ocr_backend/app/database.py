import os
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

DB_DSN = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:postgrespassword@db:5432/retail_offers"
)

# Initialize a thread-safe connection pool (min 1, max 10 connections)
pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DB_DSN)


@contextmanager
def get_db_cursor(commit: bool = False):
    """Context manager providing a RealDictCursor from the connection pool."""
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")
    finally:
        pool.putconn(conn)


def fetch_query(query: str, params: tuple = None):
    """Helper function to execute a SELECT query and return JSON-serializable dictionaries."""
    with get_db_cursor() as cur:
        cur.execute(query, params or ())
        rows = cur.fetchall()
        return jsonable_encoder(rows)