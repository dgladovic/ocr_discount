from fastapi import APIRouter, Query, HTTPException
from app.database import fetch_query

router = APIRouter(tags=["Canonical Products"])

@router.get("/canonical-products")
def get_canonical_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    category: str | None = None,
    retailer_code: str | None = None,
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc")
):
    """
    Fetch canonical products with server-side pagination, fuzzy search, 
    category & retailer filters, and dynamic sorting.
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

    # 1. Search Filter (display_name or brand)
    if search and search.strip():
        where_clauses.append("(cp.display_name ILIKE %s OR cp.brand ILIKE %s)")
        search_param = f"%{search.strip()}%"
        params.extend([search_param, search_param])

    # 2. Category Filter
    if category and category.strip():
        where_clauses.append("cp.category = %s")
        params.append(category.strip())

    # 3. Retailer Code Filter (matches canonical products linked to store products of that retailer)
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

    # Count Query (Total matching records)
    count_query = f"SELECT COUNT(DISTINCT cp.id) AS total FROM canonical_products cp {where_sql};"
    
    # Items Query
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


@router.get("/canonical-products/{canonical_id}/details")
def get_canonical_product_details(canonical_id: str):
    """Fetch complete canonical product details, active retailer offers, and historical price offers."""
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
        WHERE spl.canonical_id = %s
        ORDER BY po.week_start DESC, r.name ASC;
    """
    history = fetch_query(history_query, (canonical_id,))

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