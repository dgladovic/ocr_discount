import os
import json
import sys
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- CONFIGURATION ---
INPUT_JSON_PATH = "input_scraped_data.json"
OUTPUT_JSON_PATH = "categorized_items.json"
API_MODEL = "gemini-2.5-flash"

# --- TARGET SCHEMA (Matches the PRODUCT_OFFER_SCHEMA from the flyer extractor) ---
# Note: This is an array structure so we can classify multiple items at once.
CLASSIFICATION_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "productName": {"type": "STRING", "description": "The name of the item on offer."},
            "category": {"type": "STRING", "description": "Determine the most specific food or product category (e.g., 'Meat & Poultry', 'Baked Goods', 'Dairy')."},
            "currentPrice": {"type": "STRING", "description": "The current promotional price, including currency (e.g., 5.99€)."},
            "oldPrice": {"type": "STRING", "description": "The original, non-sale price before discount (e.g., 7.99€). If the old price is not visible, use 'N/A'."},
            "packageSize": {"type": "STRING", "description": "The size of the product package (e.g., '530 g', '1 kg', '3 pcs', '1 liter')."},
            "unitPrice": {"type": "STRING", "description": "The price per standardized unit, usually per kg or per liter (e.g., '11.30/kg'). If not found, infer from packageSize and currentPrice or use 'N/A'."},
            "discount": {"type": "STRING", "description": "The discount amount or percentage (e.g., 25% off or -1.00€). If an oldPrice exists, calculate the percentage or difference. If not, use 'N/A'."},
            "availabilityDateRange": {"type": "STRING", "description": "The start and end date of the offer (e.g., '20.10. - 22.10.' or 'Mon-Wed')."}
        },
        # NOTE: The required fields must match the target schema exactly
        "required": ["productName", "category", "currentPrice", "packageSize", "availabilityDateRange"] 
    }
}

def classify_scraped_data():
    """
    Reads raw product data, sends it to Gemini for classification and field cleanup,
    and saves the structured output to a new JSON file.
    """
    load_dotenv()

    if 'GEMINI_API_KEY' not in os.environ:
        print("FATAL ERROR: The GEMINI_API_KEY environment variable is not set.")
        return

    if not os.path.exists(INPUT_JSON_PATH):
        print(f"ERROR: Input file not found at '{INPUT_JSON_PATH}'.")
        print(f"ACTION REQUIRED: Ensure '{INPUT_JSON_PATH}' exists and contains your scraped data.")
        return

    try:
        # 1. Read the input data
        print(f"--- 1. Reading input data from '{INPUT_JSON_PATH}'... ---")
        with open(INPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        if not raw_data:
            print("WARNING: Input file is empty. Exiting.")
            return

        print(f"Successfully loaded {len(raw_data)} items for classification.")

        # 2. Initialize client and create the prompt
        client = genai.Client()
        
        # We format the raw data as a string within the prompt for clarity and classification
        raw_data_string = json.dumps(raw_data, indent=2)

        prompt_text = (
            "You are an expert data classifier for supermarket products. Your task is to transform the "
            "provided raw scraped JSON data (from a single store) into a clean, normalized structure. "
            "Your output must strictly adhere to the provided JSON schema.\n\n"
            
            "**Classification and Transformation Rules:**\n"
            "1. **Map Fields:** Map the input fields ('Name', 'Price', 'Old Price', 'Unit', 'Availability (Date Range)') to the output fields ('productName', 'currentPrice', 'oldPrice', 'packageSize', 'availabilityDateRange').\n"
            "2. **Infer Category:** Based on the product name, classify the item into a specific food category (e.g., 'Meat & Poultry', 'Baked Goods').\n"
            "3. **Clean Unit Price:** Extract the actual price per unit (e.g., '11.30/kg') from the 'Unit' field and place it in the 'unitPrice' field.\n"
            "4. **Calculate Discount:** If 'oldPrice' is available, calculate the discount percentage or difference and place it in the 'discount' field.\n"
            
            f"\n**RAW DATA TO CLASSIFY:**\n{raw_data_string}"
        )

        # 3. Generate structured content
        print("\n--- 2. Sending data to Gemini for classification... ---")
        response = client.models.generate_content(
            model=API_MODEL,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CLASSIFICATION_SCHEMA
            )
        )

        # 4. Save the categorized data
        print("\n" + "="*50)
        print("3. Structured JSON Output")
        
        try:
            parsed_json = json.loads(response.text)
            
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, ensure_ascii=False, indent=2)
            
            print(f"SUCCESS: Categorized data saved to '{OUTPUT_JSON_PATH}'.")
            
        except json.JSONDecodeError:
            print("ERROR: Failed to parse JSON response from the model.")
            print("Raw Model Output (printing to console):\n", response.text)

        print("="*50)

    except Exception as e:
        print(f"\nFATAL ERROR during classification: {e}")

if __name__ == "__main__":
    classify_scraped_data()
