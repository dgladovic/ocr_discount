from typing import Optional
from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from app.database import fetch_query, get_db_cursor

router = APIRouter(tags=["Price Offers"])


@router.get("/price-offers")
def get_price_offers(
    limit: int = Query(100, ge=1, le=1000), 
    offset: int = Query(0, ge=0)
):
    query = """
        SELECT po.*, spl.canonical_id 
        FROM price_offers po
        LEFT JOIN store_product_links spl ON spl.store_product_id = po.store_product_id
        ORDER BY po.week_start DESC 
        LIMIT %s OFFSET %s;
    """
    return fetch_query(query, (limit, offset))


@router.get("/active-offers")
def get_active_offers(
    retailer_code: Optional[str] = Query(None, description="Retailer slug (e.g. billa, spar, hofer)"),
    category: Optional[str] = Query(None, description="Category name"),
    search: Optional[str] = Query(None, description="Search term for product or brand"),
    min_discount: Optional[float] = Query(None, ge=0, le=100, description="Minimum discount percentage"),
    sort_by: str = Query("discount_desc", pattern="^(discount_desc|price_asc|newest)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    query = """
        SELECT 
            po.id AS offer_id,
            po.current_price,
            po.original_price,
            po.discount_percent,
            po.offer_type,
            po.base_price,
            po.base_price_unit,
            po.week_start,
            po.week_end,
            po.cropped_image_path,
            sp.id AS store_product_id,
            sp.product_name_raw,
            sp.unit_size,
            sp.unit_measurement,
            sp.category,
            sp.brand,
            r.name AS retailer_name,
            r.code AS retailer_code,
            sd.file_path AS flyer_pdf_url,
            cp.id AS canonical_id,
            cp.display_name AS canonical_name
        FROM price_offers po
        JOIN store_products sp ON po.store_product_id = sp.id
        JOIN retailers r ON sp.retailer_id = r.id
        LEFT JOIN source_documents sd ON po.source_document_id = sd.id
        LEFT JOIN store_product_links spl ON sp.id = spl.store_product_id
        LEFT JOIN canonical_products cp ON spl.canonical_id = cp.id
        WHERE po.week_end >= CURRENT_DATE
    """
    params = []

    if retailer_code:
        query += " AND r.code = %s"
        params.append(retailer_code)

    if category:
        query += " AND sp.category = %s"
        params.append(category)

    if search:
        query += " AND (sp.product_name_raw ILIKE %s OR sp.brand ILIKE %s)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    if min_discount is not None:
        query += " AND po.discount_percent >= %s"
        params.append(min_discount)

    # Sorting
    if sort_by == "discount_desc":
        query += " ORDER BY po.discount_percent DESC NULLS LAST"
    elif sort_by == "price_asc":
        query += " ORDER BY po.current_price ASC"
    elif sort_by == "newest":
        query += " ORDER BY po.week_end ASC"

    query += " LIMIT %s OFFSET %s;"
    params.extend([limit, offset])

    with get_db_cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    # jsonable_encoder safely serializes UUIDs, Decimals, and Dates to JSON
    return {
        "items": jsonable_encoder(rows),
        "count": len(rows),
        "limit": limit,
        "offset": offset,
    }