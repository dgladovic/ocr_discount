import re
import os
from fastapi import APIRouter, Query, HTTPException
from app.database import fetch_query

router = APIRouter(tags=["Store Products"])

def extract_flyer_info(cropped_image_path: str | None, pdf_file_path: str | None, retailer_code: str = "", week_end: str = ""):
    """Extracts page number from crop path and constructs PDF deep-link URL."""
    page_num = None
    pdf_url = None

    if cropped_image_path:
        match = re.search(r'_p(\d+)_', cropped_image_path)
        if match:
            page_num = int(match.group(1))

    # Determine PDF filename
    filename = None
    if pdf_file_path:
        filename = os.path.basename(pdf_file_path.replace("\\", "/"))
    elif retailer_code and week_end:
        # Fallback to search in downloads
        import glob
        matches = glob.glob(f"downloads/{retailer_code}_{week_end}_*.pdf")
        if matches:
            filename = os.path.basename(matches[0])

    if filename:
        pdf_url = f"downloads/{filename}"
        if page_num:
            pdf_url += f"#page={page_num}"

    return page_num, pdf_url


@router.get("/store-products/{product_id}")
def get_store_product_details(product_id: str):
    """Fetch complete details for a store product, including PDF flyer page link."""
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
            po.cropped_image_path,
            sd.file_path AS pdf_file_path,
            cp.id AS canonical_id,
            cp.display_name AS canonical_display_name,
            cp.image_url AS canonical_image_url
        FROM store_products sp
        JOIN retailers r ON sp.retailer_id = r.id
        LEFT JOIN price_offers po ON po.store_product_id = sp.id
        LEFT JOIN source_documents sd ON po.source_document_id = sd.id
        LEFT JOIN store_product_links spl ON spl.store_product_id = sp.id
        LEFT JOIN canonical_products cp ON spl.canonical_id = cp.id
        WHERE sp.id = %s
        ORDER BY po.week_start DESC
        LIMIT 1;
    """
    rows = fetch_query(query, (product_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Store product not found")
    
    product = rows[0]
    
    # Calculate PDF page deep-link
    page_num, pdf_url = extract_flyer_info(
        product.get("cropped_image_path"),
        product.get("pdf_file_path"),
        product.get("retailer_code", ""),
        str(product.get("week_end", ""))
    )
    product["flyer_page_number"] = page_num
    product["flyer_pdf_url"] = pdf_url

    return product


@router.get("/store-products")
def get_store_products(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    retailer_id: str | None = None
):
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


@router.get("/store-product-links")
def get_store_product_links(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return fetch_query("SELECT * FROM store_product_links LIMIT %s OFFSET %s;", (limit, offset))