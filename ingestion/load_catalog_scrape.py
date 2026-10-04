"""
Loads web-scraped store catalog products (Spar, Billa) into PostgreSQL.
Copies studio photos into cropped_images/<retailer>/ and upgrades canonical products.
Does NOT create price offers.
"""

import os
import sys
import json
import shutil
import re

from db.db import get_conn, get_retailer_id, upsert_store_product, find_or_create_canonical
try:
    from ingestion.normalize import normalize_offer
except ImportError:
    from normalize import normalize_offer

CROPPED_IMAGES_DIR = "cropped_images"

# Billa private-label brands that usually start the product title
KNOWN_BILLA_BRANDS = [
    "ja! natürlich", "billa bio", "billa immer gut", "billa genusswelt", "billa",
    "clever", "wieselburger", "gösser", "stiegl", "ottakringer", "alpro",
    "manner", "milka", "barilla", "darbo", "nöm", "schärdinger", "rauch", "vöslauer"
]


def extract_billa_brand(title: str) -> str | None:
    """Extracts leading manufacturer or private label brand from Billa title."""
    t_lower = title.lower()
    for b in KNOWN_BILLA_BRANDS:
        if t_lower.startswith(b):
            # Preserve special casing
            if b == "ja! natürlich": return "Ja! Natürlich"
            if b == "billa bio": return "BILLA Bio"
            if b == "billa immer gut": return "BILLA immer gut"
            if b == "billa": return "BILLA"
            if b == "clever": return "Clever"
            if b == "nöm": return "NÖM"
            return b.title()
    return None


def load_scraped_catalog(retailer_code: str, json_path: str):
    if not os.path.exists(json_path):
        print(f"Skipping {retailer_code.upper()}: file not found at '{json_path}'")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"\n" + "=" * 60)
    print(f"INGESTING {len(products)} {retailer_code.upper()} CATALOG PRODUCTS")
    print("=" * 60)

    target_img_dir = os.path.join(CROPPED_IMAGES_DIR, retailer_code)
    os.makedirs(target_img_dir, exist_ok=True)

    loaded = 0
    with get_conn() as conn:
        retailer_id = get_retailer_id(conn, retailer_code)

        for raw_item in products:
            # 1. Ensure studio image is copied to cropped_images/<retailer>/
            local_src = raw_item.get("localImagePath")
            final_img_path = None

            if local_src and os.path.exists(local_src):
                filename = os.path.basename(local_src)
                target_dest = os.path.join(target_img_dir, filename)

                if os.path.abspath(local_src) != os.path.abspath(target_dest):
                    shutil.copy2(local_src, target_dest)

                # Store with web-friendly forward slashes for PostgreSQL & FastAPI
                final_img_path = target_dest.replace("\\", "/")

            # 2. Extract brand for Billa if missing
            detected_brand = raw_item.get("brand")
            if not detected_brand and retailer_code == "billa":
                detected_brand = extract_billa_brand(raw_item.get("productName", ""))

            # 3. Setup attributes for normalize_offer
            raw_item["attributes"] = {
                "brand": detected_brand or "N/A",
                "unitSize": raw_item.get("packageSize") or "N/A",
                "fatPercent": "N/A",
                "alcoholPercent": "N/A",
                "organic": "yes" if any(w in raw_item.get("productName", "").lower() for w in ["bio", "ja! natürlich", "natur*pur"]) else "unknown",
            }

            raw_item["imageUrl"] = final_img_path
            raw_item["offerType"] = "OTHER"
            raw_item["discount"] = "N/A"
            raw_item["availabilityDateRange"] = "N/A"
            raw_item["searchTags"] = [detected_brand or "", retailer_code]

            # 4. Normalize brand casing, units, and keys
            normalized = normalize_offer(raw_item)
            if final_img_path:
                normalized["imageUrl"] = final_img_path

            # 5. Upsert store product
            store_product_id = upsert_store_product(conn, retailer_id, normalized)

            # 6. Resolve canonical master item (upgrades to studio photo!)
            find_or_create_canonical(conn, store_product_id, normalized)
            loaded += 1

    print(f"SUCCESS: {loaded} {retailer_code.upper()} products active in database with studio photos.")


def main():
    # Targets configuration
    catalogs = {
        "spar": "spar_scraped_data/spar_catalog.json",
        "billa": "billa_scraped_data/billa_catalog.json",
    }

    # If specific retailer passed as CLI arg (e.g. python -m ingestion.load_catalog_scrape billa)
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
        if target in catalogs:
            load_scraped_catalog(target, catalogs[target])
            return
        elif target != "all":
            print(f"Unknown retailer '{target}'. Available: spar, billa, all")
            return

    # Default: Ingest all available catalog files found
    for ret_code, path in catalogs.items():
        if os.path.exists(path):
            load_scraped_catalog(ret_code, path)


if __name__ == "__main__":
    main()