import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <--- Import this

DB_DSN = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:postgrespassword@db:5432/retail_offers"
)

app = FastAPI(
    title="Retail Offers API",
    description="API for fetching retail offers, store products, and canonical listings.",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("cropped_images", exist_ok=True)

app.mount("/cropped_images", StaticFiles(directory="cropped_images"), name="cropped_images")

def fetch_query(query: str, params: tuple = None):
    """Helper function to execute SELECT query and return JSON-serializable dictionaries."""
    try:
        with psycopg2.connect(DB_DSN) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                rows = cur.fetchall()
                return jsonable_encoder(rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Retail Offers API is active"}


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@app.get("/retailers", tags=["Retailers"])
def get_retailers():
    """Fetch all retailers."""
    return fetch_query("SELECT id, name, code FROM retailers ORDER BY name ASC;")


@app.get("/store-products", tags=["Store Products"])
def get_store_products(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    retailer_id: str | None = None
):
    """Fetch store products with pagination and optional retailer filter."""
    if retailer_id:
        return fetch_query(
            "SELECT * FROM store_products WHERE retailer_id = %s ORDER BY last_seen_at DESC LIMIT %s OFFSET %s;",
            (retailer_id, limit, offset)
        )
    return fetch_query(
        "SELECT * FROM store_products ORDER BY last_seen_at DESC LIMIT %s OFFSET %s;",
        (limit, offset)
    )


@app.get("/canonical-products", tags=["Canonical Products"])
def get_canonical_products(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch canonical products (excluding raw embeddings vector by default for performance)."""
    query = """
        SELECT id, display_name, category, product_type, brand, volume_ml, 
               weight_g, fat_percent, organic, is_manually_edited, updated_at 
        FROM canonical_products 
        ORDER BY updated_at DESC 
        LIMIT %s OFFSET %s;
    """
    return fetch_query(query, (limit, offset))


@app.get("/store-product-links", tags=["Product Links"])
def get_store_product_links(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch store product to canonical product links."""
    return fetch_query(
        "SELECT * FROM store_product_links LIMIT %s OFFSET %s;",
        (limit, offset)
    )


@app.get("/price-offers", tags=["Price Offers"])
def get_price_offers(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch current and historic price offers."""
    return fetch_query(
        "SELECT * FROM price_offers ORDER BY week_start DESC LIMIT %s OFFSET %s;",
        (limit, offset)
    )


@app.get("/category-announcements", tags=["Announcements"])
def get_category_announcements(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch store category-wide discount announcements."""
    return fetch_query(
        "SELECT * FROM category_announcements ORDER BY week_start DESC LIMIT %s OFFSET %s;",
        (limit, offset)
    )


@app.get("/product-overrides", tags=["Overrides"])
def get_product_overrides(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch manual human overrides."""
    return fetch_query(
        "SELECT * FROM product_overrides ORDER BY edited_at DESC LIMIT %s OFFSET %s;",
        (limit, offset)
    )


@app.get("/users", tags=["Users"])
def get_users(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Fetch users."""
    return fetch_query(
        "SELECT id, email FROM users ORDER BY email ASC LIMIT %s OFFSET %s;",
        (limit, offset)
    )


@app.get("/watchlist-items", tags=["Watchlist"])
def get_watchlist_items(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: str | None = None
):
    """Fetch user watchlist items."""
    if user_id:
        return fetch_query(
            "SELECT * FROM watchlist_items WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;",
            (user_id, limit, offset)
        )
    return fetch_query(
        "SELECT * FROM watchlist_items ORDER BY created_at DESC LIMIT %s OFFSET %s;",
        (limit, offset)
    )
    
@app.get("/store-products/{product_id}", tags=["Store Products"])
def get_store_product_details(product_id: str):
    """Fetch complete details for a store product, including latest price offer, retailer, and canonical link."""
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
            po.effective_unit_price,
            po.availability_date_range,
            cp.id AS canonical_id,
            cp.display_name AS canonical_display_name
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