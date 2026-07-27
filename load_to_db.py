"""
Phase 1 pipeline entry point. Run this after pdf_extractor.py and/or
lidl_scraper.py have written their JSON into extracted_json/.

    python load_to_db.py

For each raw offer: normalize -> upsert store_product -> resolve canonical
(exact match) -> insert this week's price_offer row.
"""
import glob
import json
import os

from db.db import get_conn, get_retailer_id, upsert_store_product, find_or_create_canonical, insert_price_offer
from normalize import normalize_offer, parse_start_date

EXTRACTED_JSON_DIR = "extracted_json"


def load_file(conn, filepath: str):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    retailer_code = data.get("retailerCode")
    week_end = data.get("weekEnd")
    if not retailer_code or not week_end:
        print(f"SKIP {filepath}: missing retailerCode/weekEnd")
        return

    retailer_id = get_retailer_id(conn, retailer_code)
    loaded, flagged = 0, 0

    for raw_offer in data.get("productOffers", []):
        offer = normalize_offer(raw_offer)

        # Prefer a connector-provided stable key (e.g. Lidl's URL hash) over the
        # name+size slug, since it's a more reliable per-store identity across weeks.
        if raw_offer.get("store_product_key_override"):
            offer["store_product_key"] = raw_offer["store_product_key_override"]

        if offer["current_price_numeric"] is None:
            print(f"  WARN: '{offer['productName']}' has no parseable price, skipping")
            continue

        if offer["type_category_mismatch"] or offer["attributes_incomplete"]:
            flagged += 1  # still ingested, just worth a look -- see README review queue note

        week_start = parse_start_date(offer.get("availabilityDateRange"), week_end)

        store_product_id = upsert_store_product(conn, retailer_id, offer)
        find_or_create_canonical(conn, store_product_id, offer)
        insert_price_offer(conn, store_product_id, week_start, week_end, offer)
        loaded += 1

    print(f"{filepath}: loaded {loaded} offers ({flagged} flagged for review)")


def main():
    files = glob.glob(os.path.join(EXTRACTED_JSON_DIR, "*.json"))
    if not files:
        print(f"No JSON files found in '{EXTRACTED_JSON_DIR}'.")
        return

    with get_conn() as conn:
        for filepath in files:
            load_file(conn, filepath)


if __name__ == "__main__":
    main()