import os
import io
import json
import sys
import glob
import re
from datetime import datetime
from google import genai
from google.genai import types
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv

# --- CONFIGURATION ---
DOWNLOAD_DIR = "downloads"
PROCESSED_LOG_PATH = "processed_flyer_log.json"
OUTPUT_JSON_DIR = "extracted_json"
API_MODEL = "gemini-2.5-flash"
# The API has a limit of 32 assets (images/pages). Using 30 for a safe buffer.
PAGE_CHUNK_SIZE = 30 

# Ensure the output directory exists
os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)

# --- HELPER FUNCTIONS FOR POST-PROCESSING (Cleaning and Normalization) ---

def slugify(text):
    """Converts text to a database-friendly, hashable slug for the productHash."""
    text = str(text).lower().strip()
    # Remove all non-alphanumeric/whitespace/hyphen characters
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace whitespace and hyphens with a single underscore
    text = re.sub(r'[-\s]+', '_', text)
    return text[:60] # Limit length

def clean_price(price_str: str | None) -> float | None:
    """Converts a price string (e.g., '5.99€') to a float or None."""
    if not isinstance(price_str, str) or price_str == 'N/A' or not price_str.strip():
        return None
    
    # Remove currency symbols (€, $), commas (replace with dot), and any trailing text
    cleaned = price_str.replace('€', '').replace('$', '').replace('Sfr', '').replace(',', '.').strip()
    
    # Find the first sequence of numbers/dots, stop at first space/letter
    match = re.match(r'[\d\.]+', cleaned)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            pass
    return None

def parse_start_date(date_range_str: str, end_date_str: str) -> str:
    """
    Parses the start date from a range string (e.g., '20.10. - 22.10.') using the
    end_date_str ('YYYY-MM-DD') for year context.
    Returns: 'YYYY-MM-DD' string or the end_date_str if parsing fails.
    """
    if not date_range_str or date_range_str == 'N/A' or not end_date_str:
        return end_date_str

    try:
        # Get the year context from the reliable end date in the filename
        end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d')
        context_year = end_date_obj.year
    except ValueError:
        return end_date_str # Cannot establish year context

    # Look for a simple DD.MM format at the start of the string
    start_date_match = re.search(r'^(\d{1,2}\.\d{1,2})[\s\.\-]', date_range_str.strip())
    
    if start_date_match:
        # Extract the 'DD.MM' part
        day_month = start_date_match.group(1)
        
        try:
            # Combine D.M. with the context year
            start_date_str_temp = f"{day_month.replace('.', '')}{context_year}" 
            start_date_obj = datetime.strptime(start_date_str_temp, '%d%m%Y')
            return start_date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass

    return end_date_str # Fallback: use the end date as both start and end date

def post_process_data(raw_data: dict, pdf_filename: str) -> dict:
    """
    Takes the model's raw JSON output and refines it for PostgreSQL import.
    - Generates productHash (unique stable ID slug).
    - Parses dates (offerStartDate, offerEndDate).
    - Converts prices to numeric floats.
    """
    # Filename structure: RETAILER_YYYY-MM-DD_TITLE.pdf (End Date is YYYY-MM-DD)
    parts = pdf_filename.split('_')
    
    # Establish a reliable offer_end_date from the filename (the day the flyer expires)
    offer_end_date = None
    if len(parts) >= 3:
        try:
            # parts[1] is the YYYY-MM-DD date string
            datetime.strptime(parts[1], '%Y-%m-%d') 
            offer_end_date = parts[1]
        except ValueError:
            pass
            
    # Fallback to current date if filename is not parseable
    if not offer_end_date:
        offer_end_date = datetime.now().strftime('%Y-%m-%d')
    
    processed_offers = []
    
    for offer in raw_data.get('productOffers', []):
        # 1. GENERATE UNIQUE PRODUCT HASH (Used for future linking to the 'products' master table)
        # This hash guarantees that 'Whole Milk 1L' is different from 'Skim Milk 1L'.
        product_key = f"{offer.get('productName', '')}|{offer.get('packageSize', '')}|{offer.get('category', '')}"
        offer['productHash'] = slugify(product_key)
        
        # 2. PARSE DATES (for transactional data)
        date_range = offer.get('availabilityDateRange')
        
        # offerEndDate is the reliable date from the filename
        offer['offerEndDate'] = offer_end_date
        
        # Try to derive the start date from the date range string
        offer['offerStartDate'] = parse_start_date(date_range, offer_end_date)
        
        # 3. CONVERT PRICES TO NUMERIC (for math/sorting in the database)
        offer['currentPriceNumeric'] = clean_price(offer.get('currentPrice'))
        offer['oldPriceNumeric'] = clean_price(offer.get('oldPrice'))

        # Append the now-enriched offer
        processed_offers.append(offer)

    # Reconstruct the final, clean structure
    final_data = {
        'productOffers': processed_offers,
        'categoryAnnouncements': raw_data.get('categoryAnnouncements', [])
    }
    
    return final_data

# --- GEMINI API SCHEMAS (Define what the model *must* return) ---

PRODUCT_OFFER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "productName": {"type": "STRING", "description": "The name of the item on offer."},
        "category": {"type": "STRING", "description": "Determine the most specific food or product category (e.g., 'Meat & Poultry', 'Baked Goods', 'Dairy')."},
        "currentPrice": {"type": "STRING", "description": "The current promotional price, including currency (e.g., 5.99€)."},
        "oldPrice": {"type": "STRING", "description": "The original, non-sale price before discount (e.g., 7.99€). If the old price is not visible, use 'N/A'."},
        "packageSize": {"type": "STRING", "description": "The size of the product package (e.g., '530 g', '1 kg', '3 pcs', '1 liter')."},
        "unitPrice": {"type": "STRING", "description": "The price per standardized unit, usually per kg or per liter (e.g., '11.30/kg'). If not found, use 'N/A'."},
        "discount": {"type": "STRING", "description": "The discount amount or percentage (e.g., 25% off or -1.00€). If not found, use 'N/A'."},
        "availabilityDateRange": {"type": "STRING", "description": "The start and end date of the offer (e.g., '20.10. - 22.10.' or 'Mon-Wed'). If not found, use 'N/A'."}
    },
    "required": ["productName", "category", "currentPrice", "packageSize", "availabilityDateRange"] 
}

CATEGORY_ANNOUNCEMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "announcementType": {"type": "STRING", "description": "The nature of the promotion (e.g., 'Category Discount', 'Coupon Required', 'Weekend Special')."},
        "categoryAffected": {"type": "STRING", "description": "The category the discount applies to (e.g., 'All Beer', 'Frozen Pizzas', 'Tea')."},
        "discountValue": {"type": "STRING", "description": "The main discount value (e.g., '25% off', 'Buy 1 Get 1 Free', '€5 off')."},
        "details": {"type": "STRING", "description": "Any key conditions or exclusions mentioned on the banner (e.g., 'Limit 5 per customer', 'Only on Friday'). If no details are visible, use 'N/A'."},
        "availabilityDateRange": {"type": "STRING", "description": "The specific date range for this banner discount (e.g., 'Friday only 8:00-12:00'). If not found, use 'N/A'."}
    },
    "required": ["categoryAffected", "discountValue", "availabilityDateRange"]
}

FLYER_DATA_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "productOffers": {
            "type": "ARRAY",
            "items": PRODUCT_OFFER_SCHEMA,
            "description": "An array of detailed information for individual products on sale."
        },
        "categoryAnnouncements": {
            "type": "ARRAY",
            "items": CATEGORY_ANNOUNCEMENT_SCHEMA,
            "description": "An array of prominent, category-wide banner discounts (e.g., '25% off all Beer'). If none are found, return an empty array."
        }
    },
    "required": ["productOffers", "categoryAnnouncements"]
}

# --- LOG MANAGEMENT FUNCTIONS ---

def load_processed_log():
    """Loads the set of previously processed PDF filenames."""
    if not os.path.exists(PROCESSED_LOG_PATH):
        return set()
    try:
        with open(PROCESSED_LOG_PATH, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"Warning: Could not read or decode {PROCESSED_LOG_PATH}. Starting with an empty log.")
        return set()

def save_processed_log(processed_files):
    """Saves the updated set of processed PDF filenames to the log file."""
    try:
        with open(PROCESSED_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(list(processed_files), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not save log file: {e}")

# --- BATCH PROCESSING HELPER ---

def chunk_list(data: list, size: int):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(data), size):
        yield data[i:i + size]

def analyze_pdf_with_gemini_vision(client: genai.Client, pdf_file_path: str, output_json_name: str):
    """
    Handles PDF conversion, uploads, API batch processing, result merging, 
    post-processing, and cleanup.
    """
    all_uploaded_files = []
    pdf_filename = os.path.basename(pdf_file_path)
    combined_raw_data = {'productOffers': [], 'categoryAnnouncements': []}
    
    try:
        # 1. Convert PDF pages to images
        print(f"--- 1. Splitting '{pdf_filename}' into high-DPI images... ---")
        try:
            pages = convert_from_path(pdf_file_path, dpi=300) 
        except Exception as e:
            print(f"ERROR: PDF conversion failed. Is Poppler Utils installed correctly?")
            print(f"Details: {e}")
            return False 

        num_pages = len(pages)
        print(f"Successfully split PDF into {num_pages} pages.")

        # 2. Iterate and process in batches (chunks)
        print(f"\n--- 2. Starting batch processing (Chunk Size: {PAGE_CHUNK_SIZE})... ---")
        
        for chunk_index, page_chunk in enumerate(chunk_list(pages, PAGE_CHUNK_SIZE)):
            start_page = chunk_index * PAGE_CHUNK_SIZE + 1
            end_page = start_page + len(page_chunk) - 1
            
            print(f"\n  [CHUNK {chunk_index + 1}] Processing pages {start_page} to {end_page}...")

            # --- Upload images for the current chunk ---
            chunk_files = []
            for i, page_image in enumerate(page_chunk):
                page_num = start_page + i
                img_byte_arr = io.BytesIO()
                page_image.save(img_byte_arr, format='PNG') 
                img_byte_arr.seek(0)

                upload_config = types.UploadFileConfig(mime_type='image/png')
                file = client.files.upload(file=img_byte_arr, config=upload_config)
                
                chunk_files.append(file)
                all_uploaded_files.append(file) # Track all files for final cleanup
            
            print(f"    Uploaded {len(chunk_files)} images for this chunk.")

            # --- Create prompt and send API request ---
            prompt_text = (
                "You are an expert retail data extraction agent. "
                "Analyze the provided high-resolution flyer images (this is a batch of pages from a larger flyer). "
                "Your task is to perform meticulous **OCR** and **structured data extraction**. "
                "1. Identify and extract data for every distinct **individual product offer** (e.g., Milk, Bread, Cheese) found across these specific pages. "
                "2. Identify and extract data for every **category-wide promotional announcement** (e.g., '25% off all frozen goods'). "
                "3. For optional fields like 'oldPrice', 'unitPrice', or 'discount', use the string **'N/A'** if the information is not explicitly visible in the image. "
                "The output MUST be a single JSON object that strictly conforms to the provided schema."
            )
            
            contents = chunk_files + [prompt_text]
            
            print("    Sending query to Gemini for structured extraction...")

            response = client.models.generate_content(
                model=API_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FLYER_DATA_SCHEMA 
                )
            )

            # --- Merge results ---
            try:
                raw_chunk_data = json.loads(response.text)
                
                # Append product offers
                combined_raw_data['productOffers'].extend(raw_chunk_data.get('productOffers', []))
                
                # Append category announcements
                combined_raw_data['categoryAnnouncements'].extend(raw_chunk_data.get('categoryAnnouncements', []))

                print(f"    Chunk successfully extracted and merged. Total offers collected so far: {len(combined_raw_data['productOffers'])}")

            except json.JSONDecodeError:
                print(f"CRITICAL ERROR: Failed to parse JSON response from the model for chunk {chunk_index + 1}.")
                # Continue processing other chunks if possible, but log the error
                continue 

        # 3. Post-process and save the final merged data
        print("\n" + "="*50)
        print("3. Post-Processing and Saving Structured JSON Output")
        print(f"Final total offers collected: {len(combined_raw_data['productOffers'])}")
        
        final_data = post_process_data(combined_raw_data, pdf_filename)
        
        output_filepath = os.path.join(OUTPUT_JSON_DIR, output_json_name)
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        
        print(f"SUCCESS: Data successfully saved to '{output_filepath}'.")
        return True 

    except Exception as e:
        print(f"\nFATAL ERROR during analysis: {e}")
        return False
        
    finally:
        # 4. Clean up by deleting ALL uploaded files
        if all_uploaded_files:
            print(f"\n--- 4. Cleaning up {len(all_uploaded_files)} uploaded files... ---")
            for file in all_uploaded_files:
                try:
                    client.files.delete(name=file.name)
                except Exception as cleanup_e:
                    print(f"Warning: Failed to clean up file {file.name}. Error: {cleanup_e}")
            print("Cleanup complete.")


def process_active_flyers():
    """
    Main function to iterate through downloaded PDFs, check the log, and categorize new ones.
    """
    load_dotenv() 
    if 'GEMINI_API_KEY' not in os.environ:
        print("FATAL ERROR: The GEMINI_API_KEY environment variable is not set.")
        return

    try:
        client = genai.Client()
    except Exception as e:
        print(f"FATAL ERROR: Could not initialize Gemini client: {e}")
        return

    processed_files = load_processed_log()
    print(f"\n--- Categorizer Started ---")
    print(f"1. Loaded {len(processed_files)} previously processed file IDs (to skip API calls).")
    
    pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f"2. No PDF files found in '{DOWNLOAD_DIR}'. Nothing to categorize.")
        return

    newly_categorized_count = 0
    
    for pdf_filepath in pdf_files:
        pdf_filename = os.path.basename(pdf_filepath)
        json_output_name = pdf_filename.replace('.pdf', '.json')

        # IDEMPOTENCY CHECK: Skip if the file has already been successfully categorized
        if pdf_filename in processed_files:
            print(f"\n--- Skipping: {pdf_filename} ---")
            print("This flyer is already in the log. Skipping categorization to save API cost.")
            continue
            
        print(f"\n--- Starting Categorization for: {pdf_filename} ---")

        # 3. Process the file
        success = analyze_pdf_with_gemini_vision(client, pdf_filepath, json_output_name)
        
        # 4. Log the success
        if success:
            processed_files.add(pdf_filename)
            newly_categorized_count += 1
            print(f"SUCCESS: Logged '{pdf_filename}' as fully categorized.")
            
    # 5. Save the updated log for the next run
    save_processed_log(processed_files)
    print(f"\n--- Categorizer Finished ---")
    print(f"Summary: {newly_categorized_count} flyers newly categorized via Gemini Vision API.")


if __name__ == "__main__":
    # Note: Requires 'pip install google-genai pypdf pdf2image python-dotenv'
    # And Poppler Utils (for pdf2image) installed on your system.
    process_active_flyers()
