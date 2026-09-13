from fastapi import APIRouter, Query
from app.database import fetch_query

router = APIRouter(tags=["Overrides"])

@router.get("/product-overrides")
def get_product_overrides(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """Fetch human product overrides joined with canonical display name."""
    query = """
        SELECT 
            po.id,
            po.canonical_id,
            cp.display_name AS canonical_display_name,
            cp.image_url AS canonical_image_url,
            po.field_name,
            po.override_value,
            po.edited_by,
            po.edited_at
        FROM product_overrides po
        JOIN canonical_products cp ON po.canonical_id = cp.id
        ORDER BY po.edited_at DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_query(query, (limit, offset))