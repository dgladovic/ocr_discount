"""
Phase 1 database layer: plain psycopg2, deterministic exact-match
cross-store resolution with image priority handling.
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
        cur.execute("SELECT id FROM retailers WHERE LOWER(code) = LOWER(%s)", (retailer_code.strip(),))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unknown retailer code: {retailer_code}")
        return row[0]


def get_or_create_source_document(conn, retailer_id: str, week_start: str, week_end: str,
                                   file_path: str, page_count: int | None = None) -> str:
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


def is_studio_image(path: str | None) -> bool:
    """Returns True if path is a clean web studio photo rather than a flyer crop."""
    if not path:
        return False
    p = path.lower()
    return "web" in p or p.startswith("http")


def upsert_store_product(conn, retailer_id: str, offer: dict) -> str:
    image_path = offer.get("imageUrl") or offer.get("image_url") or offer.get("cropped_image_path")
    brand = offer.get("brand")
    if brand and str(brand).strip().upper() in ("N/A", "NONE", ""):
        brand = None

    with conn.cursor() as cur:
        # Check existing store product image to prevent overwriting studio photo with flyer crop
        cur.execute(
            "SELECT id, image_url FROM store_products WHERE retailer_id = %s AND store_product_key = %s;",
            (retailer_id, offer["store_product_key"])
        )
        existing = cur.fetchone()
        
        final_image = image_path
        if existing and existing[1]:
            # Keep clean web studio photo if incoming is just a flyer crop
            if is_studio_image(existing[1]) and not is_studio_image(image_path):
                final_image = existing[1]

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
                offer["category"], offer["productType"], brand,
                offer.get("unit_size"), offer.get("unit_measurement"), offer.get("fat_percent"),
                offer.get("organic"), final_image,
            ),
        )
        return cur.fetchone()[0]


def _get_overridden_fields(conn, canonical_id: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT field_name FROM product_overrides WHERE canonical_id = %s", (canonical_id,))
        return {row[0] for row in cur.fetchall()}


def find_canonical_by_attributes(conn, category: str, product_type: str, brand: str | None,
                                unit_size: float | None, unit_measurement: str | None,
                                fat_percent: float | None) -> dict | None:
    """Used by crop_images.py to check if a usable image already exists on disk."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, image_url, is_manually_edited 
            FROM canonical_products
            WHERE category = %s AND product_type = %s
              AND NULLIF(LOWER(TRIM(brand)), '') IS NOT DISTINCT FROM NULLIF(LOWER(TRIM(%s)), '')
              AND unit_size IS NOT DISTINCT FROM %s
              AND NULLIF(LOWER(TRIM(unit_measurement)), '') IS NOT DISTINCT FROM NULLIF(LOWER(TRIM(%s)), '')
              AND fat_percent IS NOT DISTINCT FROM %s
            ORDER BY is_manually_edited DESC, updated_at DESC
            LIMIT 1;
            """,
            (category, product_type, brand, unit_size, unit_measurement, fat_percent)
        )
        row = cur.fetchone()
        if row:
            return {"id": row[0], "image_url": row[1], "is_manually_edited": row[2]}
        return None


def find_or_create_canonical(conn, store_product_id: str, offer: dict) -> str:
    brand = offer.get("brand")
    if brand and str(brand).strip().upper() in ("N/A", "NONE", ""):
        brand = None

    unit_size = offer.get("unit_size")
    product_name = offer["product_name_clean"]

    with conn.cursor() as cur:
        # 1. Check existing manual links
        cur.execute("""
            SELECT canonical_id, match_method 
            FROM store_product_links 
            WHERE store_product_id = %s;
        """, (store_product_id,))
        existing_link = cur.fetchone()
        if existing_link and existing_link[1] in ('manual_merge', 'manual_correction', 'manual'):
            return existing_link[0]

        # 2. MATCHING LOGIC (Protects against NULL black hole):
        # Only match by attribute tuple if BOTH brand and unit_size are explicitly known.
        # If either is NULL, require matching on the exact product name!
        if brand is not None and unit_size is not None:
            query = """
                SELECT id FROM canonical_products
                WHERE category = %s 
                  AND product_type = %s
                  AND NULLIF(LOWER(TRIM(brand)), '') IS NOT DISTINCT FROM NULLIF(LOWER(TRIM(%s)), '')
                  AND unit_size IS NOT DISTINCT FROM %s
                  AND NULLIF(LOWER(TRIM(unit_measurement)), '') IS NOT DISTINCT FROM NULLIF(LOWER(TRIM(%s)), '')
                  AND fat_percent IS NOT DISTINCT FROM %s
                ORDER BY is_manually_edited DESC, updated_at DESC
                LIMIT 1;
            """
            params = (
                offer["category"], offer["productType"], brand,
                unit_size, offer.get("unit_measurement"), offer.get("fat_percent")
            )
        else:
            # Fallback for unbranded or un-sized items: REQUIRE EXACT NAME MATCH
            query = """
                SELECT id FROM canonical_products
                WHERE category = %s 
                  AND product_type = %s
                  AND LOWER(TRIM(display_name)) = LOWER(TRIM(%s))
                ORDER BY is_manually_edited DESC, updated_at DESC
                LIMIT 1;
            """
            params = (offer["category"], offer["productType"], product_name)

        cur.execute(query, params)
        row = cur.fetchone()

        if row:
            canonical_id = row[0]
            _refresh_canonical_fields(conn, canonical_id, offer)
        else:
            image_path = offer.get("imageUrl") or offer.get("image_url") or offer.get("cropped_image_path")
            cur.execute(
                """
                INSERT INTO canonical_products
                    (display_name, category, product_type, brand, unit_size, unit_measurement, fat_percent, organic, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (product_name, offer["category"], offer["productType"], brand,
                 unit_size, offer.get("unit_measurement"), offer.get("fat_percent"),
                 offer.get("organic"), image_path),
            )
            canonical_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO store_product_links (store_product_id, canonical_id, confidence, match_method)
            VALUES (%s, %s, 1.0, 'exact')
            ON CONFLICT (store_product_id) DO UPDATE SET 
                canonical_id = CASE
                    WHEN store_product_links.match_method IN ('manual_merge', 'manual_correction')
                    THEN store_product_links.canonical_id
                    ELSE EXCLUDED.canonical_id
                END
            """,
            (store_product_id, canonical_id),
        )
        return canonical_id


def _refresh_canonical_fields(conn, canonical_id: str, offer: dict):
    with conn.cursor() as cur:
        cur.execute("SELECT is_manually_edited, image_url, display_name FROM canonical_products WHERE id = %s", (canonical_id,))
        row = cur.fetchone()
        if row and row[0]:  # Locked by human override
            return
        existing_image_url = row[1] if row else None
        existing_display_name = row[2] if row else None

    overridden = _get_overridden_fields(conn, canonical_id)
    updates, params = [], []

    # SAFEGUARD: Never overwrite an existing display name!
    if "display_name" not in overridden and not existing_display_name and offer.get("product_name_clean"):
        updates.append("display_name = %s")
        params.append(offer["product_name_clean"])

    if "organic" not in overridden and offer.get("organic") not in (None, "unknown"):
        updates.append("organic = %s")
        params.append(offer["organic"])

    incoming_image = offer.get("imageUrl") or offer.get("image_url") or offer.get("cropped_image_path")
    if "image_url" not in overridden and incoming_image:
        incoming_is_web = is_studio_image(incoming_image)
        existing_is_crop = existing_image_url and ("_p" in existing_image_url)

        # UPGRADE RULE:
        # 1. If canonical currently has NO image -> take it.
        # 2. If canonical has a flyer crop, but incoming is a clean web studio photo -> UPGRADE & OVERWRITE.
        # 3. If canonical already has a web studio photo, but incoming is just a flyer crop -> REJECT (keep studio photo).
        if not existing_image_url or (incoming_is_web and existing_is_crop):
            updates.append("image_url = %s")
            params.append(incoming_image)
        elif not existing_image_url:
            updates.append("image_url = COALESCE(image_url, %s)")
            params.append(incoming_image)

    if not updates:
        return

    updates.append("updated_at = now()")
    params.append(canonical_id)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE canonical_products SET {', '.join(updates)} WHERE id = %s", params)


def insert_price_offer(conn, store_product_id: str, source_document_id: str | None,
                        week_start: str, week_end: str, offer: dict):
    image_path = offer.get("cropped_image_path") or offer.get("imageUrl") or offer.get("image_url")

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
                image_path, offer.get("availabilityDateRange"),
            ),
        )


def log_ingestion_run(conn, retailer_code: str, file_name: str, status: str,
                      page_count: int | None = None, offer_count: int = 0, error_message: str | None = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_logs (retailer_code, file_name, status, page_count, offer_count, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (retailer_code, file_name, status, page_count, offer_count, error_message),
        )