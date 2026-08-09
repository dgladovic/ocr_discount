"""
Extracts structured offers from a retailer's PDF flyer using Gemini vision.
Writes raw JSON to extracted_json/ in the shared shape defined in schemas.py --
load_to_db.py reads that JSON and does the normalization + DB writes.

Filename convention expected: RETAILER_YYYY-MM-DD_TITLE.pdf (YYYY-MM-DD = flyer end date)
"""
import os
import io
import json
import glob
from datetime import datetime

from google import genai
from google.genai import types
from pdf2image import convert_from_path
from dotenv import load_dotenv

from ingestion.schemas import FLYER_DATA_SCHEMA
from ingestion.downloaders.config import RETAILER_CHUNK_SIZES

DOWNLOAD_DIR = "downloads"
OUTPUT_JSON_DIR = "extracted_json"
API_MODEL = "gemini-3.5-flash-lite"
DEFAULT_PAGE_CHUNK_SIZE = 8  # Gemini asset limit is 32; keep a safe buffer


os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)

PROMPT_TEXT = """
You are an expert Retail Data Normalization Engine.
Analyze the provided high-resolution flyer images (a batch of pages from one flyer).

1. Extract every distinct individual product offer, and every category-wide banner announcement.
2. STRICTLY choose 'category' from the provided ENUM. Do not invent new categories.
3. STRICTLY choose 'productType' from the provided ENUM, and make sure it belongs to the
   same category you also returned (e.g. a 'dairy_milk' productType must have category
   'Dairy & Eggs'). If genuinely nothing fits, use 'misc_other' with category 'Miscellaneous'.
4. Fill 'attributes' as precisely as printed on the label -- brand, unitSize (whatever kind
   of size/quantity is printed: weight, volume, or count), fat%, alcohol% -- using 'N/A' for
   anything not applicable or not visible. Do not guess or convert units yourself; just
   transcribe what's printed, exactly as shown (e.g. '500 g', '1 l', '10 Stück').
5. Set 'offerType' to the actual discount mechanism (percent off, fixed price, 2+1 style
   multi-buy, bundle, loyalty-card-required, or generic weekly special) -- not just the size
   of the discount. For MULTI_BUY offers also fill multibuyRequiredQty/multibuyFreeQty.
6. Generate 5-10 multilingual searchTags per product offer for fuzzy search indexing.
7. IMPORTANT -- keep 'productName' to the actual product name only. Do NOT include price or
   date clutter, AND do NOT include variant/assortment disclaimer text that describes the
   display rather than one specific product -- phrases like "versch. Sorten", "div. Sorten",
   "mehrere Sorten", "bunt gemischt", "nach Wahl", or similar "available in several varieties"
   language. If a product genuinely has no single name because it's a mixed assortment with no
   dominant item, use the category name as productName rather than inventing a variant list.
8. Report 'pageNumber' as the 1-based page number *within this batch of images* where the
   product appears, and 'boundingBox' as a tight [ymin, xmin, ymax, xmax] box (0-1000 scale)
   framing just that product's image -- these are used to crop a verification image later, so
   accuracy here matters as much as the text fields.
9. If a page has no offers or banners at all (e.g. a cover page or ad), contribute nothing
   for that page -- don't invent content.

Output a single JSON object strictly conforming to the provided schema.
"""


def _try_log_to_db(retailer_code: str, file_name: str, status: str, page_count: int | None = None, offer_count: int = 0, error_message: str | None = None):
    try:
        from db.db import get_conn, log_ingestion_run
        with get_conn() as conn:
            log_ingestion_run(conn, retailer_code, file_name, status, page_count, offer_count, error_message)
    except Exception:
        pass


def chunk_list(data: list, size: int):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def extract_offers_from_pdf(client: genai.Client, pdf_file_path: str, chunk_size: int = DEFAULT_PAGE_CHUNK_SIZE) -> tuple[dict, int]:
    """Runs the page-chunked Gemini extraction for one flyer PDF using a configured chunk size."""
    all_uploaded_files = []
    combined = {"productOffers": [], "categoryAnnouncements": []}
    pdf_filename = os.path.basename(pdf_file_path)

    try:
        pages = convert_from_path(pdf_file_path, dpi=300)
        print(f"'{pdf_filename}': {len(pages)} pages (using chunk size: {chunk_size})")

        for chunk_index, page_chunk in enumerate(chunk_list(pages, chunk_size)):
            chunk_files = []
            for page_image in page_chunk:
                buf = io.BytesIO()
                page_image.save(buf, format="PNG")
                buf.seek(0)
                file = client.files.upload(file=buf, config=types.UploadFileConfig(mime_type="image/png"))
                chunk_files.append(file)
                all_uploaded_files.append(file)

            response = client.models.generate_content(
                model=API_MODEL,
                contents=chunk_files + [PROMPT_TEXT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FLYER_DATA_SCHEMA,
                ),
            )
            try:
                chunk_data = json.loads(response.text)
                offers = chunk_data.get("productOffers", [])
                start_page = chunk_index * chunk_size + 1
                for offer in offers:
                    local_page = offer.get("pageNumber", 1)
                    offer["globalPageNumber"] = start_page + max(local_page - 1, 0)
                combined["productOffers"].extend(offers)
                combined["categoryAnnouncements"].extend(chunk_data.get("categoryAnnouncements", []))
                print(f"  chunk {chunk_index + 1}: {len(offers)} offers")
            except json.JSONDecodeError:
                print(f"  chunk {chunk_index + 1}: FAILED to parse model response, skipping")
                continue

        return combined, len(pages)
    finally:
        for f in all_uploaded_files:
            try:
                client.files.delete(name=f.name)
            except Exception as e:
                print(f"Warning: cleanup failed for {f.name}: {e}")


def process_all_flyers():
    load_dotenv()
    if "GEMINI_API_KEY" not in os.environ:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client()
    pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in '{DOWNLOAD_DIR}'.")
        return

    for pdf_path in pdf_files:
        pdf_filename = os.path.basename(pdf_path)
        parts = pdf_filename.replace(".pdf", "").split("_")
        retailer_code = parts[0].lower()
        try:
            week_end = datetime.strptime(parts[1], "%Y-%m-%d").strftime("%Y-%m-%d")
        except (IndexError, ValueError):
            week_end = datetime.now().strftime("%Y-%m-%d")

        chunk_size = RETAILER_CHUNK_SIZES.get(retailer_code, RETAILER_CHUNK_SIZES.get("default", DEFAULT_PAGE_CHUNK_SIZE))
        out_path = os.path.join(OUTPUT_JSON_DIR, pdf_filename.replace(".pdf", ".json"))

        # Skip Gemini extraction if a JSON for this exact leaflet already exists
        if os.path.exists(out_path):
            print(f"'{pdf_filename}': extracted JSON already exists — skipping Gemini extraction")
            continue

        try:
            data, page_count = extract_offers_from_pdf(client, pdf_path, chunk_size=chunk_size)
            data["retailerCode"] = retailer_code
            data["weekEnd"] = week_end
            data["sourceFilePath"] = pdf_path
            data["pageCount"] = page_count

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            offer_count = len(data["productOffers"])
            print(f"Saved {out_path} ({offer_count} offers)")

            _try_log_to_db(retailer_code, pdf_filename, "SUCCESS", page_count, offer_count)
        except Exception as e:
            err_msg = f"Extraction failed: {e}"
            print(f"ERROR extracting '{pdf_filename}': {err_msg}")
            _try_log_to_db(retailer_code, pdf_filename, "FAILED", None, 0, err_msg)
            continue


if __name__ == "__main__":
    process_all_flyers()