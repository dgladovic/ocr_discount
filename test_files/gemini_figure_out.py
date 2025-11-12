import os
import io
import json
import sys
import glob
from google import genai
from google.genai import types
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Directory created by downloader_extractor.py
DOWNLOAD_DIR = "downloads"
# Log file to track which PDF filenames have been successfully processed (categorized)
PROCESSED_LOG_PATH = "processed_flyer_log.json"
# Directory where final JSON data will be saved
OUTPUT_JSON_DIR = "extracted_json"
API_MODEL = "gemini-2.5-flash"

# Ensure the output directory exists
os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)

# 1. SCHEMA FOR INDIVIDUAL PRODUCT OFFERS
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

# 2. SCHEMA FOR CATEGORY-WIDE ANNOUNCEMENTS (Banners)
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

# 3. TOP-LEVEL SCHEMA to hold both arrays
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
            # The log stores a list, which we convert to a set for fast lookup
            return set(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"Warning: Could not read or decode {PROCESSED_LOG_PATH}. Starting with an empty log.")
        return set()

def save_processed_log(processed_files):
    """Saves the updated set of processed PDF filenames to the log file."""
    try:
        with open(PROCESSED_LOG_PATH, 'w', encoding='utf-8') as f:
            # Convert set back to list for JSON serialization
            json.dump(list(processed_files), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not save log file: {e}")


def analyze_pdf_with_gemini_vision(client: genai.Client, pdf_file_path: str, output_json_name: str):
    """
    Splits the PDF into images, uploads them to the Gemini File Service,
    runs the structured extraction query, and cleans up the uploaded files.
    """
    uploaded_files = []
    
    try:
        # 1. Convert PDF pages to images
        print(f"--- 1. Splitting '{os.path.basename(pdf_file_path)}' into high-DPI images... ---")
        try:
            pages = convert_from_path(pdf_file_path, dpi=300) 
        except Exception as e:
            print(f"ERROR: PDF conversion failed. Is Poppler Utils installed correctly?")
            print(f"Details: {e}")
            return False # Indicate failure

        print(f"Successfully split PDF into {len(pages)} pages.")

        # 2. Save images to buffer and upload
        print("\n--- 2. Uploading images to Gemini File Service... ---")
        
        for i, page_image in enumerate(pages):
            page_num = i + 1
            img_byte_arr = io.BytesIO()
            # Save image to buffer
            page_image.save(img_byte_arr, format='PNG') 
            img_byte_arr.seek(0)

            # Upload using the SDK
            upload_config = types.UploadFileConfig(mime_type='image/png')
            file = client.files.upload(file=img_byte_arr, config=upload_config)
            
            uploaded_files.append(file)
            print(f"  [P{page_num}] Uploaded file: {file.name}")
        
        if not uploaded_files:
            print("ERROR: No images were generated or uploaded.")
            return False

        # 3. Create the multimodal prompt structure
        prompt_text = (
            "Analyze the provided flyer images (potentially multiple pages). "
            "Perform OCR on all images and extract all distinct product offers and category announcements. "
            
            "**Part 1: Individual Product Offers** - Extract detailed information (name, prices, size, discount, availability) for every product on sale and classify it into a specific product category (e.g., Meat, Dairy, Produce). "
            
            "**Part 2: Category-Wide Banners** - Identify any large, prominent banners that announce discounts applying to an entire category (e.g., '25% off all Tea', 'Beer is on sale this weekend'). Record these in the 'categoryAnnouncements' array. "
            
            "Return the results ONLY as a single JSON object that strictly conforms to the provided schema, containing both 'productOffers' and 'categoryAnnouncements'."
        )

        # The 'contents' list combines all file objects and the text instruction
        contents = uploaded_files + [prompt_text]

        # 4. Generate structured content
        print("\n--- 3. Sending query to Gemini for structured extraction... ---")
        response = client.models.generate_content(
            model=API_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FLYER_DATA_SCHEMA 
            )
        )

        # 5. Save the extracted data
        output_filepath = os.path.join(OUTPUT_JSON_DIR, output_json_name)
        print("\n" + "="*50)
        print("4. Saving Structured JSON Output")
        
        try:
            parsed_json = json.loads(response.text)
            
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, ensure_ascii=False, indent=2)
            
            print(f"SUCCESS: Data successfully saved to '{output_filepath}'.")
            return True # Indicate success
            
        except json.JSONDecodeError:
            print("ERROR: Failed to parse JSON response from the model.")
            # print("Raw Model Output (printing to console):\n", response.text)
            return False

    except Exception as e:
        print(f"\nFATAL ERROR during analysis: {e}")
        return False
        
    finally:
        # 6. Clean up by deleting the uploaded files
        if uploaded_files:
            print(f"\n--- 5. Cleaning up {len(uploaded_files)} uploaded files... ---")
            for file in uploaded_files:
                try:
                    client.files.delete(name=file.name)
                except Exception as cleanup_e:
                    print(f"Warning: Failed to clean up file {file.name}. Error: {cleanup_e}")
            print("Cleanup complete.")


def process_active_flyers():
    """
    Main function to iterate through downloaded PDFs, check the log, and categorize new ones.
    """
    # 0. Load environment variables and initialize client
    load_dotenv() 
    if 'GEMINI_API_KEY' not in os.environ:
        print("FATAL ERROR: The GEMINI_API_KEY environment variable is not set.")
        print("Please ensure it is set either in your shell or in a local .env file.")
        return

    try:
        client = genai.Client()
    except Exception as e:
        print(f"FATAL ERROR: Could not initialize Gemini client: {e}")
        return

    # 1. Load the list of files already processed
    processed_files = load_processed_log()
    print(f"\n--- Categorizer Started ---")
    print(f"1. Loaded {len(processed_files)} previously processed file IDs (to skip API calls).")
    
    # 2. Iterate over currently downloaded PDFs
    pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f"2. No PDF files found in '{DOWNLOAD_DIR}'. Nothing to categorize.")
        return

    newly_categorized_count = 0
    
    for pdf_filepath in pdf_files:
        pdf_filename = os.path.basename(pdf_filepath)
        
        # The JSON output name is the PDF filename with a .json extension
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
    print(f"Total files tracked in log: {len(processed_files)}")


if __name__ == "__main__":
    # Note: Requires 'pip install google-genai pypdf pdf2image python-dotenv'
    # And Poppler Utils (for pdf2image) installed on your system.
    process_active_flyers()
