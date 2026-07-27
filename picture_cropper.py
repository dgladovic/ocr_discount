"""
Reads extracted JSON files from extracted_json/, finds the corresponding PDF
in downloads/, converts PDF pages to images, crops out individual product offer
images based on Gemini 2D bounding boxes, and saves them to cropped_images/.
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
    """
    box: [ymin, xmin, ymax, xmax] on a 0-1000 scale.
    Converts 0-1000 normalized coordinates to pixel coordinates and crops.
    """
    if not box or len(box) != 4:
        return None

    ymin, xmin, ymax, xmax = box
    
    # Validation checks
    if ymin >= ymax or xmin >= xmax:
        return None

    width, height = page_image.size

    # Convert 0-1000 normalized scale to actual pixel coordinates
    left = (xmin / 1000.0) * width
    top = (ymin / 1000.0) * height
    right = (xmax / 1000.0) * width
    bottom = (ymax / 1000.0) * height

    # Clamp coordinates to image boundaries
    left = max(0, min(width, left))
    top = max(0, min(height, top))
    right = max(left + 1, min(width, right))
    bottom = max(top + 1, min(height, bottom))

    return page_image.crop((left, top, right, bottom))


def process_json_file(json_path: str):
    filename = os.path.basename(json_path)
    pdf_filename = filename.replace(".json", ".pdf")
    pdf_path = os.path.join(DOWNLOAD_DIR, pdf_filename)

    if not os.path.exists(pdf_path):
        print(f"Skipping {filename}: Matching PDF not found at {pdf_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    product_offers = data.get("productOffers", [])
    if not product_offers:
        print(f"{filename}: No product offers to crop.")
        return

    retailer_code = data.get("retailerCode", "unknown")
    retailer_crop_dir = os.path.join(CROPPED_IMAGES_DIR, retailer_code)
    os.makedirs(retailer_crop_dir, exist_ok=True)

    print(f"Processing '{pdf_filename}'...")
    try:
        pages = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        print(f"  ERROR: Could not render PDF {pdf_path}: {e}")
        return

    cropped_count = 0
    updated = False

    for idx, offer in enumerate(product_offers):
        page_num = offer.get("globalPageNumber", offer.get("pageNumber", 1))
        box = offer.get("boundingBox")

        if not box or page_num < 1 or page_num > len(pages):
            continue

        page_image = pages[page_num - 1]  # 0-indexed page list
        cropped = crop_image_from_box(page_image, box)

        if cropped:
            product_slug = slugify(offer.get("productName", f"product_{idx}"))
            crop_filename = f"{retailer_code}_{data.get('weekEnd', '')}_p{page_num}_{idx}_{product_slug}.png"
            crop_filepath = os.path.join(retailer_crop_dir, crop_filename)

            cropped.save(crop_filepath, format="PNG")
            
            # Attach local image path to the offer dict
            offer["imageUrl"] = crop_filepath
            cropped_count += 1
            updated = True

    # Save updated JSON with imageUrl references
    if updated:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  -> Cropped {cropped_count}/{len(product_offers)} product images into '{retailer_crop_dir}/'.")


def main():
    json_files = glob.glob(os.path.join(EXTRACTED_JSON_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{EXTRACTED_JSON_DIR}'. Run pdf_extractor.py first.")
        return

    for json_file in json_files:
        # Ignore debug text files
        if os.path.basename(json_file).startswith("_debug"):
            continue
        process_json_file(json_file)


if __name__ == "__main__":
    main()