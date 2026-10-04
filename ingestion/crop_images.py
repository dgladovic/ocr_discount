"""
Crops individual product offer images from PDF flyers based on bounding boxes.
Skips cropping if a verified image (e.g. web studio photo) already exists on disk.
"""
import os
import re
import json
import glob
from pdf2image import convert_from_path
from PIL import Image

from db.db import get_conn, find_canonical_by_attributes
try:
    from ingestion.normalize import normalize_offer
except ImportError:
    from normalize import normalize_offer

EXTRACTED_JSON_DIR = "extracted_json"
DOWNLOAD_DIR = "downloads"
CROPPED_IMAGES_DIR = "cropped_images"

os.makedirs(CROPPED_IMAGES_DIR, exist_ok=True)


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:40].strip("_")


def crop_image_from_box(page_image: Image.Image, box: list) -> Image.Image | None:
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


def _has_existing_image_on_disk(conn, offer: dict) -> bool:
    """Returns True if matching canonical item already has a photo that exists on disk."""
    try:
        norm = normalize_offer(offer)
        match = find_canonical_by_attributes(
            conn, 
            norm["category"], 
            norm["productType"], 
            norm.get("brand"),
            norm.get("unit_size"), 
            norm.get("unit_measurement"), 
            norm.get("fat_percent"),
        )
        if match and match.get("image_url"):
            return os.path.exists(match["image_url"])
        return False
    except Exception:
        return False


def process_json_file(conn, json_path: str):
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
        return

    retailer_code = data.get("retailerCode", "unknown")
    retailer_crop_dir = os.path.join(CROPPED_IMAGES_DIR, retailer_code)
    os.makedirs(retailer_crop_dir, exist_ok=True)

    print(f"Processing '{pdf_filename}'...")

    offers_to_crop = []
    for idx, offer in enumerate(product_offers):
        existing_img = offer.get("imageUrl")
        if existing_img and os.path.exists(existing_img):
            continue
        # Skip if canonical item already has a clean studio photo on disk!
        if _has_existing_image_on_disk(conn, offer):
            continue
        offers_to_crop.append((idx, offer))

    if not offers_to_crop:
        print(f"  -> All {len(product_offers)} offers already have studio/canonical images on disk. Skipping PDF render.")
        return

    try:
        pages = convert_from_path(pdf_path, dpi=150)
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

    print(f"  -> Cropped {cropped_count} new product images into '{retailer_crop_dir}/'.")


def main():
    json_files = glob.glob(os.path.join(EXTRACTED_JSON_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{EXTRACTED_JSON_DIR}'. Run pdf_extractor.py first.")
        return

    with get_conn() as conn:
        for json_file in json_files:
            if os.path.basename(json_file).startswith("_debug"):
                continue
            process_json_file(conn, json_file)


if __name__ == "__main__":
    main()