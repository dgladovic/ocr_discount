import json
import os
import sys
from datetime import datetime

# --- Configuration ---
# The script will now scan this directory for all .json files
INPUT_DIR = 'extracted_json'
OUTPUT_FILE = 'merged_retail_data.json'

def get_store_name_from_path(filepath):
    """
    Infers the clean store name from the filename for proper normalization.
    e.g., 'spar_offers.json' -> 'SPAR'
    """
    # Get the filename part (e.g., 'spar_offers.json')
    filename = os.path.basename(filepath)
    # Get the base name before the first underscore (e.g., 'spar')
    store_key = filename.split('_')[0].lower()

    # Simple mapping for better display names
    name_map = {
        'spar': 'SPAR',
        'billa': 'BILLA',
        'hofer': 'HOFER',
        'lidl': 'LIDL',
        # Add any other store mappings here if needed
    }
    # Use .get() with a default to handle unexpected filenames gracefully
    return name_map.get(store_key, store_key.upper())


def merge_and_normalize_data(input_dir, output_file):
    """
    Dynamically finds and merges product offers from all JSON files 
    in the specified directory, adding a 'storeName' field to each offer.
    """
    all_offers = []
    input_files_full_path = []
    
    # 1. Check directory existence and find all .json files
    if not os.path.isdir(input_dir):
        print(f"ERROR: Input directory not found at {input_dir}. Cannot merge files.")
        print("Please ensure the 'extracted_json' directory exists and contains your data.")
        sys.exit(1)

    # Dynamically find all .json files in the directory
    for filename in os.listdir(input_dir):
        if filename.endswith('.json'):
            input_files_full_path.append(os.path.join(input_dir, filename))
            
    print(f"Found {len(input_files_full_path)} JSON files in '{input_dir}'...")
    
    if not input_files_full_path:
        print("WARNING: No JSON files found to merge. Output file will be empty.")

    # 2. Process and normalize each file
    for file_path in input_files_full_path:
        # Get store name from the file path/name
        store_name = get_store_name_from_path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # We assume the core list of offers is under the 'productOffers' key
            # This is the most common key in a scraper's output structure.
            offers = data.get('productOffers', [])
            
            if not offers:
                print(f"WARNING: File {file_path} (Store: {store_name}) loaded but found no 'productOffers' key. Skipping.")
                continue

            # Normalize: Add the storeName field to every offer object
            processed_count = 0
            for offer in offers:
                offer['storeName'] = store_name
                all_offers.append(offer)
                processed_count += 1
                
            print(f"SUCCESS: Added {processed_count} offers from {store_name} (File: {file_path})")

        except json.JSONDecodeError:
            print(f"ERROR: Failed to decode JSON from {file_path}. Is the file corrupted?")
        except Exception as e:
            print(f"An unexpected error occurred while processing {file_path}: {e}")

    # 3. Create the final consolidated structure
    final_output = {
        "metadata": {
            "totalOffers": len(all_offers),
            "mergedFromFiles": len(input_files_full_path),
            "dateGenerated": datetime.now().isoformat()
        },
        "mergedOffers": all_offers
    }

    # 4. Write the consolidated data to the output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Use indent for readability
            json.dump(final_output, f, ensure_ascii=False, indent=4)
        print(f"\n--- Merge Complete ---")
        print(f"Successfully wrote {len(all_offers)} total offers to {output_file}")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to write output file {output_file}: {e}")


if __name__ == "__main__":
    # The script will run the main function, ensuring the directory exists is 
    # handled by the check inside the function itself.
    merge_and_normalize_data(INPUT_DIR, OUTPUT_FILE)
