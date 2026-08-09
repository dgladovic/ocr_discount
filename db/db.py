"""
Phase 1 database layer: plain psycopg2, deterministic exact-match
cross-store resolution (no embeddings / LLM matching yet), and
override-aware writes to canonical_products so manual edits never
get silently clobbered by the next ingestion run.
"""
import os
import psycopg2
from contextlib import contextmanager

DB_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/retail_offers")


@contextmanager
def get_conn():
    conn = psycopg2.connect(DB_DSN)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_retailer_id(conn, retailer_code: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM retailers WHERE code = %s", (retailer_code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unknown retailer code: {retailer_code}")
        return row[0]


def get_or_create_source_document(conn, retailer_id: str, week_start: str, week_end: str,
                                   file_path: str, page_count: int | None = None) -> str:
    """One row per flyer actually ingested -- what price_offers traces back to for debugging."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_documents (retailer_id, week_start, week_end, file_path, page_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (retailer_id, week_end) DO UPDATE SET
                file_path = EXCLUDED.file_path,
                page_count = EXCLUDED.page_count
            RETURNING id
            """,
            (retailer_id, week_start, week_end, file_path, page_count),
        )
        return cur.fetchone()[0]


def upsert_store_product(conn, retailer_id: str, offer: dict) -> str:
    """
    Insert or refresh the per-store product identity. Stable across weeks for
    the same store_product_key (name+size slug -- every retailer now goes
    through the same PDF extraction path, so there's one key strategy).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO store_products
                (retailer_id, store_product_key, product_name_raw, category, product_type,
                 brand, unit_size, unit_measurement, fat_percent, organic, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (retailer_id, store_product_key) DO UPDATE SET
                product_name_raw = EXCLUDED.product_name_raw,
                brand = EXCLUDED.brand,
                unit_size = EXCLUDED.unit_size,
                unit_measurement = EXCLUDED.unit_measurement,
                fat_percent = EXCLUDED.fat_percent,
                organic = EXCLUDED.organic,
                image_url = COALESCE(EXCLUDED.image_url, store_products.image_url),
                last_seen_at = now()
            RETURNING id
            """,
            (
                retailer_id, offer["store_product_key"], offer["product_name_clean"],
                offer["category"], offer["productType"], offer.get("brand"),
                offer.get("unit_size"), offer.get("unit_measurement"), offer.get("fat_percent"),
                offer.get("organic"), offer.get("imageUrl"),
            ),
        )
        return cur.fetchone()[0]


def _get_overridden_fields(conn, canonical_id: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT field_name FROM product_overrides WHERE canonical_id = %s", (canonical_id,))
        return {row[0] for row in cur.fetchall()}


def find_or_create_canonical(conn, store_product_id: str, offer: dict) -> str:
    """
    Phase 1 resolution: deterministic exact match on
    (category, product_type, brand, unit_size, unit_measurement, fat_percent).
    Under-merges rather than over-merges -- safer failure mode to ship with.
    Embedding/LLM matching (phase 2+) only ever *improves* the match rate;
    this function's signature and the store_product_links table don't change.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM canonical_products
            WHERE category = %s AND product_type = %s
              AND brand IS NOT DISTINCT FROM %s
              AND unit_size IS NOT DISTINCT FROM %s
              AND unit_measurement IS NOT DISTINCT FROM %s
              AND fat_percent IS NOT DISTINCT FROM %s
            LIMIT 1
            """,
            (offer["category"], offer["productType"], offer.get("brand"),
             offer.get("unit_size"), offer.get("unit_measurement"), offer.get("fat_percent")),
        )
        row = cur.fetchone()

        if row:
            canonical_id = row[0]
            _refresh_canonical_fields(conn, canonical_id, offer)
        else:
            image_path = offer.get("imageUrl") or offer.get("image_url")
            cur.execute(
                """
                INSERT INTO canonical_products
                    (display_name, category, product_type, brand, unit_size, unit_measurement, fat_percent, organic, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (offer["product_name_clean"], offer["category"], offer["productType"], offer.get("brand"),
                 offer.get("unit_size"), offer.get("unit_measurement"), offer.get("fat_percent"), offer.get("organic"), image_path),
            )
            canonical_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO store_product_links (store_product_id, canonical_id, confidence, match_method)
            VALUES (%s, %s, 1.0, 'exact')
            ON CONFLICT (store_product_id) DO UPDATE SET canonical_id = EXCLUDED.canonical_id
            """,
            (store_product_id, canonical_id),
        )
        return canonical_id


def _refresh_canonical_fields(conn, canonical_id: str, offer: dict):
    """
    Refresh display_name/organic/image_url on an existing canonical product, skipping
    any field a human has manually overridden. Overrides always win over
    automated writes.
    """
    overridden = _get_overridden_fields(conn, canonical_id)
    updates, params = [], []

    if "display_name" not in overridden:
        updates.append("display_name = %s")
        params.append(offer["product_name_clean"])
    if "organic" not in overridden and offer.get("organic") not in (None, "unknown"):
        updates.append("organic = %s")
        params.append(offer["organic"])
    
    image_path = offer.get("imageUrl") or offer.get("image_url")
    if "image_url" not in overridden and image_path:
        # Only set canonical image_url if it's currently NULL
        updates.append("image_url = COALESCE(image_url, %s)")
        params.append(image_path)

    if not updates:
        return
    updates.append("updated_at = now()")
    params.append(canonical_id)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE canonical_products SET {', '.join(updates)} WHERE id = %s", params)


def insert_price_offer(conn, store_product_id: str, source_document_id: str | None,
                        week_start: str, week_end: str, offer: dict):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO price_offers
                (store_product_id, source_document_id, week_start, week_end, current_price, original_price,
                 offer_type, discount_percent, multibuy_required_qty, multibuy_free_qty,
                 base_price, base_price_unit, base_price_source, cropped_image_path, availability_date_range)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (store_product_id, week_start) DO UPDATE SET
                source_document_id = EXCLUDED.source_document_id,
                current_price = EXCLUDED.current_price,
                original_price = EXCLUDED.original_price,
                offer_type = EXCLUDED.offer_type,
                discount_percent = EXCLUDED.discount_percent,
                multibuy_required_qty = EXCLUDED.multibuy_required_qty,
                multibuy_free_qty = EXCLUDED.multibuy_free_qty,
                base_price = EXCLUDED.base_price,
                base_price_unit = EXCLUDED.base_price_unit,
                base_price_source = EXCLUDED.base_price_source,
                cropped_image_path = COALESCE(EXCLUDED.cropped_image_path, price_offers.cropped_image_path),
                availability_date_range = EXCLUDED.availability_date_range
            """,
            (
                store_product_id, source_document_id, week_start, week_end,
                offer["current_price_numeric"], offer.get("original_price_numeric"),
                offer["offerType"], offer.get("discount_percent_numeric"),
                offer.get("multibuy_required_qty"), offer.get("multibuy_free_qty"),
                offer.get("base_price"), offer.get("base_price_unit"), offer.get("base_price_source", "computed"),
                offer.get("imageUrl"), offer.get("availabilityDateRange"),
            ),
        )


def log_ingestion_run(conn, retailer_code: str, file_name: str, status: str,
                      page_count: int | None = None, offer_count: int = 0, error_message: str | None = None):
    """Log an ingestion attempt (success, failure, or partial) to ingestion_logs table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_logs (retailer_code, file_name, status, page_count, offer_count, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (retailer_code, file_name, status, page_count, offer_count, error_message),
        )