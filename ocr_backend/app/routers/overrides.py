from fastapi import APIRouter, Query
from app.database import fetch_query
router = APIRouter(tags=["Overrides"])

@router.get("/product-overrides")
def get_product_overrides(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return fetch_query("SELECT * FROM product_overrides ORDER BY edited_at DESC LIMIT %s OFFSET %s;", (limit, offset))