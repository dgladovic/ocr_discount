"""
Extracts structured offers from a retailer's PDF flyer using Gemini vision.
Writes raw JSON to extracted_json/ in the shared shape defined in schemas.py --
load_to_db.py reads that JSON and does the normalization + DB writes.

Filename convention expected: RETAILER_YYYY-MM-DD_TITLE.pdf (YYYY-MM-DD = flyer end date)

WHY CHUNKING KEPT FAILING BEFORE:
Gemini models have "thinking" enabled by default, and thinking tokens are
billed against the SAME max_output_tokens budget as the actual JSON response.
Without an explicit max_output_tokens (which defaults lower than the model's
real 65,536 ceiling in several SDKs/CLIs) and without constraining thinking,
the model can burn an unpredictable chunk of its output budget "reasoning"
before writing any JSON -- producing silent truncation that has nothing to
do with how many pages you batched. This version:
  1. Uses gemini-3.5-flash-lite, Google's model recommended for high-
     throughput JSON extraction, with thinking_level=MINIMAL (the Gemini 3.x
     replacement for the old thinking_budget param -- setting both in the
     same request is a 400 error)
  2. Sets max_output_tokens explicitly to the model's real ceiling
  3. Batches a conservative number of pages per call (PAGE_CHUNK_SIZE),
     sized from observed offer density with a safety margin
  4. Auto-retries a failed chunk by splitting it in half once, so a single
     dense chunk doesn't cost you the whole chunk's offers
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

DOWNLOAD_DIR = "downloads"
OUTPUT_JSON_DIR = "extracted_json"
# 3.5 Flash-Lite is Google's cost/latency-optimized model, explicitly
# recommended by Google for high-throughput JSON extraction tasks like this one.
API_MODEL = "gemini-3.5-flash-lite"

# Sized from real observed data: ~12.6 offers/page average, 16 offers/page
# worst-case, ~200 tokens/offer -> even at worst-case density this leaves a
# ~60% safety margin against the model's 65,536 output-token ceiling.
# Raise this if you want fewer API calls; lower it if you still see failures.
PAGE_CHUNK_SIZE = 8
MAX_OUTPUT_TOKENS = 65536

os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)

PROMPT_TEXT = """
You are an expert Retail Data Normalization Engine.
Analyze the provided high-resolution flyer images (a batch of pages from one flyer).

1. Extract every distinct individual product offer, and every category-wide banner announcement.
2. STRICTLY choose 'category' from the provided ENUM. Do not invent new categories.
3. STRICTLY choose 'productType' from the provided ENUM, and make sure it belongs to the
   same category you also returned (e.g. a 'dairy_milk' productType must have category
   'Dairy & Eggs'). If genuinely nothing fits, use 'misc_other' with category 'Miscellaneous'.
4. Fill 'attributes' as precisely as printed on the label -- brand, volume/weight/count,
   fat%, alcohol% -- using 'N/A' for anything not applicable or not visible. Do not guess
   or convert units yourself; just transcribe what's printed.
5. Set 'offerType' to the actual discount mechanism (percent off, fixed price, 2+1 style
   multi-buy, bundle, loyalty-card-required, or generic weekly special) -- not just the size
   of the discount. For MULTI_BUY offers also fill multibuyRequiredQty/multibuyFreeQty.
6. Generate 5-10 multilingual searchTags per product offer for fuzzy search indexing.
7. Keep productName clean of price/date clutter.
8. If a page has no offers or banners at all (e.g. a cover page or ad), contribute nothing
   for that page -- don't invent content.

Output a single JSON object strictly conforming to the provided schema.
"""

GENERATE_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=FLYER_DATA_SCHEMA,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    # Gemini 3.x models use thinking_level, not the old thinking_budget --
    # setting both in the same request throws a 400 error. MINIMAL is right
    # for straightforward schema-constrained extraction: no multi-step
    # reasoning needed, and it keeps the full output budget available for
    # the actual JSON instead of "thinking" tokens eating into it.
    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
)


def chunk_list(data: list, size: int):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def _upload_pages(client: genai.Client, page_images: list) -> list:
    uploaded = []
    for page_image in page_images:
        buf = io.BytesIO()
        page_image.save(buf, format="PNG")
        buf.seek(0)
        uploaded.append(client.files.upload(file=buf, config=types.UploadFileConfig(mime_type="image/png")))
    return uploaded


def _cleanup(client: genai.Client, uploaded_files: list):
    for f in uploaded_files:
        try:
            client.files.delete(name=f.name)
        except Exception as e:
            print(f"Warning: cleanup failed for {f.name}: {e}")


def _run_gemini(client: genai.Client, page_images: list):
    """Uploads a batch of page images, runs one Gemini call, returns parsed dict or None."""
    uploaded_files = _upload_pages(client, page_images)
    try:
        response = client.models.generate_content(
            model=API_MODEL,
            contents=uploaded_files + [PROMPT_TEXT],
            config=GENERATE_CONFIG,
        )
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "unknown"
            print(f"    FAILED to parse ({e}). finish_reason={finish_reason}")
            return None
    finally:
        _cleanup(client, uploaded_files)


def extract_offers_from_pdf(client: genai.Client, pdf_file_path: str) -> dict:
    """Runs the page-chunked Gemini extraction for one flyer PDF, with
    auto-split retry if a chunk's response fails to parse."""
    combined = {"productOffers": [], "categoryAnnouncements": []}
    pdf_filename = os.path.basename(pdf_file_path)

    # Wrap conversion in a try/except to catch HTML pages disguised as PDFs
    try:
        pages = convert_from_path(pdf_file_path, dpi=300)
    except Exception as e:
        print(f"  FAILED: '{pdf_filename}' is not a valid PDF or is corrupted. Skipping.")
        return None  # Return None so we don't generate a broken JSON cache

    print(f"'{pdf_filename}': {len(pages)} pages")

    for chunk_index, page_chunk in enumerate(chunk_list(pages, PAGE_CHUNK_SIZE)):
        chunk_num = chunk_index + 1
        chunk_data = _run_gemini(client, page_chunk)

        if chunk_data is None and len(page_chunk) > 1:
            # Retry by splitting the chunk in half -- handles the case where
            # this particular chunk was denser than our safety margin assumed.
            print(f"  chunk {chunk_num}: retrying as two smaller chunks")
            mid = len(page_chunk) // 2
            halves = [page_chunk[:mid], page_chunk[mid:]]
            merged = {"productOffers": [], "categoryAnnouncements": []}
            any_success = False
            for half_index, half in enumerate(halves):
                half_data = _run_gemini(client, half)
                if half_data is not None:
                    any_success = True
                    merged["productOffers"].extend(half_data.get("productOffers", []))
                    merged["categoryAnnouncements"].extend(half_data.get("categoryAnnouncements", []))
                else:
                    print(f"    chunk {chunk_num} half {half_index + 1}: still failed, dropping those pages")
            chunk_data = merged if any_success else None

        if chunk_data is None:
            print(f"  chunk {chunk_num}: FAILED, skipping ({len(page_chunk)} page(s) lost)")
            debug_path = os.path.join(OUTPUT_JSON_DIR, f"_debug_{pdf_filename.replace('.pdf', '')}_c{chunk_num}.txt")
            with open(debug_path, "w", encoding="utf-8") as dbg:
                dbg.write("chunk failed to parse even after split retry\n")
            continue

        n_offers = len(chunk_data.get("productOffers", []))
        combined["productOffers"].extend(chunk_data.get("productOffers", []))
        combined["categoryAnnouncements"].extend(chunk_data.get("categoryAnnouncements", []))
        print(f"  chunk {chunk_num} ({len(page_chunk)} pages): {n_offers} offers")

    return combined


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
        out_path = os.path.join(OUTPUT_JSON_DIR, pdf_filename.replace(".pdf", ".json"))
        
        # SKIP LOGIC: If JSON exists, assume already parsed successfully
        if os.path.exists(out_path):
            print(f"Skipping '{pdf_filename}': Already parsed ({out_path} exists).")
            continue

        parts = pdf_filename.replace(".pdf", "").split("_")
        retailer_code = parts[0].lower()
        try:
            week_end = datetime.strptime(parts[1], "%Y-%m-%d").strftime("%Y-%m-%d")
        except (IndexError, ValueError):
            week_end = datetime.now().strftime("%Y-%m-%d")

        data = extract_offers_from_pdf(client, pdf_path)
        
        # If the function returned None (e.g. invalid PDF), skip saving JSON
        if data is None:
            continue
            
        data["retailerCode"] = retailer_code
        data["weekEnd"] = week_end

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved {out_path} ({len(data['productOffers'])} offers)")


if __name__ == "__main__":
    process_all_flyers()