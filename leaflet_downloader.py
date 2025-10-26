import os
import json
import requests
import re
from datetime import datetime

# --- CONFIGURATION ---
# Path to the daily overwritten file from the scraper
INPUT_JSON_PATH = "current_active_flyers.json"
# Directory where full PDFs will be saved
DOWNLOAD_DIR = "downloads"

# Ensure the downloads directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- HELPER FUNCTIONS ---

def slugify(text):
    """Converts text to a safe filename slug."""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '', text) # Removing hyphens/spaces to keep it clean
    return text[:50] # Limit length

def download_active_flyers(flyers_data):
    """
    Iterates through flyers, downloads them, and saves them to the DOWNLOAD_DIR.
    This script relies on the Cleanup step to remove outdated files.
    """
    download_count = 0
    
    for flyer in flyers_data:
        pdf_url = flyer.get('PDF_URL')
        retailer = flyer.get('Retailer', 'Unknown')
        end_date = flyer.get('EndDate', datetime.now().strftime("%Y-%m-%d"))
        title = flyer.get('Title', 'Flyer')

        if not pdf_url:
            print(f"Skipping flyer with missing PDF_URL: {title}")
            continue

        print(f"\n--- ACTIVE FLYER DETECTED: {retailer} | {title} ({end_date}) ---")
        
        # 1. Determine a unique local filename based on retailer, end date, and title
        filename_slug = f"{retailer}_{end_date}_{slugify(title)}.pdf"
        local_filepath = os.path.join(DOWNLOAD_DIR, filename_slug)

        # 2. DOWNLOAD PDF (This will overwrite any existing file, ensuring the latest version)
        print(f"1. Downloading PDF from {pdf_url}...")
        try:
            # Using stream=True for efficiency with potentially large files
            response = requests.get(pdf_url, stream=True, timeout=30) 
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            with open(local_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"   -> Successfully saved PDF to: {local_filepath} (Overwriting if file existed)")
            
            # Note: No logging or further processing logic here. That's for the next script.
            download_count += 1

        except requests.exceptions.RequestException as e:
            print(f"   -> ERROR during download for {pdf_url}. Skipping: {e}")
            
    print(f"\n--- Download Summary: {download_count} flyers downloaded/verified. ---")


if __name__ == "__main__":
    
    # 1. Load the list of flyers to process from the scraper output
    flyers_data = []
    if os.path.exists(INPUT_JSON_PATH):
        try:
            with open(INPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                flyers_data = json.load(f)
            print(f"1. Read {len(flyers_data)} active flyers from {INPUT_JSON_PATH}.")
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"ERROR: Could not read or decode the input file {INPUT_JSON_PATH}. Exiting.")
            exit(1)
    else:
        print(f"ERROR: Input file {INPUT_JSON_PATH} not found. Did the scraper run?")
        exit(1)

    # 2. CLEANUP STEP: Remove expired PDFs from the download directory
    # This ensures only currently listed flyers remain in the directory.
    
    # Calculate expected filenames first
    expected_filenames = set()
    for flyer in flyers_data:
        retailer = flyer.get('Retailer', 'Unknown')
        end_date = flyer.get('EndDate', datetime.now().strftime("%Y-%m-%d"))
        title = flyer.get('Title', 'Flyer')
        # Use the same logic as the slug generation in download_active_flyers
        filename_slug = f"{retailer}_{end_date}_{slugify(title)}.pdf"
        expected_filenames.add(filename_slug)

    print("\n2. Starting Cleanup of Expired PDFs...")
    deleted_count = 0
    for filename in os.listdir(DOWNLOAD_DIR):
        # Only process PDF files, and check if the file name is NOT in the expected set
        if filename.endswith(".pdf") and filename not in expected_filenames:
            try:
                os.remove(os.path.join(DOWNLOAD_DIR, filename))
                print(f"   -> Deleted expired PDF: {filename}")
                deleted_count += 1
            except Exception as e:
                print(f"   -> Error deleting {filename}: {e}")

    print(f"Cleanup complete. {deleted_count} expired PDFs removed.")

    # 3. Execute download logic (downloads all files listed in the JSON)
    download_active_flyers(flyers_data)
    
    print("Downloader script finished. Directory now contains only current, active flyers.")
