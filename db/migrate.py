"""
Database Migration Script.
Applies schema updates (such as adding new columns) to the live PostgreSQL database.
"""
import os
import psycopg2

DB_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/retail_offers")


def run_migrations():
    print(f"Connecting to database at {DB_DSN.split('@')[-1]}...")
    with psycopg2.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            print("Applying migration: Adding image_url column to canonical_products...")
            cur.execute("""
                ALTER TABLE canonical_products 
                ADD COLUMN IF NOT EXISTS image_url TEXT;
            """)
            conn.commit()
            print("Successfully executed migration script.")


if __name__ == "__main__":
    run_migrations()
