import os
import json
import requests
import sys
import time 
from typing import List, Dict, Any
from dotenv import load_dotenv

# --- Configuration ---
INPUT_FILE = 'merged_retail_data.json'
OUTPUT_FILE = 'enriched_retail_data.json'
# Setting to 100 as per your previous working configuration.
BATCH_SIZE = 100 

# --- Fixed Category List (CRITICAL for data consistency) ---
PREDETERMINED_CATEGORIES = [
    "Fresh Produce (Obst & Gemüse)",
    "Meat & Poultry (Fleisch & Geflügel)",
    "Fish & Seafood (Fisch)",
    "Dairy & Eggs (Milchprodukte & Eier)",
    "Frozen Foods (Tiefkühl)",
    "Pantry & Baking (Grundnahrungsmittel)",
    "Drinks & Beverages (Getränke)",
    "Snacks & Confectionery (Süßwaren & Snacks)",
    "Household & Cleaning (Haushalt)",
    "Pet Supplies (Tiernahrung)",
    "Health & Beauty (Drogerie)",
    "Bread & Bakery (Brot & Gebäck)",
    "Miscellaneous" 
]

# --- Gemini API Configuration (Defaults, updated in __main__) ---
API_KEY = os.environ.get("GEMINI_API_KEY", "") 
API_MODEL = "gemini-2.5-flash" 
# URL is a global variable that needs to be accessible in process_batch
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{API_MODEL}:generateContent?key={API_KEY}"

# --- JSON Schema for Structured Output (MINIMALIST STRATEGY) ---
# The LLM only returns the necessary mapping 'id' and the five generated fields.
# This is the most reliable way to enforce structured output.
ENRICHED_OFFER_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {
                "type": "INTEGER", 
                "description": "The unique index from the input array used for mapping back to the original offer. This is required."
            },
            "productHash": {
                "type": "STRING", 
                "description": "A stable, unique ID for the canonical product concept (e.g., 'schweinefilet-530g'). Should be a lowercase string using only letters, numbers, and hyphens."
            },
            "category": {
                "type": "STRING", 
                "description": "The normalized product category. MUST be one of the enumerated values.",
                "enum": PREDETERMINED_CATEGORIES
            },
            "searchTags": {
                "type": "ARRAY", 
                "items": {"type": "STRING"}, 
                "description": "A list of 5-10 descriptive, multilingual keywords for fuzzy searching (e.g., ['milk', 'milch', 'dairy', 'drink', 'vollmilch'])."
            },
            "offerStartDate": {
                "type": "STRING", 
                "description": "The start date of the offer in YYYY-MM-DD format, parsed from the date range text in the offer. If parsing fails, use the current date (YYYY-MM-DD)."
            },
            "offerEndDate": {
                "type": "STRING", 
                "description": "The end date of the offer in YYYY-MM-DD format, parsed from the date range text in the offer. If parsing fails, use the current date (YYYY-MM-DD)."
            },
        },
        "required": ["id", "productHash", "category", "searchTags", "offerStartDate", "offerEndDate"]
    }
}

def load_merged_data(filepath: str) -> List[Dict[str, Any]]:
    """Loads the consolidated data from the merged JSON file."""
    if not os.path.exists(filepath):
        print(f"FATAL ERROR: Input file not found at {filepath}. Please run json_merger.py first.")
        sys.exit(1)
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('mergedOffers', [])
    except json.JSONDecodeError:
        print(f"FATAL ERROR: Failed to decode JSON from {filepath}.")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR: An unexpected error occurred while reading {filepath}: {e}")
        sys.exit(1)


def prepare_batch_for_llm(batch: List[Dict[str, Any]], offset_index: int) -> List[Dict[str, Any]]:
    """
    Strips down the full offer data to the minimal set needed for enrichment 
    (Name, Unit, Date Range, Store Name) and adds a unique 'id' for mapping.
    This is the key component from your working V1 script.
    """
    minimal_batch = []
    for i, offer in enumerate(batch):
        minimal_batch.append({
            "id": offset_index + i, # Unique index for mapping results back
            "productName": offer.get("productName", ""),
            "Unit": offer.get("Unit", ""),
            "Availability (Date Range)": offer.get("Availability (Date Range)", ""),
            "storeName": offer.get("storeName", ""),
        })
    return minimal_batch


def process_batch(batch: List[Dict[str, Any]], batch_index: int, offset_index: int) -> List[Dict[str, Any]]:
    """
    Sends a batch for enrichment, requesting only the ID and new fields,
    and handles retries with exponential backoff.
    """
    
    # Use the minimal input format (V1 strategy)
    minimal_input = prepare_batch_for_llm(batch, offset_index)
    
    system_prompt = (
        "You are a Retail Data Normalization Engine. Your task is to process a list of product offers, "
        "add a stable product hash, normalize the category, generate search tags, and parse the offer dates. "
        "Return an array containing the 'id' and only the five requested enriched fields. "
        "STRICTLY choose the 'category' from the provided ENUM list in the schema. "
        "Rule 1: The 'productHash' must be a unique, canonical identifier (e.g., 'schweinefilet-530g'). "
        "Rule 2: Parse all date ranges into two separate YYYY-MM-DD fields. If a range is ambiguous, use the current date for both start and end."
    )
    
    offers_json_string = json.dumps(minimal_input, ensure_ascii=False)
    user_query = f"Enrich the following array of {len(batch)} product items. Return the 'id' and only the generated fields:\n\n{offers_json_string}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": ENRICHED_OFFER_SCHEMA
        },
        # NOTE: Removed 'tools' property from the previous version to align with 
        # the simplicity of the working V1 script.
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }

    headers = {'Content-Type': 'application/json'}
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status() 
            
            result = response.json()
            # Extract the raw JSON string from the nested response structure
            json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
            
            if not json_text:
                raise ValueError("LLM response did not contain structured content.")

            # Attempt to clean and parse the JSON response
            parsed_json = json.loads(json_text.strip())
            
            if isinstance(parsed_json, list):
                # We return the list of enriched fields + ID
                return parsed_json
            else:
                raise ValueError(f"LLM returned an invalid array structure: {type(parsed_json)}.")

        except Exception as e:
            if attempt < max_retries - 1:
                # Suppress logging for clarity; just backoff and retry
                time.sleep(2**(attempt+1))
            else:
                print(f"ERROR: Batch {batch_index} failed after {max_retries} attempts. Skipping this batch. Error: {e}")
                return [] 
    return [] 


def enrich_data_with_llm(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Splits offers into minimal batches, processes, and merges results back 
    into the original list. (V1 merging strategy)
    """
        
    print(f"\n--- Starting Gemini Enrichment for {len(offers)} offers... ---")
    
    total_offers = len(offers)
    batches = [offers[i:i + BATCH_SIZE] for i in range(0, total_offers, BATCH_SIZE)]
    
    print(f"Total Offers: {total_offers}. Processing in {len(batches)} batches of size {BATCH_SIZE}.")

    successful_enrichments = 0
    current_offset = 0 
    
    for i, batch in enumerate(batches):
        batch_index = i + 1
        print(f"Processing Batch {batch_index}/{len(batches)} (Offers: {len(batch)}) | Starting Index: {current_offset}")
        
        # We pass the current offset so the LLM can give us an absolute ID for mapping
        processed_batch = process_batch(batch, batch_index, current_offset)
        
        # Map the enriched data back to the original list (V1's robust merging)
        for enriched_item in processed_batch:
            try:
                original_index = enriched_item.get('id')
                if original_index is not None and 0 <= original_index < total_offers:
                    # Update the original offer object in place
                    offers[original_index].update({
                        "productHash": enriched_item.get("productHash"),
                        "category": enriched_item.get("category"),
                        "searchTags": enriched_item.get("searchTags"),
                        "offerStartDate": enriched_item.get("offerStartDate"),
                        "offerEndDate": enriched_item.get("offerEndDate"),
                    })
                    successful_enrichments += 1
            except Exception as e:
                print(f"WARNING: Failed to merge enriched item with id {enriched_item.get('id')}. Skipping record: {e}")

        current_offset += len(batch)
        
        if processed_batch:
            time.sleep(1) # Delay between batches

    # Filter out any offers that were skipped (if they still lack a productHash)
    enriched_data = [offer for offer in offers if 'productHash' in offer]
    
    print(f"\n--- Batching Complete ---")
    print(f"Successfully enriched {successful_enrichments} records out of {total_offers} total offers.")
    return enriched_data


# --- Main Execution ---
if __name__ == "__main__":
    
    # --- Load .env file and re-configure API Key ---
    load_dotenv()
    
    API_KEY = os.environ.get("GEMINI_API_KEY")

    if not API_KEY:
        print("FATAL ERROR: GEMINI_API_KEY environment variable is not set.")
        print("Please ensure it is set either in your shell or in a local .env file.")
        sys.exit(1)
        
    # Re-calculate the global API_URL with the now-available key
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{API_MODEL}:generateContent?key={API_KEY}"
    # --- END API KEY FIX ---
        
    # 1. Load the merged data
    merged_offers = load_merged_data(INPUT_FILE)
    
    if not merged_offers:
        print("No offers loaded. Exiting.")
        sys.exit(0)
        
    # 2. Enrich the data using the Gemini API
    try:
        enriched_data = enrich_data_with_llm(merged_offers)
        
        # 3. Save the enriched data
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, ensure_ascii=False, indent=2)
            
        print(f"\n--- Enrichment Finalized ---")
        print(f"Final enriched data saved to '{OUTPUT_FILE}'.")
        print(f"Successfully processed {len(enriched_data)} records.")

    except Exception as e:
        print(f"Process failed during enrichment stage. See error above: {e}")
