from fastapi import APIRouter, Query
from app.database import fetch_query
router = APIRouter(tags=["Price Offers"])

@router.get("/price-offers")
def get_price_offers(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    query = """
        SELECT po.*, spl.canonical_id 
        FROM price_offers po
        LEFT JOIN store_product_links spl ON spl.store_product_id = po.store_product_id
        ORDER BY po.week_start DESC LIMIT %s OFFSET %s;
    """
    return fetch_query(query, (limit, offset))