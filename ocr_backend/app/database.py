import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

DB_DSN = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:postgrespassword@db:5432/retail_offers"
)

def fetch_query(query: str, params: tuple = None):
    """Helper function to execute SELECT query and return JSON-serializable dictionaries."""
    try:
        with psycopg2.connect(DB_DSN) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                rows = cur.fetchall()
                return jsonable_encoder(rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))