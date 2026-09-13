from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from app.database import get_db_cursor

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def get_active_user_id(cur) -> str:
    """Fetches the real UUID of admin@retailoffers.com from the users table."""
    cur.execute("SELECT id FROM users WHERE email = 'admin@retailoffers.com' LIMIT 1;")
    user = cur.fetchone()
    if not user:
        # Fallback to the first available user in the table
        cur.execute("SELECT id FROM users LIMIT 1;")
        user = cur.fetchone()
    if not user:
        raise HTTPException(
            status_code=500, 
            detail="Database has 0 users. Run seed step to create admin@retailoffers.com."
        )
    return user["id"]


@router.get("")
def get_watchlist():
    """Returns all watched products for the active user, cross-referenced with flyer deals."""
    with get_db_cursor() as cur:
        user_id = get_active_user_id(cur)

        query = """
            SELECT 
                cp.id AS canonical_id,
                cp.display_name,
                cp.brand,
                cp.category,
                cp.unit_size,
                cp.unit_measurement,
                cp.image_url,
                wi.created_at AS watched_since,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'offer_id', po.id,
                            'retailer_name', r.name,
                            'retailer_code', r.code,
                            'current_price', po.current_price,
                            'original_price', po.original_price,
                            'discount_percent', po.discount_percent,
                            'base_price', po.base_price,
                            'base_price_unit', po.base_price_unit,
                            'week_start', po.week_start,
                            'week_end', po.week_end,
                            'flyer_pdf_url', sd.file_path,
                            'cropped_image_path', po.cropped_image_path
                        )
                    ) FILTER (WHERE po.id IS NOT NULL), '[]'::json
                ) AS active_offers
            FROM watchlist_items wi
            JOIN canonical_products cp ON wi.canonical_id = cp.id
            LEFT JOIN store_product_links spl ON spl.canonical_id = cp.id
            LEFT JOIN store_products sp ON spl.store_product_id = sp.id
            LEFT JOIN price_offers po ON po.store_product_id = sp.id AND po.week_end >= CURRENT_DATE
            LEFT JOIN retailers r ON sp.retailer_id = r.id
            LEFT JOIN source_documents sd ON po.source_document_id = sd.id
            WHERE wi.user_id = %s
            GROUP BY cp.id, wi.created_at
            ORDER BY wi.created_at DESC;
        """
        cur.execute(query, (user_id,))
        rows = cur.fetchall()

        on_sale, no_deals = [], []
        for item in rows:
            offers = item.get("active_offers", [])
            if offers and len(offers) > 0:
                best_price = min(o["current_price"] for o in offers if o.get("current_price"))
                best_discount = max((o.get("discount_percent") or 0) for o in offers)
                item["best_current_price"] = best_price
                item["best_discount_percent"] = best_discount if best_discount > 0 else None
                on_sale.append(item)
            else:
                no_deals.append(item)

        return jsonable_encoder({
            "total_watched": len(rows),
            "on_sale_count": len(on_sale),
            "on_sale": on_sale,
            "no_deals": no_deals
        })


@router.post("/{canonical_id}")
def add_to_watchlist(canonical_id: str):
    """Add product to watchlist with real PostgreSQL UNIQUE constraint enforcement."""
    with get_db_cursor(commit=True) as cur:
        user_id = get_active_user_id(cur)
        
        # Verify canonical product exists
        cur.execute("SELECT id FROM canonical_products WHERE id = %s;", (canonical_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Canonical product not found")

        # Native PostgreSQL upsert/conflict clause
        cur.execute("""
            INSERT INTO watchlist_items (user_id, canonical_id, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id, canonical_id) DO NOTHING;
        """, (user_id, canonical_id))

        return {"status": "success", "message": "Product added to watchlist"}


@router.delete("/{canonical_id}")
def remove_from_watchlist(canonical_id: str):
    """Remove a product from the user's watchlist."""
    with get_db_cursor(commit=True) as cur:
        user_id = get_active_user_id(cur)
        cur.execute("""
            DELETE FROM watchlist_items 
            WHERE user_id = %s AND canonical_id = %s;
        """, (user_id, canonical_id))
        return {"status": "success", "message": "Product removed from watchlist"}