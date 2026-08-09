"""
Reads extracted JSON files from extracted_json/, finds the corresponding PDF
in downloads/, converts PDF pages to images, crops out individual product
offer images based on Gemini's globalPageNumber + bounding boxes, and saves
them to cropped_images/<retailer>/. Writes the crop path back onto each
offer as imageUrl, so load_to_db.py can persist it to store_products.image_url
and price_offers.cropped_image_path (the traceability mechanism -- see
specs/01-data-model.md).

Run this AFTER pdf_extractor.py and BEFORE load_to_db.py.
"""
import os
import re
import json
import glob
from pdf2image import convert_from_path
from PIL import Image

EXTRACTED_JSON_DIR = "extracted_json"
DOWNLOAD_DIR = "downloads"
CROPPED_IMAGES_DIR = "cropped_images"

os.makedirs(CROPPED_IMAGES_DIR, exist_ok=True)


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:40]


def crop_image_from_box(page_image: Image.Image, box: list) -> Image.Image | None:
    """box: [ymin, xmin, ymax, xmax] on a 0-1000 scale."""
    if not box or len(box) != 4:
        return None
    ymin, xmin, ymax, xmax = box
    if ymin >= ymax or xmin >= xmax:
        return None

    width, height = page_image.size
    left = max(0, min(width, (xmin / 1000.0) * width))
    top = max(0, min(height, (ymin / 1000.0) * height))
    right = max(left + 1, min(width, (xmax / 1000.0) * width))
    bottom = max(top + 1, min(height, (ymax / 1000.0) * height))
    return page_image.crop((left, top, right, bottom))


def _check_db_canonical_has_image(offer: dict) -> bool:
    """Returns True ONLY if a matching canonical product has an image AND that file exists on disk."""
    try:
        from db.db import get_conn
        from ingestion.normalize import normalize_offer
        norm = normalize_offer(offer)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT image_url FROM canonical_products
                    WHERE category = %s AND product_type = %s
                      AND brand IS NOT DISTINCT FROM %s
                      AND unit_size IS NOT DISTINCT FROM %s
                      AND unit_measurement IS NOT DISTINCT FROM %s
                      AND fat_percent IS NOT DISTINCT FROM %s
                      AND image_url IS NOT NULL
                    LIMIT 1
                    """,
                    (norm["category"], norm["productType"], norm.get("brand"),
                     norm.get("unit_size"), norm.get("unit_measurement"), norm.get("fat_percent")),
                )
                row = cur.fetchone()
                if row and row[0]:
                    # Make sure the file in the database ACTUALLY exists on disk!
                    db_image_path = row[0]
                    return os.path.exists(db_image_path)
                return False
    except Exception:
        return False


def process_json_file(json_path: str):
    filename = os.path.basename(json_path)
    pdf_filename = filename.replace(".json", ".pdf")
    pdf_path = os.path.join(DOWNLOAD_DIR, pdf_filename)

    if not os.path.exists(pdf_path):
        print(f"Skipping {filename}: matching PDF not found at {pdf_path}")
        return

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    product_offers = data.get("productOffers", [])
    if not product_offers:
        print(f"{filename}: no product offers to crop.")
        return

    retailer_code = data.get("retailerCode", "unknown")
    retailer_crop_dir = os.path.join(CROPPED_IMAGES_DIR, retailer_code)
    os.makedirs(retailer_crop_dir, exist_ok=True)

    print(f"Processing '{pdf_filename}'...")
    
    # Filter offers that actually need cropping (no imageUrl set & no canonical image in DB)
    offers_to_crop = []
    for idx, offer in enumerate(product_offers):
        existing_img = offer.get("imageUrl")
        if existing_img and os.path.exists(existing_img):
            continue  # Only skip if the file ACTUALLY exists on disk!
        if _check_db_canonical_has_image(offer):
            # Canonical product already has an image, skip cropping
            continue
        offers_to_crop.append((idx, offer))

    if not offers_to_crop:
        print(f"  -> All {len(product_offers)} offers already have canonical images or imageUrl. Skipping PDF render.")
        return

    try:
        pages = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        print(f"  ERROR: could not render PDF {pdf_path}: {e}")
        return

    cropped_count = 0
    updated = False

    for idx, offer in offers_to_crop:
        page_num = offer.get("globalPageNumber", offer.get("pageNumber", 1))
        box = offer.get("boundingBox")

        if not box or page_num < 1 or page_num > len(pages):
            continue

        page_image = pages[page_num - 1]
        cropped = crop_image_from_box(page_image, box)
        if not cropped:
            continue

        product_slug = slugify(offer.get("productName", f"product_{idx}"))
        crop_filename = f"{retailer_code}_{data.get('weekEnd', '')}_p{page_num}_{idx}_{product_slug}.png"
        crop_filepath = os.path.join(retailer_crop_dir, crop_filename)
        cropped.save(crop_filepath, format="PNG")

        offer["imageUrl"] = crop_filepath
        cropped_count += 1
        updated = True

    if updated:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  -> cropped {cropped_count} new product images into '{retailer_crop_dir}/'.")


def main():
    json_files = glob.glob(os.path.join(EXTRACTED_JSON_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{EXTRACTED_JSON_DIR}'. Run pdf_extractor.py first.")
        return
    for json_file in json_files:
        if os.path.basename(json_file).startswith("_debug"):
            continue
        process_json_file(json_file)


if __name__ == "__main__":
    main()