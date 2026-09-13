import re
import os
import psycopg2
from pydantic import BaseModel
from fastapi import APIRouter, Query, HTTPException
from app.database import fetch_query

router = APIRouter(tags=["Canonical Products"])

class ProductOverrideSchema(BaseModel):
    display_name: str | None = None
    category: str | None = None
    product_type: str | None = None
    brand: str | None = None
    unit_size: float | None = None
    unit_measurement: str | None = None
    fat_percent: float | None = None
    organic: str | None = None
    image_url: str | None = None
    edited_by: str = "admin@retailoffers.com"

@router.post("/canonical-products/{canonical_id}/override")
def create_product_override(canonical_id: str, payload: ProductOverrideSchema):
    """Create/update overrides for a canonical product and lock it from AI pipeline updates."""
    edited_by = payload.edited_by or "admin@retailoffers.com"
    
    field_values = {
        "display_name": payload.display_name,
        "category": payload.category,
        "product_type": payload.product_type,
        "brand": payload.brand,
        "unit_size": payload.unit_size,
        "unit_measurement": payload.unit_measurement,
        "fat_percent": payload.fat_percent,
        "organic": payload.organic,
        "image_url": payload.image_url,
    }

    active_edits = {k: v for k, v in field_values.items() if v is not None}
    if not active_edits:
        raise HTTPException(status_code=400, detail="No fields provided to override")

    try:
        with psycopg2.connect(DB_DSN) as conn:
            with conn.cursor() as cur:
                # 1. Upsert into product_overrides table
                for field, val in active_edits.items():
                    cur.execute(
                        """
                        INSERT INTO product_overrides (canonical_id, field_name, override_value, edited_by, edited_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (canonical_id, field_name)
                        DO UPDATE SET override_value = EXCLUDED.override_value,
                                      edited_by = EXCLUDED.edited_by,
                                      edited_at = NOW();
                        """,
                        (canonical_id, field, str(val), edited_by)
                    )
                
                # 2. Update canonical_products table directly & lock product (is_manually_edited = true)
                set_clauses = [f"{field} = %s" for field in active_edits.keys()]
                set_clauses.append("is_manually_edited = true")
                set_clauses.append("updated_at = NOW()")
                
                update_sql = f"UPDATE canonical_products SET {', '.join(set_clauses)} WHERE id = %s;"
                params = list(active_edits.values()) + [canonical_id]
                cur.execute(update_sql, tuple(params))
                conn.commit()

        return {"status": "success", "message": f"Updated {len(active_edits)} field(s) for canonical product {canonical_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply override: {e}")


@router.delete("/canonical-products/{canonical_id}/override")
def revert_product_override(canonical_id: str):
    """Delete all overrides for a canonical product and unlock it for AI pipeline management."""
    try:
        with psycopg2.connect(DB_DSN) as conn:
            with conn.cursor() as cur:
                # 1. Delete override records
                cur.execute("DELETE FROM product_overrides WHERE canonical_id = %s;", (canonical_id,))
                
                # 2. Unlock product (is_manually_edited = false)
                cur.execute(
                    "UPDATE canonical_products SET is_manually_edited = false, updated_at = NOW() WHERE id = %s;",
                    (canonical_id,)
                )
                conn.commit()

        return {"status": "success", "message": f"Reverted overrides for canonical product {canonical_id}. AI management unlocked."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revert override: {e}")

@router.get("/canonical-brands")
def get_canonical_brands(
    category: str | None = None,
    retailer_code: str | None = None,
    search: str | None = None
):
    """
    Fetch distinct brand names dynamically filtered by category, 
    retailer code, or search term for cascading filter dropdowns.
    """
    where_clauses = ["cp.brand IS NOT NULL", "cp.brand != 'N/A'", "cp.brand != ''"]
    params = []

    # Filter available brands by Category
    if category and category.strip():
        where_clauses.append("cp.category = %s")
        params.append(category.strip())

    # Filter available brands by Search Term
    if search and search.strip():
        where_clauses.append("(cp.display_name ILIKE %s OR cp.brand ILIKE %s)")
        search_param = f"%{search.strip()}%"
        params.extend([search_param, search_param])

    # Filter available brands by Retailer
    if retailer_code and retailer_code.strip():
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM store_product_links spl
                JOIN store_products sp ON spl.store_product_id = sp.id
                JOIN retailers r ON sp.retailer_id = r.id
                WHERE spl.canonical_id = cp.id AND LOWER(r.code) = %s
            )
        """)
        params.append(retailer_code.strip().lower())

    where_sql = " WHERE " + " AND ".join(where_clauses)
    query = f"""
        SELECT DISTINCT cp.brand 
        FROM canonical_products cp
        {where_sql}
        ORDER BY cp.brand ASC;
    """
    rows = fetch_query(query, tuple(params))
    return [r["brand"] for r in rows if r.get("brand")]


@router.get("/canonical-products")
def get_canonical_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    retailer_code: str | None = None,
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc")
):
    """
    Fetch canonical products with server-side pagination, fuzzy search, 
    category, brand & retailer filters, and dynamic sorting.
    """
    allowed_sort_fields = {
        "updated_at": "cp.updated_at",
        "display_name": "cp.display_name",
        "brand": "cp.brand",
        "category": "cp.category"
    }
    order_field = allowed_sort_fields.get(sort_by, "cp.updated_at")
    order_direction = "ASC" if sort_order.lower() == "asc" else "DESC"

    where_clauses = []
    params = []

    if search and search.strip():
        where_clauses.append("(cp.display_name ILIKE %s OR cp.brand ILIKE %s)")
        search_param = f"%{search.strip()}%"
        params.extend([search_param, search_param])

    if category and category.strip():
        where_clauses.append("cp.category = %s")
        params.append(category.strip())

    if brand and brand.strip():
        where_clauses.append("cp.brand = %s")
        params.append(brand.strip())

    if retailer_code and retailer_code.strip():
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM store_product_links spl
                JOIN store_products sp ON spl.store_product_id = sp.id
                JOIN retailers r ON sp.retailer_id = r.id
                WHERE spl.canonical_id = cp.id AND LOWER(r.code) = %s
            )
        """)
        params.append(retailer_code.strip().lower())

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_query = f"SELECT COUNT(DISTINCT cp.id) AS total FROM canonical_products cp {where_sql};"
    
    data_query = f"""
        SELECT DISTINCT cp.id, cp.display_name, cp.category, cp.product_type, cp.brand, 
                        cp.unit_size, cp.unit_measurement, cp.fat_percent, cp.organic, 
                        cp.image_url, cp.is_manually_edited, cp.updated_at 
        FROM canonical_products cp
        {where_sql}
        ORDER BY {order_field} {order_direction} 
        LIMIT %s OFFSET %s;
    """

    count_res = fetch_query(count_query, tuple(params))
    total_count = count_res[0]["total"] if count_res else 0

    data_params = tuple(params + [limit, offset])
    items = fetch_query(data_query, data_params)

    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


def extract_flyer_info(cropped_image_path: str | None, pdf_file_path: str | None, retailer_code: str = "", week_end: str = ""):
    page_num = None
    pdf_url = None

    if cropped_image_path:
        match = re.search(r'_p(\d+)_', cropped_image_path)
        if match:
            page_num = int(match.group(1))

    filename = None
    if pdf_file_path:
        filename = os.path.basename(pdf_file_path.replace("\\", "/"))
    elif retailer_code and week_end:
        import glob
        matches = glob.glob(f"downloads/{retailer_code}_{week_end}_*.pdf")
        if matches:
            filename = os.path.basename(matches[0])

    if filename:
        pdf_url = f"downloads/{filename}"
        if page_num:
            pdf_url += f"#page={page_num}"

    return page_num, pdf_url


@router.get("/canonical-products/{canonical_id}/details")
def get_canonical_product_details(canonical_id: str):
    can_query = """
        SELECT id, display_name, category, product_type, brand, unit_size, 
               unit_measurement, fat_percent, organic, image_url, is_manually_edited, updated_at
        FROM canonical_products
        WHERE id = %s;
    """
    can_rows = fetch_query(can_query, (canonical_id,))
    if not can_rows:
        raise HTTPException(status_code=404, detail="Canonical product not found")
    canonical = can_rows[0]

    history_query = """
        SELECT 
            po.id AS offer_id,
            po.week_start,
            po.week_end,
            po.current_price,
            po.original_price,
            po.offer_type,
            po.discount_percent,
            po.multibuy_required_qty,
            po.multibuy_free_qty,
            po.base_price,
            po.base_price_unit,
            po.cropped_image_path,
            po.availability_date_range,
            sd.file_path AS pdf_file_path,
            sp.id AS store_product_id,
            sp.product_name_raw,
            sp.image_url AS store_product_image_url,
            r.id AS retailer_id,
            r.name AS retailer_name,
            r.code AS retailer_code
        FROM store_product_links spl
        JOIN store_products sp ON spl.store_product_id = sp.id
        JOIN retailers r ON sp.retailer_id = r.id
        JOIN price_offers po ON po.store_product_id = sp.id
        LEFT JOIN source_documents sd ON po.source_document_id = sd.id
        WHERE spl.canonical_id = %s
        ORDER BY po.week_start DESC, r.name ASC;
    """
    history = fetch_query(history_query, (canonical_id,))

    # Enrich each offer with PDF deep-link
    for item in history:
        pnum, purl = extract_flyer_info(
            item.get("cropped_image_path"),
            item.get("pdf_file_path"),
            item.get("retailer_code", ""),
            str(item.get("week_end", ""))
        )
        item["flyer_page_number"] = pnum
        item["flyer_pdf_url"] = purl

    active_offers = {}
    for offer in history:
        rcode = offer["retailer_code"]
        if rcode not in active_offers:
            active_offers[rcode] = offer

    return {
        "canonical": canonical,
        "active_offers": list(active_offers.values()),
        "price_history": history
    }