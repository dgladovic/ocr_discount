"""
Rebuilds canonical_products and store_product_links cleanly from store_products
using the patched db.py matching logic.
Zero price offers or store products are lost.
"""
from db.db import get_conn, find_or_create_canonical

def rebuild():
    print("=" * 60)
    print("REBUILDING CANONICAL CATALOG FROM STORE PRODUCTS")
    print("=" * 60)
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Clean out the corrupted canonical records (preserving any manual human edits)
            print("1. Removing contaminated canonical records and links...")
            cur.execute("""
                DELETE FROM watchlist_items 
                WHERE canonical_id IN (SELECT id FROM canonical_products WHERE is_manually_edited = false);

                DELETE FROM store_product_links 
                WHERE canonical_id IN (SELECT id FROM canonical_products WHERE is_manually_edited = false);

                DELETE FROM canonical_products 
                WHERE is_manually_edited = false;
            """)

            # 2. Fetch all raw store products (which are 100% uncorrupted)
            cur.execute("""
                SELECT id, retailer_id, product_name_raw, category, product_type,
                       brand, unit_size, unit_measurement, fat_percent, organic, image_url
                FROM store_products
                ORDER BY first_seen_at ASC;
            """)
            store_prods = cur.fetchall()

            print(f"2. Re-resolving {len(store_prods)} store products with strict matching rules...")
            
            rebuilt_count = 0
            for sp in store_prods:
                sp_id = sp[0]
                offer_dict = {
                    "product_name_clean": sp[2],
                    "category": sp[3],
                    "productType": sp[4],
                    "brand": sp[5],
                    "unit_size": sp[6],
                    "unit_measurement": sp[7],
                    "fat_percent": sp[8],
                    "organic": sp[9],
                    "imageUrl": sp[10],
                }
                
                # Re-resolves using your patched find_or_create_canonical logic!
                find_or_create_canonical(conn, sp_id, offer_dict)
                rebuilt_count += 1

    print("=" * 60)
    print(f"SUCCESS: Re-resolved {rebuilt_count} store products into clean canonical products.")
    print("=" * 60)

if __name__ == "__main__":
    rebuild()