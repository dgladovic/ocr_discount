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
            print("Applying migration: Creating ingestion_logs table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    retailer_code TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INT,
                    offer_count INT DEFAULT 0,
                    error_message TEXT,
                    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            conn.commit()
            print("Successfully executed migration script.")


if __name__ == "__main__":
    run_migrations()
