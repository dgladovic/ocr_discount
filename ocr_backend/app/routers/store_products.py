from fastapi import APIRouter, Query, HTTPException
from app.database import fetch_query

router = APIRouter(tags=["Store Products"])

@router.get("/store-products")
def get_store_products(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    retailer_id: str | None = None
):
    """Fetch store products with optional retailer filter and canonical_id join."""
    if retailer_id:
        query = """
            SELECT sp.*, spl.canonical_id 
            FROM store_products sp
            LEFT JOIN store_product_links spl ON spl.store_product_id = sp.id
            WHERE sp.retailer_id = %s 
            ORDER BY sp.last_seen_at DESC LIMIT %s OFFSET %s;
        """
        return fetch_query(query, (retailer_id, limit, offset))
    
    query = """
        SELECT sp.*, spl.canonical_id 
        FROM store_products sp
        LEFT JOIN store_product_links spl ON spl.store_product_id = sp.id
        ORDER BY sp.last_seen_at DESC LIMIT %s OFFSET %s;
    """
    return fetch_query(query, (limit, offset))


@router.get("/store-products/{product_id}")
def get_store_product_details(product_id: str):
    """Fetch complete details for a store product."""
    query = """
        SELECT 
            sp.*,
            r.name AS retailer_name,
            r.code AS retailer_code,
            po.id AS offer_id,
            po.week_start,
            po.week_end,
            po.current_price,
            po.original_price,
            po.offer_type,
            po.discount_percent,
            po.multibuy_required_qty,
            po.multibuy_free_qty,
            po.availability_date_range,
            cp.id AS canonical_id,
            cp.display_name AS canonical_display_name,
            cp.image_url AS canonical_image_url
        FROM store_products sp
        JOIN retailers r ON sp.retailer_id = r.id
        LEFT JOIN price_offers po ON po.store_product_id = sp.id
        LEFT JOIN store_product_links spl ON spl.store_product_id = sp.id
        LEFT JOIN canonical_products cp ON spl.canonical_id = cp.id
        WHERE sp.id = %s
        ORDER BY po.week_start DESC
        LIMIT 1;
    """
    rows = fetch_query(query, (product_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Store product not found")
    return rows[0]


@router.get("/store-product-links")
def get_store_product_links(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch store product to canonical product links."""
    return fetch_query(
        "SELECT * FROM store_product_links LIMIT %s OFFSET %s;",
        (limit, offset)
    )